"""
Motor de optimización de cuadrantes basado en Google OR-Tools (CP-SAT).

Se modela el problema como un *Constraint Satisfaction Problem* (CSP) con
objetivos múltiples ponderados. CP-SAT combina programación por restricciones,
programación lineal entera y búsqueda con *backtracking*, por lo que cubre de
forma nativa todas las técnicas exigidas por el pliego (CSP, programación lineal,
optimización multiobjetivo, heurísticas y backtracking).

Estrategia de modelado
-----------------------
* Variable de decisión ``x[t, d, turno, puesto] ∈ {0,1}``: el trabajador ``t``
  cubre ese turno-puesto el día ``d``.
* **Restricciones duras** (nunca se incumplen salvo imposibilidad operativa):
    - Un trabajador realiza como máximo un turno por día.
    - Restricciones individuales (puestos habilitados, prohibición de noches...).
    - Disponibilidad (ausencias y días no disponibles).
    - Cobertura de todos los puestos (con variable de holgura penalizada para
      poder detectar y justificar la imposibilidad en lugar de fallar).
    - No encadenar noche -> mañana del día siguiente.
    - Sábado y domingo del mismo fin de semana los realiza el mismo trabajador.
    - Máximo de días y de noches consecutivos.
    - Evitar noche justo antes de vacaciones y al reincorporarse.
* **Objetivos blandos** (ponderados y minimizados conjuntamente):
    - Equilibrio de horas, horas extra, noches y fines de semana.
    - Compensación según la memoria histórica.
    - Rotación de puestos, preferencias, recuperación tras noches, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ortools.sat.python import cp_model

from ..config.configuracion import Configuracion
from ..config.constantes import (
    HORAS_POR_TURNO,
    Puesto,
    TipoAusencia,
    Turno,
    turnos_puesto_requeridos,
)
from ..datos.modelos import Asignacion, Ausencia, Cuadrante, RestriccionTemporal, Trabajador
from ..dominio.calendario import CalendarioMes
from ..dominio.historico import CargaHistorica


@dataclass
class ResultadoOptimizacion:
    """Resultado de una ejecución del optimizador."""

    cuadrante: Cuadrante
    estado_solver: str            # OPTIMAL, FEASIBLE, INFEASIBLE...
    puestos_sin_cubrir: list[tuple[int, str, str]]  # (día, turno, puesto)
    valor_objetivo: float
    tiempo_segundos: float
    mensajes: list[str]

    @property
    def hay_incidencias(self) -> bool:
        return bool(self.puestos_sin_cubrir)


# Penalización muy alta para dejar un puesto sin cubrir (solo como último recurso).
PENALIZACION_SIN_CUBRIR = 1_000_000
# Penalización por cada día de descanso aislado. Alta para que se respete el mínimo
# de dos días libres seguidos, pero muy por debajo de la de cobertura: así la regla
# cede antes de dejar un puesto sin cubrir (nunca causa un problema operativo).
PENALIZACION_DESCANSO_AISLADO = 8_000
# Penalización por desviación en el reparto de F1 de mañana laborable entre jefes.
PENALIZACION_REPARTO_F1 = 10_000
# Recompensa por cada día trabajado de quien tiene «maximizar_dias» (trabaja el
# máximo de días disponibles). Alta para que llene sus días, pero por debajo del
# objetivo individual de fines de semana (20_000), de modo que NO le haga hacer
# más fines de semana de la cuenta, y muy por debajo de la cobertura.
RECOMPENSA_MAXIMIZAR_DIAS = 3_000
# Penalización por partir un fin de semana a caballo entre dos meses (el sábado en
# un mes y el domingo en el siguiente los hace gente distinta). Alta, pero BLANDA:
# cede ante el límite de días consecutivos, que protege el descanso.
PENALIZACION_FINDE_PARTIDO = 6_000


class OptimizadorCuadrante:
    """Construye y resuelve el modelo CP-SAT de un cuadrante mensual."""

    def __init__(
        self,
        anio: int,
        mes: int,
        trabajadores: list[Trabajador],
        configuracion: Configuracion,
        ausencias: list[Ausencia] | None = None,
        restricciones: list[RestriccionTemporal] | None = None,
        festivos: set[date] | None = None,
        carga_historica: dict[int, CargaHistorica] | None = None,
        cuadrante_previo: Cuadrante | None = None,
    ):
        self.anio = anio
        self.mes = mes
        self.trabajadores = trabajadores
        self.config = configuracion
        self.ausencias = ausencias or []
        self.restricciones = restricciones or []
        self.calendario = CalendarioMes(anio, mes, festivos or set())
        self.carga_historica = carga_historica or {}
        self.cuadrante_previo = cuadrante_previo

        self.modelo = cp_model.CpModel()
        # x[(t, d, turno, puesto)] -> variable booleana.
        self.x: dict[tuple[int, int, Turno, Puesto], cp_model.IntVar] = {}
        # Holgura por puesto sin cubrir.
        self.holgura: dict[tuple[int, Turno, Puesto], cp_model.IntVar] = {}
        self.mensajes: list[str] = []

        self._mapa_trabajadores = {t.id: t for t in trabajadores}
        self._disponibilidad = self._calcular_disponibilidad()
        # La reserva de MT-F1 a jefes solo tiene sentido si existe al menos un jefe;
        # de lo contrario el puesto quedaría sin poder cubrirse.
        self._hay_jefes = any(t.es_jefe_equipo for t in trabajadores)
        # Holguras de la regla de descansos agrupados (se penalizan en el objetivo).
        self._slacks_descanso: list[cp_model.IntVar] = []
        # Holguras de la continuidad del fin de semana partido entre meses.
        self._slacks_continuidad: list[cp_model.IntVar] = []
        # Penalizaciones que nacen dentro de los métodos de restricciones (donde no
        # se tiene a mano la lista de términos del objetivo) y se suman al final.
        self._penalizaciones_blandas: list = []
        # Final del mes anterior (continuidad entre meses).
        self._prev_turno: dict[tuple[int, int], bool] = {}
        self._prev_dias_seguidos: dict[int, int] = {}
        self._prev_ultimo_es_sabado = False
        self._preparar_mes_previo()

    # ------------------------------------------------------------------
    # Preparación de datos
    # ------------------------------------------------------------------
    def _calcular_disponibilidad(self) -> dict[tuple[int, int], bool]:
        """Determina si cada trabajador está disponible cada día del mes.

        No está disponible si tiene una ausencia que cubre ese día o si figura en
        los días no disponibles de una restricción temporal.
        """
        disponible: dict[tuple[int, int], bool] = {}
        for trabajador in self.trabajadores:
            for dia in self.calendario.dias:
                fecha = self.calendario.fecha(dia)
                libre = True
                for ausencia in self.ausencias:
                    if ausencia.trabajador_id == trabajador.id and ausencia.cubre(fecha):
                        libre = False
                        break
                disponible[(trabajador.id, dia)] = libre

        for restriccion in self.restricciones:
            for dia in restriccion.dias_no_disponibles:
                if 1 <= dia <= self.calendario.numero_dias:
                    disponible[(restriccion.trabajador_id, dia)] = False
        return disponible

    def _creditos_ausencia(self) -> dict[int, int]:
        """Horas de cómputo que aporta cada trabajador por sus ausencias computables.

        Cuenta los días del mes con vacaciones, permiso retribuido o formación y los
        multiplica por el valor por día (5,34 h por defecto). Se usa para equilibrar
        las horas de forma justa (quien tiene vacaciones parte con esa carga).
        """
        valor = self.config.horas_computo_por_dia_ausencia
        creditos: dict[int, int] = {}
        for trabajador in self.trabajadores:
            dias = 0
            for dia in self.calendario.dias:
                fecha = self.calendario.fecha(dia)
                for ausencia in self.ausencias:
                    if (ausencia.trabajador_id == trabajador.id and ausencia.cubre(fecha)
                            and ausencia.tipo.cuenta_como_trabajada):
                        dias += 1
                        break
            creditos[trabajador.id] = int(round(dias * valor))
        return creditos

    def _ausencia_del_dia(self, trabajador_id: int, dia: int) -> TipoAusencia | None:
        fecha = self.calendario.fecha(dia)
        for ausencia in self.ausencias:
            if ausencia.trabajador_id == trabajador_id and ausencia.cubre(fecha):
                return ausencia.tipo
        return None

    # ------------------------------------------------------------------
    # Construcción del modelo
    # ------------------------------------------------------------------
    def _reservado_a_jefes(self, turno: Turno, puesto: Puesto, festivo_finde: bool) -> bool:
        """Indica si el turno-puesto está reservado a los jefes de equipo ese día.

        El puesto F1 de mañana (MT-F1) en día laborable solo pueden realizarlo los
        jefes de equipo. En fin de semana o festivo no hay reserva.
        """
        return (
            self.config.reservar_f1_manana_a_jefes
            and self._hay_jefes
            and not festivo_finde
            and turno is Turno.MANANA_TARDE
            and puesto is Puesto.F1
        )

    def _crear_variables(self) -> None:
        for trabajador in self.trabajadores:
            for dia in self.calendario.dias:
                festivo_finde = self.calendario.es_festivo_o_finde(dia)
                for turno, puesto in turnos_puesto_requeridos(festivo_finde):
                    # Solo se crea la variable si el trabajador puede, en principio,
                    # realizar ese turno-puesto (restricción individual) y está
                    # disponible ese día.
                    if not trabajador.puede_realizar(turno, puesto):
                        continue
                    if not self._disponibilidad[(trabajador.id, dia)]:
                        continue
                    # Reserva de F1 de mañana a los jefes de equipo en día laborable:
                    # no se crea la variable para el resto de trabajadores, con lo que
                    # queda prohibido que lo realicen.
                    if self._reservado_a_jefes(turno, puesto, festivo_finde) and not trabajador.es_jefe_equipo:
                        continue
                    self.x[(trabajador.id, dia, turno, puesto)] = self.modelo.NewBoolVar(
                        f"x_{trabajador.id}_{dia}_{turno.value}_{puesto.value}"
                    )

    def _preparar_mes_previo(self) -> None:
        """Lee los últimos días del mes anterior para enlazar los dos meses.

        Guarda, por trabajador, qué turnos hizo en los últimos días (si fueron de
        noche), cuántos días seguidos encadenaba al terminar el mes y si el mes
        anterior acabó en sábado (fin de semana partido entre meses).
        """
        if self.cuadrante_previo is None:
            return
        import calendar as _calendario
        from datetime import date as _fecha

        previo = self.cuadrante_previo
        n_dias_previo = _calendario.monthrange(previo.anio, previo.mes)[1]
        self._prev_ultimo_es_sabado = (
            _fecha(previo.anio, previo.mes, n_dias_previo).weekday() == 5
        )
        for trabajador in self.trabajadores:
            seguidos = 0
            for atras in range(1, 9):           # últimos 8 días del mes anterior
                dia = n_dias_previo - atras + 1
                if dia < 1:
                    break
                asignacion = previo.obtener(trabajador.id, dia)
                if asignacion is not None and asignacion.es_trabajo:
                    self._prev_turno[(trabajador.id, atras)] = asignacion.turno.es_nocturno
                    if seguidos == atras - 1:
                        seguidos = atras
            self._prev_dias_seguidos[trabajador.id] = seguidos

    def _restriccion_continuidad_mes_previo(self) -> None:
        """Enlaza el arranque del mes con el final del mes anterior.

        * No se encadena una noche del último día del mes anterior con una jornada
          diurna el día 1.
        * Los máximos de días y de noches consecutivos se cuentan a caballo entre
          los dos meses.
        * Si el mes anterior acabó en sábado, el domingo (día 1) lo hace quien
          hizo ese sábado (el fin de semana no se parte por el cambio de mes).
        """
        if self.cuadrante_previo is None or not self.calendario.dias:
            return
        dias = self.calendario.dias
        dia_uno = dias[0]
        max_dias = self.config.descanso.max_dias_consecutivos
        max_noches = self.config.descanso.max_noches_consecutivas
        for trabajador in self.trabajadores:
            tid = trabajador.id
            # Noche el último día del mes anterior -> nada diurno el día 1.
            if self._prev_turno.get((tid, 1)) is True:
                for var in self._variable_trabaja(tid, dia_uno, solo_noche=False):
                    self.modelo.Add(var == 0)

            # Días consecutivos arrastrados del mes anterior.
            seguidos = self._prev_dias_seguidos.get(tid, 0)
            if seguidos and not trabajador.maximizar_dias:
                margen = max_dias - seguidos
                if margen <= 0:
                    for var in self._variable_trabaja(tid, dia_uno):
                        self.modelo.Add(var == 0)
                else:
                    ventana = [
                        v for d in dias[: margen + 1] for v in self._variable_trabaja(tid, d)
                    ]
                    if ventana:
                        self.modelo.Add(sum(ventana) <= margen)

            # Noches consecutivas arrastradas del mes anterior.
            noches_seguidas = 0
            for atras in range(1, 9):
                if self._prev_turno.get((tid, atras)) is True and noches_seguidas == atras - 1:
                    noches_seguidas = atras
                else:
                    break
            if noches_seguidas:
                margen_n = max_noches - noches_seguidas
                if margen_n <= 0:
                    for var in self._variable_trabaja(tid, dia_uno, solo_noche=True):
                        self.modelo.Add(var == 0)
                else:
                    ventana = [
                        v for d in dias[: margen_n + 1]
                        for v in self._variable_trabaja(tid, d, solo_noche=True)
                    ]
                    if ventana:
                        self.modelo.Add(sum(ventana) <= margen_n)

            # Fin de semana partido entre meses (mes anterior acaba en sábado).
            # Es un objetivo BLANDO: si el trabajador ya agotó sus días seguidos al
            # acabar el mes anterior, manda el descanso y el fin de semana se parte.
            if (self._prev_ultimo_es_sabado
                    and self.config.fin_de_semana.sabado_domingo_mismo_trabajador):
                vars_domingo = self._variable_trabaja(tid, dia_uno)
                bloqueado_por_descanso = (
                    seguidos and not trabajador.maximizar_dias and max_dias - seguidos <= 0
                )
                if vars_domingo and not bloqueado_por_descanso:
                    trabajo_el_sabado = (tid, 1) in self._prev_turno
                    objetivo = 1 if trabajo_el_sabado else 0
                    desvio = self.modelo.NewIntVar(0, 1, f"findepartido_{tid}")
                    if objetivo:
                        # No trabajar el domingo tras haber hecho el sábado: penaliza.
                        self.modelo.Add(desvio >= 1 - sum(vars_domingo))
                    else:
                        # Entrar el domingo sin haber hecho el sábado: penaliza.
                        self.modelo.Add(desvio >= sum(vars_domingo))
                    self._slacks_continuidad.append(desvio)

    def _restriccion_cobertura(self) -> None:
        """Cada puesto requerido debe cubrirse exactamente una vez (con holgura)."""
        for dia in self.calendario.dias:
            festivo_finde = self.calendario.es_festivo_o_finde(dia)
            for turno, puesto in turnos_puesto_requeridos(festivo_finde):
                candidatos = [
                    self.x[(t.id, dia, turno, puesto)]
                    for t in self.trabajadores
                    if (t.id, dia, turno, puesto) in self.x
                ]
                holgura = self.modelo.NewBoolVar(f"holgura_{dia}_{turno.value}_{puesto.value}")
                self.holgura[(dia, turno, puesto)] = holgura
                # Suma de asignados + holgura = 1  ->  si nadie puede, holgura=1.
                self.modelo.Add(sum(candidatos) + holgura == 1)

    def _restriccion_un_turno_por_dia(self) -> None:
        """Un trabajador realiza como máximo un turno-puesto cada día."""
        for trabajador in self.trabajadores:
            for dia in self.calendario.dias:
                variables = [
                    var for (t, d, _, _), var in self.x.items()
                    if t == trabajador.id and d == dia
                ]
                if variables:
                    self.modelo.Add(sum(variables) <= 1)

    def _variable_trabaja(self, trabajador_id: int, dia: int, solo_noche: bool | None = None):
        """Devuelve la lista de variables de trabajo de un trabajador ese día.

        :param solo_noche: ``True`` -> solo noches; ``False`` -> solo días;
                           ``None`` -> cualquiera.
        """
        resultado = []
        for (t, d, turno, _), var in self.x.items():
            if t != trabajador_id or d != dia:
                continue
            if solo_noche is True and not turno.es_nocturno:
                continue
            if solo_noche is False and turno.es_nocturno:
                continue
            resultado.append(var)
        return resultado

    def _restriccion_noche_manana(self) -> None:
        """Prohíbe encadenar una noche con una jornada diurna al día siguiente."""
        for trabajador in self.trabajadores:
            for dia in self.calendario.dias[:-1]:
                noches_hoy = self._variable_trabaja(trabajador.id, dia, solo_noche=True)
                dia_manana = self._variable_trabaja(trabajador.id, dia + 1, solo_noche=False)
                for vn in noches_hoy:
                    for vd in dia_manana:
                        self.modelo.Add(vn + vd <= 1)

    def _dias_puente(self, dia_festivo: int) -> list[int]:
        """Días del puente que forma un festivo con el fin de semana contiguo.

        * Festivo en lunes  -> puente sábado, domingo, lunes.
        * Festivo en viernes -> puente viernes, sábado, domingo.
        Si el festivo no es contiguo a un fin de semana, no forma puente.
        """
        dsem = self.calendario.dia_semana(dia_festivo)
        if dsem == 0:            # lunes
            bloque = [dia_festivo - 2, dia_festivo - 1, dia_festivo]
        elif dsem == 4:          # viernes
            bloque = [dia_festivo, dia_festivo + 1, dia_festivo + 2]
        else:
            return []
        return [d for d in bloque if 1 <= d <= self.calendario.numero_dias]

    def _restriccion_puente_festivo(self) -> None:
        """Quien trabaje un festivo que hace puente debe hacer el puente completo.

        Si un festivo forma puente con el fin de semana contiguo, el trabajador que
        cubra el festivo debe cubrir también el resto de días del puente (no se
        permite trabajar solo el festivo y librar el finde, ni al revés).
        """
        for dia in self.calendario.dias:
            if not self.calendario.es_festivo(dia):
                continue
            bloque = self._dias_puente(dia)
            if len(bloque) < 2:
                continue
            for trabajador in self.trabajadores:
                trabaja_fest = self._variable_trabaja(trabajador.id, dia)
                if not trabaja_fest:
                    continue
                for otro in bloque:
                    if otro == dia:
                        continue
                    trabaja_otro = self._variable_trabaja(trabajador.id, otro)
                    # trabaja(festivo) -> trabaja(otro día del puente).
                    self.modelo.Add(sum(trabaja_fest) <= (sum(trabaja_otro) if trabaja_otro else 0))

    def _restriccion_fines_semana(self) -> None:
        """Sábado y domingo del mismo fin de semana los realiza la misma persona."""
        if not self.config.fin_de_semana.sabado_domingo_mismo_trabajador:
            return
        for sabado, domingo in self.calendario.fines_de_semana():
            for trabajador in self.trabajadores:
                trabaja_sab = self._variable_trabaja(trabajador.id, sabado)
                trabaja_dom = self._variable_trabaja(trabajador.id, domingo)
                if not trabaja_sab or not trabaja_dom:
                    continue
                b_sab = self.modelo.NewBoolVar(f"sab_{trabajador.id}_{sabado}")
                b_dom = self.modelo.NewBoolVar(f"dom_{trabajador.id}_{domingo}")
                self.modelo.Add(sum(trabaja_sab) == b_sab)
                self.modelo.Add(sum(trabaja_dom) == b_dom)
                # El trabajador hace el sábado si y solo si hace el domingo.
                self.modelo.Add(b_sab == b_dom)

    def _restriccion_finde_solo_noche(self) -> None:
        """Trabajadores que en fin de semana solo pueden de noche.

        Si el trabajador tiene ``finde_solo_noche``, en sábado y domingo se le
        prohíben los turnos diurnos: si le toca fin de semana, será de noche.
        """
        for trabajador in self.trabajadores:
            if not getattr(trabajador, "finde_solo_noche", False):
                continue
            for dia in self.calendario.dias:
                if not self.calendario.es_fin_de_semana(dia):
                    continue
                for var in self._variable_trabaja(trabajador.id, dia, solo_noche=False):
                    self.modelo.Add(var == 0)

    def _restriccion_jefes_finde_distinto(self) -> None:
        """Dos jefes de equipo no coinciden en el mismo fin de semana.

        Cada jefe hace su fin de semana en una fecha distinta a la del otro, de modo
        que no cubren el mismo sábado/domingo. (Basta con controlar el sábado: la
        regla de sábado-domingo del mismo trabajador arrastra el domingo.)
        """
        jefes = [t for t in self.trabajadores if t.es_jefe_equipo]
        if len(jefes) < 2:
            return
        for dia in self.calendario.dias:
            if not self.calendario.es_sabado(dia):
                continue
            vars_sabado = []
            for jefe in jefes:
                vars_sabado += self._variable_trabaja(jefe.id, dia)
            if vars_sabado:
                self.modelo.Add(sum(vars_sabado) <= 1)

    def _restriccion_noche_viernes(self) -> None:
        """Una noche en viernes obliga a hacer el fin de semana completo de noche.

        No se permite un turno de noche el viernes salvo que ese mismo trabajador
        realice también la noche del sábado y la del domingo de ese fin de semana.
        Así no quedan noches sueltas de viernes desligadas del fin de semana.
        """
        if not self.config.fin_de_semana.noche_viernes_requiere_finde_completo:
            return
        for sabado, domingo in self.calendario.fines_de_semana():
            viernes = sabado - 1
            if viernes < 1:
                continue  # El viernes cae en el mes anterior; no se puede ligar.
            for trabajador in self.trabajadores:
                noche_vie = self._variable_trabaja(trabajador.id, viernes, solo_noche=True)
                if not noche_vie:
                    continue
                noche_sab = self._variable_trabaja(trabajador.id, sabado, solo_noche=True)
                noche_dom = self._variable_trabaja(trabajador.id, domingo, solo_noche=True)
                # noche_viernes -> noche_sábado  y  noche_viernes -> noche_domingo.
                # Si no hay variable de noche el sábado o el domingo (p. ej. no
                # disponible), la suma vale 0 y el viernes de noche queda prohibido.
                self.modelo.Add(sum(noche_vie) <= (sum(noche_sab) if noche_sab else 0))
                self.modelo.Add(sum(noche_vie) <= (sum(noche_dom) if noche_dom else 0))

    def _restriccion_consecutivos(self) -> None:
        """Limita días y noches consecutivos mediante ventanas deslizantes."""
        max_dias = self.config.descanso.max_dias_consecutivos
        max_noches = self.config.descanso.max_noches_consecutivas
        dias = self.calendario.dias

        for trabajador in self.trabajadores:
            # Quien trabaja el máximo de días queda exento del límite de días
            # consecutivos (puede encadenar muchos días seguidos de forma excepcional).
            if not trabajador.maximizar_dias:
                # Días consecutivos trabajados.
                ventana = max_dias + 1
                for inicio in range(0, len(dias) - ventana + 1):
                    variables = []
                    for offset in range(ventana):
                        variables += self._variable_trabaja(trabajador.id, dias[inicio + offset])
                    if variables:
                        self.modelo.Add(sum(variables) <= max_dias)

            # Límite PERSONAL de días seguidos, más estricto que el general. Es
            # blando: se penaliza cada día de más, pero cede si el servicio lo exige.
            propio = trabajador.max_dias_seguidos_preferido
            peso_propio = self.config.pesos.limite_dias_seguidos_individual
            if propio and peso_propio and not trabajador.maximizar_dias and propio < max_dias:
                ventana_p = propio + 1
                for inicio in range(0, len(dias) - ventana_p + 1):
                    variables = []
                    for offset in range(ventana_p):
                        variables += self._variable_trabaja(trabajador.id, dias[inicio + offset])
                    if variables:
                        holgura = self.modelo.NewIntVar(
                            0, ventana_p, f"seguidospropio_{trabajador.id}_{inicio}")
                        self.modelo.Add(sum(variables) <= propio + holgura)
                        self._penalizaciones_blandas.append(peso_propio * holgura)

            # Noches consecutivas.
            ventana_n = max_noches + 1
            for inicio in range(0, len(dias) - ventana_n + 1):
                variables = []
                for offset in range(ventana_n):
                    variables += self._variable_trabaja(
                        trabajador.id, dias[inicio + offset], solo_noche=True
                    )
                if variables:
                    self.modelo.Add(sum(variables) <= max_noches)

    def _dia_relativo(self, fecha) -> int | None:
        """Día del mes que se está planificando equivalente a ``fecha``.

        Devuelve el día tal cual si la fecha cae en este mes; un número por encima
        del último día si cae en el mes siguiente (por ejemplo, el 2 de noviembre
        es el «día 33» de octubre), de modo que las reglas que cuentan días hacia
        atrás desde una fecha funcionen aunque esa fecha esté en el mes siguiente.
        ``None`` si queda demasiado lejos para importar.
        """
        if fecha.year == self.anio and fecha.month == self.mes:
            return fecha.day
        siguiente = (self.anio + 1, 1) if self.mes == 12 else (self.anio, self.mes + 1)
        if (fecha.year, fecha.month) == siguiente:
            return self.calendario.numero_dias + fecha.day
        return None

    def _restriccion_vacaciones(self) -> None:
        """Evita noche antes de vacaciones y noche al reincorporarse."""
        params = self.config.vacaciones
        for ausencia in self.ausencias:
            if ausencia.tipo is not TipoAusencia.VACACIONES:
                continue
            # Día anterior al inicio de las vacaciones (si cae en el mes).
            if params.evitar_noche_antes:
                dia_antes = ausencia.fecha_inicio.day - 1
                if ausencia.fecha_inicio.month == self.mes and 1 <= dia_antes <= self.calendario.numero_dias:
                    for var in self._variable_trabaja(ausencia.trabajador_id, dia_antes, solo_noche=True):
                        self.modelo.Add(var == 0)
            # Día de reincorporación (día siguiente al fin de vacaciones).
            if params.evitar_noche_al_reincorporarse:
                dia_despues = ausencia.fecha_fin.day + 1
                if ausencia.fecha_fin.month == self.mes and 1 <= dia_despues <= self.calendario.numero_dias:
                    for var in self._variable_trabaja(ausencia.trabajador_id, dia_despues, solo_noche=True):
                        self.modelo.Add(var == 0)

    # ------------------------------------------------------------------
    # Objetivos blandos
    # ------------------------------------------------------------------
    def _construir_objetivo(self) -> None:
        pesos = self.config.pesos
        terminos: list = []

        # (1) Penalización dura por puestos sin cubrir.
        terminos.append(PENALIZACION_SIN_CUBRIR * sum(self.holgura.values()))

        # (1 bis) Penalización por descansos aislados (mínimo dos días libres
        # seguidos). Alta, pero cede antes que la cobertura del servicio.
        if self._slacks_descanso:
            terminos.append(PENALIZACION_DESCANSO_AISLADO * sum(self._slacks_descanso))
        if self._slacks_continuidad:
            terminos.append(PENALIZACION_FINDE_PARTIDO * sum(self._slacks_continuidad))
        terminos.extend(self._penalizaciones_blandas)

        # Totales por trabajador.
        turnos_totales: dict[int, cp_model.IntVar] = {}
        noches_totales: dict[int, cp_model.IntVar] = {}
        fines_totales: dict[int, cp_model.IntVar] = {}

        sabados = set(self.calendario.sabados())
        max_turnos = len(self.calendario.dias)

        for trabajador in self.trabajadores:
            vars_trab = [v for (t, _, _, _), v in self.x.items() if t == trabajador.id]
            vars_noche = [
                v for (t, _, turno, _), v in self.x.items()
                if t == trabajador.id and turno.es_nocturno
            ]
            vars_finde = [
                v for (t, d, _, _), v in self.x.items()
                if t == trabajador.id and d in sabados
            ]

            tt = self.modelo.NewIntVar(0, max_turnos, f"turnos_{trabajador.id}")
            self.modelo.Add(tt == (sum(vars_trab) if vars_trab else 0))
            turnos_totales[trabajador.id] = tt

            nt = self.modelo.NewIntVar(0, max_turnos, f"noches_{trabajador.id}")
            self.modelo.Add(nt == (sum(vars_noche) if vars_noche else 0))
            noches_totales[trabajador.id] = nt

            ft = self.modelo.NewIntVar(0, len(sabados), f"fines_{trabajador.id}")
            self.modelo.Add(ft == (sum(vars_finde) if vars_finde else 0))
            fines_totales[trabajador.id] = ft

        # (2) Equilibrio: minimizar el rango (máx - mín) de cada magnitud.
        # El rango de cada magnitud se calcula únicamente sobre el subconjunto de
        # trabajadores al que la regla aplica, para no distorsionar el equilibrio
        # con quienes tienen restricciones (p. ej. Luis y Fernando no hacen noches
        # ni más de un fin de semana, así que no deben arrastrar el reparto del
        # resto de la plantilla).
        ids = [t.id for t in self.trabajadores]
        ids_noche = [t.id for t in self.trabajadores if t.puede_hacer_noches]
        ids_finde_libre = [t.id for t in self.trabajadores if t.fines_semana_exactos is None]

        def termino_rango(valores: dict[int, cp_model.IntVar], cota: int, nombre: str,
                          ids_subconjunto: list[int] | None = None):
            objetivo = ids_subconjunto if ids_subconjunto is not None else ids
            if len(objetivo) < 2:
                return 0  # Con menos de dos trabajadores no hay reparto que equilibrar.
            maximo = self.modelo.NewIntVar(0, cota, f"max_{nombre}")
            minimo = self.modelo.NewIntVar(0, cota, f"min_{nombre}")
            for i in objetivo:
                self.modelo.Add(maximo >= valores[i])
                self.modelo.Add(minimo <= valores[i])
            rango = self.modelo.NewIntVar(0, cota, f"rango_{nombre}")
            self.modelo.Add(rango == maximo - minimo)
            return rango

        # Equilibrio de HORAS teniendo en cuenta las vacaciones y permisos: cada día
        # de ausencia computable «vale» horas (5,34 por defecto), de modo que quien
        # está de vacaciones ya parte con carga y hace proporcionalmente menos
        # turnos. Así el reparto de horas es realmente equitativo.
        creditos = self._creditos_ausencia()
        credito_max = max(creditos.values()) if creditos else 0
        cota_horas = HORAS_POR_TURNO * max_turnos + credito_max + 1
        carga_horas: dict[int, cp_model.IntVar] = {}
        for trabajador in self.trabajadores:
            carga = self.modelo.NewIntVar(0, cota_horas, f"carga_{trabajador.id}")
            self.modelo.Add(
                carga == HORAS_POR_TURNO * turnos_totales[trabajador.id] + creditos[trabajador.id]
            )
            carga_horas[trabajador.id] = carga

        # Quedan fuera del reparto de horas quienes se han ofrecido a cargar más:
        # el que pide trabajar el máximo de días («maximizar_dias») y el que asume
        # el sobrante («absorbe_exceso»). Incluirlos dispararía el rango y
        # arrastraría al resto hacia arriba.
        ids_horas = [t.id for t in self.trabajadores
                     if not t.maximizar_dias and not t.absorbe_exceso] or ids

        terminos.append(pesos.equilibrio_horas * termino_rango(
            carga_horas, cota_horas, "horas", ids_subconjunto=ids_horas))

        # El rango (máximo menos mínimo) solo aprieta a los dos extremos: quien
        # queda en medio puede desviarse cuanto quiera sin coste. Para que el
        # reparto sea parejo de verdad se penaliza además la desviación de CADA
        # trabajador respecto a un objetivo común, que el propio motor elige.
        if pesos.equilibrio_horas_extra and len(ids_horas) >= 2:
            objetivo_horas = self.modelo.NewIntVar(0, cota_horas, "objetivo_horas")
            for trabajador_id in ids_horas:
                desvio = self.modelo.NewIntVar(0, cota_horas, f"desviohoras_{trabajador_id}")
                self.modelo.Add(desvio >= carga_horas[trabajador_id] - objetivo_horas)
                self.modelo.Add(desvio >= objetivo_horas - carga_horas[trabajador_id])
                terminos.append(pesos.equilibrio_horas_extra * desvio)
        # Quien «absorbe_exceso» carga con la parte que no se puede repartir a
        # partes iguales: se le exige no quedar por debajo de ningún compañero. Así
        # el sobrante recae siempre en él y el resto queda parejo. Es un objetivo
        # blando: cede antes que dejar un puesto sin cubrir.
        absorbentes = [t.id for t in self.trabajadores if t.absorbe_exceso]
        if pesos.absorber_exceso and absorbentes and len(ids) > 1:
            for absorbente in absorbentes:
                otros = [i for i in ids if i != absorbente]
                if not otros:
                    continue
                # Un único término contra el MÁXIMO de los demás. Penalizar contra
                # cada compañero por separado multiplicaría el peso por el tamaño
                # de la plantilla y empujaría al absorbente muy por encima, en vez
                # de dejarle solo el sobrante.
                tope_otros = self.modelo.NewIntVar(0, cota_horas, f"topeotros_{absorbente}")
                for otro in otros:
                    self.modelo.Add(tope_otros >= carga_horas[otro])
                falta = self.modelo.NewIntVar(0, cota_horas, f"faltahoras_{absorbente}")
                self.modelo.Add(falta >= tope_otros - carga_horas[absorbente])
                terminos.append(pesos.absorber_exceso * falta)

        terminos.append(pesos.equilibrio_noches * termino_rango(
            noches_totales, max_turnos, "noches", ids_subconjunto=ids_noche))
        terminos.append(pesos.equilibrio_fines_semana * termino_rango(
            fines_totales, len(sabados) or 1, "fines", ids_subconjunto=ids_finde_libre))

        # Equilibrio ANUAL de festivos: se balancea el total (festivos ya trabajados
        # en meses anteriores + festivos de este mes), de modo que a lo largo del año
        # todos trabajen un número parecido de festivos. Quien más festivos lleva
        # recibe menos este mes.
        festivo_dias = [d for d in self.calendario.dias if self.calendario.es_festivo(d)]
        if festivo_dias:
            fest_hist = {
                t.id: (self.carga_historica[t.id].festivos if t.id in self.carga_historica else 0)
                for t in self.trabajadores
            }
            cota_fest = len(festivo_dias) + (max(fest_hist.values()) if fest_hist else 0) + 1
            carga_festivos: dict[int, cp_model.IntVar] = {}
            fest_mes_por_id: dict[int, cp_model.IntVar] = {}
            for trabajador in self.trabajadores:
                # El reparto equilibra los festivos realmente TRABAJADOS. Un festivo
                # que cae en vacaciones no cuenta como trabajado (quien estuvo de
                # vacaciones no queda "por delante" ni "por detrás" por ese día).
                vars_fest = [
                    v for d in festivo_dias
                    for v in self._variable_trabaja(trabajador.id, d)
                ]
                fest_mes = self.modelo.NewIntVar(0, len(festivo_dias), f"festmes_{trabajador.id}")
                self.modelo.Add(fest_mes == (sum(vars_fest) if vars_fest else 0))
                fest_mes_por_id[trabajador.id] = fest_mes
                total_fest = self.modelo.NewIntVar(0, cota_fest, f"festtot_{trabajador.id}")
                self.modelo.Add(total_fest == fest_mes + fest_hist[trabajador.id])
                carga_festivos[trabajador.id] = total_fest
            terminos.append(pesos.equilibrio_festivos * termino_rango(
                carga_festivos, cota_fest, "festivos"))
            # Además del rango, preferir dar los festivos del mes a quien MENOS lleva:
            # coste proporcional a los festivos ya trabajados en el año. Así, cuando
            # hay un valor atípico que fija el máximo (y el rango no distingue), el
            # motor sigue eligiendo a los de menor recuento (p. ej. da el festivo al
            # que lleva 0-1 antes que al que lleva 3).
            for trabajador in self.trabajadores:
                if fest_hist[trabajador.id]:
                    terminos.append(
                        pesos.equilibrio_festivos
                        * fest_hist[trabajador.id]
                        * fest_mes_por_id[trabajador.id])

        # (3) Compensación histórica: penaliza asignar turnos a quien más ha
        #     trabajado en meses anteriores (desvío positivo respecto a la media).
        if self.carga_historica:
            from ..dominio.historico import AgregadorHistorico

            desvios = AgregadorHistorico.normalizar_para_equilibrio(self.carga_historica, ids)
            for i in ids:
                desvio_horas = int(round(desvios.get(i, {}).get("horas", 0.0) / HORAS_POR_TURNO))
                desvio_noches = int(round(desvios.get(i, {}).get("noches", 0.0)))
                # Coste proporcional al exceso histórico.
                if desvio_horas != 0:
                    terminos.append(pesos.tener_en_cuenta_historico * desvio_horas * turnos_totales[i])
                if desvio_noches != 0:
                    terminos.append(pesos.tener_en_cuenta_historico * desvio_noches * noches_totales[i])

        # (4) Tope de fines de semana con holgura penalizada.
        tope = self.config.fin_de_semana.fines_semana_tope_duro
        n_sabados = len(sabados) or 1
        for i in ids:
            exceso = self.modelo.NewIntVar(0, n_sabados, f"exceso_finde_{i}")
            self.modelo.Add(exceso >= fines_totales[i] - tope)
            terminos.append(pesos.equilibrio_fines_semana * 50 * exceso)

        # (4 ter) Mínimo preferente de fines de semana: nadie debería quedarse a 0
        # mientras otros hacen dos o tres. Solo se aplica a quien NO tiene objetivo
        # individual y tiene sábados disponibles ese mes (si está de vacaciones en
        # todos, no se le penaliza por no llegar).
        minimo = self.config.fin_de_semana.fines_semana_objetivo_min
        if minimo:
            for trabajador in self.trabajadores:
                if trabajador.fines_semana_exactos is not None:
                    continue
                sabados_posibles = sum(
                    1 for d in sabados if self._variable_trabaja(trabajador.id, d)
                )
                if not sabados_posibles:
                    continue
                objetivo_min = min(minimo, sabados_posibles)
                falta = self.modelo.NewIntVar(0, n_sabados, f"falta_finde_{trabajador.id}")
                self.modelo.Add(falta >= objetivo_min - fines_totales[trabajador.id])
                terminos.append(pesos.equilibrio_fines_semana * 50 * falta)

        # (4 bis) Objetivo individual de fines de semana (p. ej. Luis y Fernando:
        # exactamente uno al mes). Se penaliza fuertemente cualquier desviación
        # respecto al número exacto, en ambos sentidos (ni más ni menos).
        for trabajador in self.trabajadores:
            objetivo = trabajador.fines_semana_exactos
            if objetivo is None:
                continue
            desv_pos = self.modelo.NewIntVar(0, n_sabados, f"finde_desv_pos_{trabajador.id}")
            desv_neg = self.modelo.NewIntVar(0, n_sabados, f"finde_desv_neg_{trabajador.id}")
            # desv_pos - desv_neg = fines_totales - objetivo   (desviación con signo).
            self.modelo.Add(fines_totales[trabajador.id] - objetivo == desv_pos - desv_neg)
            terminos.append(pesos.objetivo_finde_individual * (desv_pos + desv_neg))

        # (5) Preferencias de turno (día/noche) declaradas por el trabajador.
        for trabajador in self.trabajadores:
            if trabajador.prefiere_turno_noche:
                # Recompensar noches -> restar del coste.
                terminos.append(-pesos.respetar_preferencias * noches_totales[trabajador.id])
            if trabajador.prefiere_turno_dia:
                dias_trab = self.modelo.NewIntVar(0, max_turnos, f"dias_{trabajador.id}")
                self.modelo.Add(
                    dias_trab == turnos_totales[trabajador.id] - noches_totales[trabajador.id]
                )
                terminos.append(-pesos.respetar_preferencias * dias_trab)

        # (6) Agrupar el mes en BLOQUES de día y de noche, para no ir alternando
        #     mañana/noche constantemente. Se define una «fase» por día
        #     (0 = fase de mañana, 1 = fase de noche): trabajar de noche obliga a
        #     fase de noche y trabajar de mañana obliga a fase de mañana; los días
        #     libres quedan libres y sirven de transición. Se penaliza cada CAMBIO
        #     de fase, de modo que lo barato es hacer una parte del mes de día y
        #     otra de noche (los descansos intermedios no rompen el bloque).
        #     Además de contar los cambios, se exige que cada bloque dure un
        #     mínimo de días («dias_minimos_por_bloque»): un bloque de un solo día
        #     —una noche suelta entre mañanas— obliga a cambiar el horario de sueño
        #     para un único turno, que es justo el vaivén que se quiere evitar.
        min_bloque = max(1, self.config.descanso.dias_minimos_por_bloque)
        max_cambios = self.config.descanso.max_cambios_dia_noche
        if (pesos.agrupar_dia_noche or (pesos.bloques_minimos and min_bloque > 1)
                or (max_cambios and pesos.limite_cambios_fase)):
            for trabajador in self.trabajadores:
                fases: dict[int, cp_model.IntVar] = {}
                for dia in self.calendario.dias:
                    noches = self._variable_trabaja(trabajador.id, dia, solo_noche=True)
                    mananas = self._variable_trabaja(trabajador.id, dia, solo_noche=False)
                    if not noches and not mananas:
                        continue
                    fase = self.modelo.NewBoolVar(f"fase_{trabajador.id}_{dia}")
                    for var in noches:
                        self.modelo.Add(fase >= var)        # noche  -> fase noche
                    for var in mananas:
                        self.modelo.Add(fase <= 1 - var)    # mañana -> fase mañana
                    fases[dia] = fase
                dias_fase = sorted(fases)
                # Enlace con el mes anterior: si acabó el mes de noche (o de día),
                # empezar el nuevo mes en la otra fase también cuenta como cambio.
                fase_previa = None
                for atras in range(1, 9):
                    if (trabajador.id, atras) in self._prev_turno:
                        fase_previa = self._prev_turno[(trabajador.id, atras)]
                        break
                cambios: list[cp_model.IntVar] = []
                if fase_previa is not None and dias_fase:
                    primera = fases[dias_fase[0]]
                    cambio_ini = self.modelo.NewBoolVar(f"cambiofase_ini_{trabajador.id}")
                    if fase_previa:                      # venía de noche
                        self.modelo.Add(cambio_ini >= 1 - primera)
                    else:                                 # venía de día
                        self.modelo.Add(cambio_ini >= primera)
                    cambios.append(cambio_ini)
                for anterior, siguiente in zip(dias_fase, dias_fase[1:]):
                    cambio = self.modelo.NewBoolVar(f"cambiofase_{trabajador.id}_{anterior}")
                    self.modelo.Add(cambio >= fases[siguiente] - fases[anterior])
                    self.modelo.Add(cambio >= fases[anterior] - fases[siguiente])
                    cambios.append(cambio)
                if pesos.agrupar_dia_noche:
                    for cambio in cambios:
                        terminos.append(pesos.agrupar_dia_noche * cambio)

                # Tope de cambios de horario dentro del mes. Con 1, al trabajador
                # le queda una parte del mes entera de noches y otra entera de
                # mañanas. No se cuenta «cambio_ini» (el enlace con el mes
                # anterior): si contara, a quien llega cambiado del mes previo le
                # tocaría pasar el mes entero en un solo horario.
                internos = cambios[1:] if fase_previa is not None and dias_fase else cambios
                if max_cambios and pesos.limite_cambios_fase and internos:
                    exceso = self.modelo.NewIntVar(
                        0, len(internos), f"excesocambios_{trabajador.id}")
                    self.modelo.Add(sum(internos) <= max_cambios + exceso)
                    terminos.append(pesos.limite_cambios_fase * exceso)

                # Longitud mínima de bloque. Dos cambios de fase separados por menos
                # de «min_bloque» días dejan en medio un bloque más corto que el
                # mínimo, así que en cada ventana de ese tamaño solo se admite un
                # cambio. Es un objetivo blando (con holgura penalizada): cede si la
                # cobertura del servicio no deja otra opción.
                if pesos.bloques_minimos and min_bloque > 1:
                    for inicio in range(len(cambios) - min_bloque + 1):
                        ventana = cambios[inicio:inicio + min_bloque]
                        holgura = self.modelo.NewIntVar(
                            0, min_bloque - 1, f"bloquecorto_{trabajador.id}_{inicio}")
                        self.modelo.Add(sum(ventana) <= 1 + holgura)
                        terminos.append(pesos.bloques_minimos * holgura)

        # (6 bis) ROTACIÓN DE PUESTOS. Dos penalizaciones: encadenar el mismo
        #     puesto en días consecutivos, y acaparar un puesto a lo largo del mes.
        #     Sin esto el reparto de puestos salía por casualidad (nueve F1
        #     seguidos y luego diez F2, sin pisar MO ni EX en todo el mes).
        if pesos.rotacion_puestos:
            tope_puesto = max(1, self.config.max_turnos_mismo_puesto)
            # Índice (trabajador, día, puesto) -> variables, para no recorrer todo
            # el diccionario de variables una vez por combinación.
            por_tdp: dict[tuple[int, int, Puesto], list] = {}
            for (t, d, _turno, p), var in self.x.items():
                por_tdp.setdefault((t, d, p), []).append(var)
            for trabajador in self.trabajadores:
                for puesto in Puesto:
                    usa: dict[int, cp_model.IntVar] = {}
                    for dia in self.calendario.dias:
                        variables = por_tdp.get((trabajador.id, dia, puesto))
                        if not variables:
                            continue
                        u = self.modelo.NewBoolVar(
                            f"usa_{trabajador.id}_{dia}_{puesto.value}")
                        self.modelo.AddMaxEquality(u, variables)
                        usa[dia] = u
                    if not usa:
                        continue
                    # (a) mismo puesto dos días seguidos
                    dias_usa = sorted(usa)
                    for anterior, siguiente in zip(dias_usa, dias_usa[1:]):
                        if siguiente - anterior != 1:
                            continue
                        repite = self.modelo.NewBoolVar(
                            f"repite_{trabajador.id}_{anterior}_{puesto.value}")
                        self.modelo.Add(repite >= usa[anterior] + usa[siguiente] - 1)
                        terminos.append(pesos.rotacion_puestos * repite)
                    # (b) acaparar el puesto durante el mes
                    exceso = self.modelo.NewIntVar(
                        0, len(dias_usa), f"acapara_{trabajador.id}_{puesto.value}")
                    self.modelo.Add(exceso >= sum(usa.values()) - tope_puesto)
                    terminos.append(pesos.rotacion_puestos * exceso)

        # (7) Reparto del F1 de mañana en días laborables entre los jefes de equipo:
        # a partes iguales y, cuando el número no es par, el día de más para el jefe
        # de mayor prioridad (por ejemplo, Luis por encima de Fernando).
        jefes = sorted(
            [t for t in self.trabajadores if t.es_jefe_equipo],
            key=lambda t: (-t.prioridad_jefe, t.id),
        )
        if len(jefes) >= 2:
            laborables = [d for d in self.calendario.dias
                          if not self.calendario.es_festivo_o_finde(d)]
            conteo: dict[int, cp_model.IntVar] = {}
            for jefe in jefes:
                vars_f1 = [
                    self.x[(jefe.id, d, Turno.MANANA_TARDE, Puesto.F1)]
                    for d in laborables
                    if (jefe.id, d, Turno.MANANA_TARDE, Puesto.F1) in self.x
                ]
                c = self.modelo.NewIntVar(0, len(laborables) or 1, f"f1lab_{jefe.id}")
                self.modelo.Add(c == (sum(vars_f1) if vars_f1 else 0))
                conteo[jefe.id] = c
            # Para cada par (mayor prioridad, siguiente): el de mayor prioridad hace
            # más F1 que el otro. Con «f1_jefe_prioritario_estricto» la diferencia
            # mínima es de un día (si no, con un número par de laborables acababan
            # empatados); el margen máximo es de dos días para que no se dispare.
            minimo = 1 if self.config.f1_jefe_prioritario_estricto else 0
            for superior, inferior in zip(jefes, jefes[1:]):
                tope = len(laborables) or 1
                falta = self.modelo.NewIntVar(0, tope, f"f1_falta_{superior.id}")
                self.modelo.Add(
                    falta >= conteo[inferior.id] + minimo - conteo[superior.id])
                desbalance = self.modelo.NewIntVar(0, tope, f"f1_des_{superior.id}")
                self.modelo.Add(
                    desbalance >= conteo[superior.id] - conteo[inferior.id] - minimo - 1)
                terminos.append(PENALIZACION_REPARTO_F1 * (falta + desbalance))

        # (8) Procurar días libres agrupados con las vacaciones: para cada periodo
        # de vacaciones se intenta dejar libres los días inmediatamente anteriores
        # O los inmediatamente posteriores (basta con uno de los dos lados). Se
        # penaliza el «lado menos libre» (el mínimo de días trabajados a cada lado),
        # de modo que el motor tiende a dejar completamente libre al menos un lado.
        if self.config.vacaciones.procurar_descanso_alrededor and pesos.adaptacion_vacaciones > 0:
            v_antes = max(1, self.config.vacaciones.dias_libres_antes_min)
            v_despues = max(1, self.config.vacaciones.dias_libres_despues_min)
            for idx, ausencia in enumerate(self.ausencias):
                if ausencia.tipo is not TipoAusencia.VACACIONES:
                    continue
                if ausencia.trabajador_id not in self._mapa_trabajadores:
                    continue
                tid = ausencia.trabajador_id
                # Los días previos se cuentan hacia atrás desde el inicio de las
                # vacaciones AUNQUE ese inicio caiga en el mes siguiente: unas
                # vacaciones que arrancan el día 2 exigen dejar libre el final de
                # este mes. Se traduce la fecha a un número de día relativo a este
                # mes (0 o negativo si cae ya en el siguiente).
                inicio_rel = self._dia_relativo(ausencia.fecha_inicio)
                fin_rel = self._dia_relativo(ausencia.fecha_fin)
                antes_vars: list = []
                if inicio_rel is not None:
                    for k in range(1, v_antes + 1):
                        d = inicio_rel - k
                        if 1 <= d <= self.calendario.numero_dias:
                            antes_vars += self._variable_trabaja(tid, d)
                despues_vars: list = []
                if fin_rel is not None:
                    for k in range(1, v_despues + 1):
                        d = fin_rel + k
                        if 1 <= d <= self.calendario.numero_dias:
                            despues_vars += self._variable_trabaja(tid, d)
                # Si un lado cae entero fuera del mes, el otro deja de ser opcional:
                # se exige ese, en vez de darlo por bueno como antes.
                if not antes_vars and not despues_vars:
                    continue
                if not antes_vars or not despues_vars:
                    unico = antes_vars or despues_vars
                    n = self.modelo.NewIntVar(0, len(unico), f"vac_unico_{tid}_{idx}")
                    self.modelo.Add(n == sum(unico))
                    terminos.append(pesos.adaptacion_vacaciones * n)
                    continue
                na = self.modelo.NewIntVar(0, v_antes, f"vac_antes_{tid}_{idx}")
                self.modelo.Add(na == sum(antes_vars))
                nd = self.modelo.NewIntVar(0, v_despues, f"vac_despues_{tid}_{idx}")
                self.modelo.Add(nd == sum(despues_vars))
                lado_peor = self.modelo.NewIntVar(0, max(v_antes, v_despues), f"vac_peor_{tid}_{idx}")
                self.modelo.AddMinEquality(lado_peor, [na, nd])
                terminos.append(pesos.adaptacion_vacaciones * lado_peor)

        # (9) Maximizar los días trabajados de quien tenga «maximizar_dias»: se
        # recompensa cada turno suyo para que llene sus días disponibles, aunque
        # encadene muchos seguidos. Los topes de fines de semana y de noches siguen
        # vigentes, así que no hará más findes ni noches de los permitidos.
        for trabajador in self.trabajadores:
            if trabajador.maximizar_dias:
                terminos.append(-RECOMPENSA_MAXIMIZAR_DIAS * turnos_totales[trabajador.id])

        self.modelo.Minimize(sum(terminos))

    def _restriccion_descansos_agrupados(self) -> None:
        """Mínimo dos días libres seguidos (sin máximo).

        Prohíbe los días de descanso aislados (patrón trabajo-libre-trabajo) para
        que los descansos vayan en bloques de dos o más días. No hay límite superior
        de días libres. Se implementa con una variable de holgura muy penalizada, de
        modo que la regla se cumple siempre salvo imposibilidad operativa real.
        """
        works: dict[tuple[int, int], cp_model.IntVar] = {}
        for trabajador in self.trabajadores:
            for dia in self.calendario.dias:
                vars_dia = self._variable_trabaja(trabajador.id, dia)
                wb = self.modelo.NewBoolVar(f"works_{trabajador.id}_{dia}")
                self.modelo.Add(wb == (sum(vars_dia) if vars_dia else 0))
                works[(trabajador.id, dia)] = wb

        dias = self.calendario.dias
        for trabajador in self.trabajadores:
            # Quien trabaja el máximo de días no exige descanso mínimo agrupado.
            if trabajador.maximizar_dias:
                continue
            for i in range(1, len(dias) - 1):
                dia = dias[i]
                if not self._disponibilidad[(trabajador.id, dia)]:
                    continue
                # Prohíbe trabajar día anterior y siguiente descansando solo este,
                # salvo que la holgura lo permita (penalizada en el objetivo). Así la
                # regla se respeta siempre que sea posible, pero cede si es necesario
                # para cubrir el servicio, sin causar problemas.
                holgura = self.modelo.NewBoolVar(f"holgura_descanso_{trabajador.id}_{dia}")
                self.modelo.Add(
                    works[(trabajador.id, dias[i - 1])]
                    - works[(trabajador.id, dia)]
                    + works[(trabajador.id, dias[i + 1])] - holgura <= 1
                )
                self._slacks_descanso.append(holgura)

    # ------------------------------------------------------------------
    # Resolución
    # ------------------------------------------------------------------
    def resolver(self) -> ResultadoOptimizacion:
        """Construye el modelo completo, lo resuelve y devuelve el cuadrante."""
        self._crear_variables()
        self._restriccion_cobertura()
        self._restriccion_un_turno_por_dia()
        self._restriccion_noche_manana()
        self._restriccion_continuidad_mes_previo()
        self._restriccion_fines_semana()
        self._restriccion_puente_festivo()
        self._restriccion_finde_solo_noche()
        self._restriccion_jefes_finde_distinto()
        self._restriccion_noche_viernes()
        self._restriccion_consecutivos()
        self._restriccion_vacaciones()
        self._restriccion_descansos_agrupados()
        self._construir_objetivo()

        solucionador = cp_model.CpSolver()
        solucionador.parameters.max_time_in_seconds = float(self.config.tiempo_maximo_solver_segundos)
        # Un hilo por nucleo disponible: pedir mas hilos que nucleos los hace
        # competir entre si y empeora la convergencia.
        import os as _os
        solucionador.parameters.num_search_workers = max(1, min(8, _os.cpu_count() or 4))

        estado = solucionador.Solve(self.modelo)
        nombre_estado = solucionador.StatusName(estado)

        cuadrante = self._construir_cuadrante(solucionador, estado)
        sin_cubrir = self._detectar_sin_cubrir(solucionador, estado)

        if estado in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            valor = solucionador.ObjectiveValue()
            if estado == cp_model.FEASIBLE:
                cota = solucionador.BestObjectiveBound()
                self.mensajes.append(
                    f"Solucion no optima: valor {valor:.0f}, cota {cota:.0f}. "
                    "Con mas tiempo de solver el reparto puede mejorar.")
        else:
            valor = float("inf")
            self.mensajes.append(
                "El solucionador no encontró solución factible. Revise las restricciones."
            )

        return ResultadoOptimizacion(
            cuadrante=cuadrante,
            estado_solver=nombre_estado,
            puestos_sin_cubrir=sin_cubrir,
            valor_objetivo=valor,
            tiempo_segundos=solucionador.WallTime(),
            mensajes=self.mensajes,
        )

    def _construir_cuadrante(self, solucionador, estado) -> Cuadrante:
        cuadrante = Cuadrante(
            id=None,
            anio=self.anio,
            mes=self.mes,
            empresa=self.config.empresa,
            sede=self.config.sede,
            computo_mensual=self.config.computo_mensual_referencia,
            fecha_generacion=date.today(),
            trabajadores_ids=[t.id for t in self.trabajadores],
        )

        resuelto = estado in (cp_model.OPTIMAL, cp_model.FEASIBLE)
        for trabajador in self.trabajadores:
            for dia in self.calendario.dias:
                asignado = False
                if resuelto:
                    for (t, d, turno, puesto), var in self.x.items():
                        if t == trabajador.id and d == dia and solucionador.Value(var) == 1:
                            cuadrante.establecer(
                                Asignacion(trabajador.id, dia, turno=turno, puesto=puesto)
                            )
                            asignado = True
                            break
                if not asignado:
                    # Celda de ausencia o día libre.
                    ausencia = self._ausencia_del_dia(trabajador.id, dia)
                    cuadrante.establecer(
                        Asignacion(trabajador.id, dia, ausencia=ausencia)
                    )
        return cuadrante

    def _detectar_sin_cubrir(self, solucionador, estado) -> list[tuple[int, str, str]]:
        sin_cubrir: list[tuple[int, str, str]] = []
        if estado not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return sin_cubrir
        for (dia, turno, puesto), var in self.holgura.items():
            if solucionador.Value(var) == 1:
                sin_cubrir.append((dia, turno.value, puesto.value))
        return sin_cubrir
