"""
Sistema de validación y auditoría del cuadrante.

Estas comprobaciones NO son un simple informe: forman parte del algoritmo. El
programa no puede entregar un cuadrante como VALIDADO hasta verificarlas todas.
Cuando alguna regla no puede cumplirse, la auditoría:

* la detecta automáticamente,
* explica el motivo,
* identifica a los trabajadores afectados,
* propone la alternativa más equilibrada posible,
* y marca el cuadrante como «Generado con incidencias justificadas».
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..config.configuracion import Configuracion
from ..config.constantes import EstadoCuadrante, Turno
from ..datos.modelos import Ausencia, Cuadrante, Trabajador
from ..dominio.calendario import CalendarioMes
from ..dominio.computos import calcular_resumenes


class EstadoRegla(str, Enum):
    CUMPLE = "Cumple"
    NO_CUMPLE = "No cumple"
    ADVERTENCIA = "Advertencia"


@dataclass
class ResultadoRegla:
    """Resultado de la comprobación de una regla de la auditoría."""

    nombre: str
    estado: EstadoRegla
    motivo: str = ""
    solucion_propuesta: str = ""
    trabajadores_afectados: list[str] = field(default_factory=list)

    @property
    def es_bloqueante(self) -> bool:
        return self.estado is EstadoRegla.NO_CUMPLE


@dataclass
class InformeAuditoria:
    """Informe completo de la auditoría de un cuadrante."""

    reglas: list[ResultadoRegla] = field(default_factory=list)
    estado_cuadrante: EstadoCuadrante = EstadoCuadrante.BORRADOR

    @property
    def es_valido(self) -> bool:
        return all(r.estado is not EstadoRegla.NO_CUMPLE for r in self.reglas)

    @property
    def incidencias(self) -> list[ResultadoRegla]:
        return [r for r in self.reglas if r.estado is not EstadoRegla.CUMPLE]


class Auditor:
    """Ejecuta la batería completa de comprobaciones sobre un cuadrante."""

    def __init__(
        self,
        cuadrante: Cuadrante,
        trabajadores: dict[int, Trabajador],
        configuracion: Configuracion,
        ausencias: list[Ausencia] | None = None,
    ):
        self.cuadrante = cuadrante
        self.trabajadores = trabajadores
        self.config = configuracion
        self.ausencias = ausencias or []
        self.calendario = CalendarioMes(cuadrante.anio, cuadrante.mes)
        self.resumenes = calcular_resumenes(cuadrante, trabajadores, self.calendario)

    def _nombre(self, trabajador_id: int) -> str:
        t = self.trabajadores.get(trabajador_id)
        return t.nombre if t else f"Trabajador {trabajador_id}"

    # ------------------------------------------------------------------
    # Reglas individuales de la auditoría
    # ------------------------------------------------------------------
    def _regla_cobertura(self) -> ResultadoRegla:
        sin_cubrir: list[str] = []
        for dia in self.calendario.dias:
            festivo_finde = self.calendario.es_festivo_o_finde(dia)
            from ..config.constantes import turnos_puesto_requeridos

            for turno, puesto in turnos_puesto_requeridos(festivo_finde):
                cubierto = any(
                    a.es_trabajo and a.turno == turno and a.puesto == puesto
                    for (t, d), a in self.cuadrante.asignaciones.items() if d == dia
                )
                if not cubierto:
                    sin_cubrir.append(f"día {dia} {turno.value}-{puesto.value}")
        if sin_cubrir:
            return ResultadoRegla(
                "Cobertura del servicio", EstadoRegla.NO_CUMPLE,
                motivo="Existen puestos sin cubrir: " + "; ".join(sin_cubrir[:10]),
                solucion_propuesta=(
                    "Incorporar personal de refuerzo o reasignar turnos de trabajadores "
                    "con menor carga los días afectados."),
            )
        return ResultadoRegla("Cobertura del servicio", EstadoRegla.CUMPLE,
                              motivo="Todos los puestos están cubiertos.")

    def _regla_restricciones_individuales(self) -> ResultadoRegla:
        infracciones: list[str] = []
        afectados: set[str] = set()
        for (trabajador_id, dia), asignacion in self.cuadrante.asignaciones.items():
            if not asignacion.es_trabajo:
                continue
            trabajador = self.trabajadores.get(trabajador_id)
            if trabajador and not trabajador.puede_realizar(asignacion.turno, asignacion.puesto):
                infracciones.append(
                    f"{trabajador.nombre} en {asignacion.turno.value}-{asignacion.puesto.value} (día {dia})")
                afectados.add(trabajador.nombre)
        if infracciones:
            return ResultadoRegla(
                "Restricciones individuales", EstadoRegla.NO_CUMPLE,
                motivo="; ".join(infracciones[:8]),
                solucion_propuesta="Reasignar esos turnos a trabajadores habilitados para el puesto.",
                trabajadores_afectados=sorted(afectados),
            )
        return ResultadoRegla("Restricciones individuales", EstadoRegla.CUMPLE,
                              motivo="Se respetan todas las restricciones individuales.")

    def _regla_equilibrio(
        self, atributo: str, nombre: str, tolerancia: float, solo_nocturnos: bool = False
    ) -> ResultadoRegla:
        """Comprueba el equilibrio de una magnitud entre los trabajadores activos.

        :param solo_nocturnos: si es ``True`` solo se consideran trabajadores
            habilitados para hacer noches (evita penalizar el reparto por quienes
            tienen prohibido el turno nocturno, como Luis o Fernando).
        """
        valores = {
            tid: getattr(r, atributo)
            for tid, r in self.resumenes.items()
            if self.trabajadores.get(tid) and self._participa(tid)
            and (not solo_nocturnos or self.trabajadores[tid].puede_hacer_noches)
        }
        if not valores:
            return ResultadoRegla(nombre, EstadoRegla.CUMPLE)
        maximo = max(valores.values())
        minimo = min(valores.values())
        rango = maximo - minimo
        if rango > tolerancia:
            afectados = [self._nombre(tid) for tid, v in valores.items() if v in (maximo, minimo)]
            return ResultadoRegla(
                nombre, EstadoRegla.ADVERTENCIA,
                motivo=f"Diferencia de {rango:.0f} entre el máximo ({maximo:.0f}) y el mínimo ({minimo:.0f}).",
                solucion_propuesta="Ajustar el reparto en el próximo mes usando la memoria histórica.",
                trabajadores_afectados=afectados,
            )
        return ResultadoRegla(nombre, EstadoRegla.CUMPLE,
                              motivo=f"Reparto equilibrado (rango {rango:.0f}).")

    def _participa(self, trabajador_id: int) -> bool:
        """Un trabajador participa si tiene al menos un turno o no está de baja todo el mes."""
        resumen = self.resumenes.get(trabajador_id)
        return bool(resumen and resumen.dias_trabajados > 0)

    def _regla_fines_semana(self) -> ResultadoRegla:
        infracciones: list[str] = []
        afectados: set[str] = set()
        tope = self.config.fin_de_semana.fines_semana_tope_duro
        for tid, resumen in self.resumenes.items():
            if resumen.numero_fines_semana > tope:
                infracciones.append(
                    f"{self._nombre(tid)} realiza {resumen.numero_fines_semana} fines de semana")
                afectados.add(self._nombre(tid))
        # Comprobación de emparejamiento sábado-domingo.
        for sabado, domingo in self.calendario.fines_de_semana():
            for tid in self.resumenes:
                sab = self.cuadrante.obtener(tid, sabado)
                dom = self.cuadrante.obtener(tid, domingo)
                trabaja_sab = bool(sab and sab.es_trabajo)
                trabaja_dom = bool(dom and dom.es_trabajo)
                if trabaja_sab != trabaja_dom:
                    infracciones.append(
                        f"{self._nombre(tid)} no realiza sábado y domingo juntos ({sabado}/{domingo})")
                    afectados.add(self._nombre(tid))
        if infracciones:
            return ResultadoRegla(
                "Fines de semana", EstadoRegla.ADVERTENCIA,
                motivo="; ".join(infracciones[:6]),
                solucion_propuesta="Reequilibrar los fines de semana priorizando a quien menos ha realizado.",
                trabajadores_afectados=sorted(afectados),
            )
        return ResultadoRegla("Fines de semana", EstadoRegla.CUMPLE,
                              motivo="Fines de semana equilibrados y emparejados correctamente.")

    def _regla_descansos(self) -> ResultadoRegla:
        max_dias = self.config.descanso.max_dias_consecutivos
        infracciones: list[str] = []
        afectados: set[str] = set()
        for tid in self.resumenes:
            consecutivos = 0
            maximo_racha = 0
            for dia in self.calendario.dias:
                asignacion = self.cuadrante.obtener(tid, dia)
                if asignacion and asignacion.es_trabajo:
                    consecutivos += 1
                    maximo_racha = max(maximo_racha, consecutivos)
                else:
                    consecutivos = 0
            if maximo_racha > max_dias:
                infracciones.append(f"{self._nombre(tid)} ({maximo_racha} días seguidos)")
                afectados.add(self._nombre(tid))
        if infracciones:
            return ResultadoRegla(
                "Descansos", EstadoRegla.ADVERTENCIA,
                motivo="Rachas superiores al máximo de " + str(max_dias) + " días: " + "; ".join(infracciones[:6]),
                solucion_propuesta="Intercalar un día de descanso en las rachas señaladas.",
                trabajadores_afectados=sorted(afectados),
            )
        return ResultadoRegla("Descansos", EstadoRegla.CUMPLE,
                              motivo="Se respetan los descansos legales y no hay rachas excesivas.")

    def _regla_cambios_turno(self) -> ResultadoRegla:
        infracciones: list[str] = []
        afectados: set[str] = set()
        for tid in self.resumenes:
            for dia in self.calendario.dias[:-1]:
                hoy = self.cuadrante.obtener(tid, dia)
                manana = self.cuadrante.obtener(tid, dia + 1)
                if (hoy and hoy.es_noche and manana and manana.es_trabajo
                        and manana.turno is Turno.MANANA_TARDE):
                    infracciones.append(f"{self._nombre(tid)} (noche día {dia} -> mañana día {dia+1})")
                    afectados.add(self._nombre(tid))
        if infracciones:
            return ResultadoRegla(
                "Cambios de turno", EstadoRegla.NO_CUMPLE,
                motivo="Cambios bruscos noche->mañana: " + "; ".join(infracciones[:6]),
                solucion_propuesta="Insertar un descanso tras la noche antes de asignar una jornada diurna.",
                trabajadores_afectados=sorted(afectados),
            )
        return ResultadoRegla("Cambios de turno", EstadoRegla.CUMPLE,
                              motivo="No hay cambios bruscos entre noches y mañanas.")

    def _regla_vacaciones(self) -> ResultadoRegla:
        from ..config.constantes import TipoAusencia

        infracciones: list[str] = []
        afectados: set[str] = set()
        for ausencia in self.ausencias:
            if ausencia.tipo is not TipoAusencia.VACACIONES:
                continue
            nombre = self._nombre(ausencia.trabajador_id)
            # Noche justo antes de vacaciones.
            if ausencia.fecha_inicio.month == self.cuadrante.mes:
                dia_antes = ausencia.fecha_inicio.day - 1
                asig = self.cuadrante.obtener(ausencia.trabajador_id, dia_antes)
                if asig and asig.es_noche:
                    infracciones.append(f"{nombre} tiene noche antes de vacaciones (día {dia_antes})")
                    afectados.add(nombre)
            # Noche al reincorporarse.
            if ausencia.fecha_fin.month == self.cuadrante.mes:
                dia_despues = ausencia.fecha_fin.day + 1
                asig = self.cuadrante.obtener(ausencia.trabajador_id, dia_despues)
                if asig and asig.es_noche:
                    infracciones.append(f"{nombre} se reincorpora directamente a noche (día {dia_despues})")
                    afectados.add(nombre)
        if infracciones:
            return ResultadoRegla(
                "Vacaciones y adaptación", EstadoRegla.ADVERTENCIA,
                motivo="; ".join(infracciones[:6]),
                solucion_propuesta="Sustituir esas noches por jornadas diurnas o días de descanso.",
                trabajadores_afectados=sorted(afectados),
            )
        return ResultadoRegla("Vacaciones y adaptación", EstadoRegla.CUMPLE,
                              motivo="Se respetan los periodos de adaptación de las vacaciones.")

    def _regla_rotacion(self) -> ResultadoRegla:
        # Comprobación ligera: que ningún trabajador polivalente repita siempre el mismo puesto.
        monotonos: list[str] = []
        for tid in self.resumenes:
            trabajador = self.trabajadores.get(tid)
            if not trabajador or len(trabajador.puestos_diurnos_permitidos) <= 1:
                continue
            puestos = {
                a.codigo_puesto()
                for (t, _), a in self.cuadrante.asignaciones.items()
                if t == tid and a.es_trabajo
            }
            if len(puestos) == 1 and self.resumenes[tid].dias_trabajados > 5:
                monotonos.append(self._nombre(tid))
        if monotonos:
            return ResultadoRegla(
                "Rotación de puestos", EstadoRegla.ADVERTENCIA,
                motivo="Trabajadores sin rotación de puesto: " + ", ".join(monotonos),
                solucion_propuesta="Alternar los puestos F1/F2/MO/EX a lo largo del mes.",
                trabajadores_afectados=monotonos,
            )
        return ResultadoRegla("Rotación de puestos", EstadoRegla.CUMPLE,
                              motivo="La rotación de puestos es adecuada.")

    # ------------------------------------------------------------------
    # Auditoría completa
    # ------------------------------------------------------------------
    def auditar(self) -> InformeAuditoria:
        """Ejecuta todas las reglas y determina el estado final del cuadrante."""
        reglas = [
            self._regla_cobertura(),
            self._regla_restricciones_individuales(),
            self._regla_equilibrio("horas_trabajadas", "Horas ordinarias", tolerancia=24),
            self._regla_equilibrio("horas_extra", "Horas extraordinarias", tolerancia=24),
            self._regla_equilibrio("numero_noches", "Noches", tolerancia=3, solo_nocturnos=True),
            self._regla_fines_semana(),
            self._regla_descansos(),
            self._regla_vacaciones(),
            self._regla_rotacion(),
            self._regla_cambios_turno(),
        ]

        informe = InformeAuditoria(reglas=reglas)
        # Determinación del estado final del cuadrante.
        if not informe.es_valido:
            informe.estado_cuadrante = EstadoCuadrante.GENERADO_CON_INCIDENCIAS
        elif informe.incidencias:
            # Solo advertencias -> se considera generado con incidencias justificadas.
            informe.estado_cuadrante = EstadoCuadrante.GENERADO_CON_INCIDENCIAS
        else:
            informe.estado_cuadrante = EstadoCuadrante.VALIDADO
        return informe
