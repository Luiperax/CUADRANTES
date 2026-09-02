"""
Gestión de la configuración de reglas de negocio.

Toda regla de planificación es parametrizable desde aquí (y, por extensión, desde
el panel de configuración de la interfaz gráfica). El objetivo es que el usuario
nunca tenga que modificar el código para cambiar una regla: pesos, límites y
activación/desactivación de restricciones se guardan como datos.

La configuración distingue dos tipos de reglas:

* **Restricciones duras (obligatorias):** el motor NUNCA las incumple salvo
  imposibilidad operativa (por ejemplo, cobertura de todos los puestos o las
  restricciones individuales de cada trabajador).
* **Objetivos blandos (preferencias):** se ponderan mediante «pesos» y el motor
  intenta satisfacerlos al máximo. Un peso mayor implica mayor prioridad.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass
class ParametrosDescanso:
    """Parámetros relativos a descansos y secuencias de trabajo."""

    max_dias_consecutivos: int = 6          # Máximo de días seguidos trabajando.
    max_noches_consecutivas: int = 4        # Evitar secuencias largas de noches.
    penalizar_noche_tras_manana: bool = True  # Evitar cambio brusco mañana->noche.
    dias_libres_tras_noches: int = 1        # Descanso recomendado tras bloque de noches.
    # Longitud mínima (en días) de un bloque de mañanas o de noches. Evita los
    # bloques de un solo día —una noche suelta entre mañanas, o al revés—, que
    # obligan a cambiar el horario de sueño para un único turno. Los días libres
    # cuentan dentro del bloque: lo que se mide es cuánto tiempo seguido se
    # mantiene el mismo horario, no cuántos turnos se hacen. Medido sobre octubre
    # con 10 vigilantes: con 3 quedaban 5 bloques de uno o dos turnos; con 5 solo
    # quedan 2, y además bajan los cambios de horario del mes (19 -> 15).
    dias_minimos_por_bloque: int = 5
    # Máximo de cambios de horario (mañana <-> noche) que puede sufrir un
    # trabajador dentro del mes. Con 1 el mes le queda partido en dos tramos: una
    # parte entera de noches y otra entera de mañanas, sin volver a tocarle el
    # ritmo de sueño. Con 0 no se limita (solo actúan los bloques mínimos). No
    # cuenta el enlace con el mes anterior, para no obligar a pasar el mes entero
    # en un único horario.
    max_cambios_dia_noche: int = 1


@dataclass
class ParametrosFinDeSemana:
    """Parámetros de reparto de fines de semana."""

    sabado_domingo_mismo_trabajador: bool = True  # S y D los hace la misma persona.
    fines_semana_objetivo_min: int = 1            # Mínimo preferente por trabajador.
    # Máximo preferente por trabajador. Por debajo del tope duro: se intenta que
    # nadie pase de aquí, y solo se supera si el servicio lo exige.
    fines_semana_objetivo_max: int = 2
    fines_semana_tope_duro: int = 3               # Nunca superar salvo necesidad.
    # Un turno de noche en viernes solo se permite si ese trabajador va a hacer el
    # fin de semana completo de noche (sábado y domingo noche). Evita noches sueltas
    # de viernes desligadas del fin de semana.
    noche_viernes_requiere_finde_completo: bool = True


@dataclass
class ParametrosVacaciones:
    """Parámetros de adaptación alrededor de las vacaciones."""

    dias_libres_antes_min: int = 2
    dias_libres_antes_max: int = 4
    dias_libres_despues_min: int = 2
    dias_libres_despues_max: int = 4
    evitar_noche_antes: bool = True
    evitar_noche_al_reincorporarse: bool = True
    # Procurar (objetivo blando) que haya varios días libres justo antes O justo
    # después del periodo de vacaciones, para que el descanso quede agrupado con
    # las vacaciones. El tamaño de la «ventana» a cada lado son los días mínimos
    # de arriba (por defecto 2). Se cumple en al menos uno de los dos lados.
    procurar_descanso_alrededor: bool = True


@dataclass
class PesosObjetivos:
    """Pesos de los objetivos blandos de la optimización multiobjetivo.

    Cuanto mayor es el valor, más prioridad tiene ese objetivo al resolver
    empates entre soluciones válidas. Ajustables desde el panel de configuración.
    """

    equilibrio_horas: int = 100
    # Desviación de CADA trabajador respecto al reparto medio de horas. El peso
    # «equilibrio_horas» solo mide el rango (máximo menos mínimo), que no aprieta a
    # quien queda en medio; este reparte de verdad. Se mide POR HORA de desviación
    # y por persona, así que un valor alto rompería los bloques de mañana/noche
    # (que cuestan 5000): con 90, corregir una jornada de 12 h vale 1080.
    equilibrio_horas_extra: int = 90
    # Reparto de noches. Debe pesar en el mismo orden que la agrupacion de
    # bloques dia/noche: si se queda muy por debajo, el motor agrupa metiendo
    # todas las noches del mes a una sola persona.
    equilibrio_noches: int = 500
    # Penalización por cada hora en que quien tiene «absorbe_exceso» queda POR
    # DEBAJO de un compañero. Es lo que hace que el sobrante del reparto recaiga
    # siempre en quien se ha ofrecido a asumirlo. Se mide por hora y por pareja de
    # trabajadores, así que basta un valor moderado para que domine.
    absorber_exceso: int = 300
    # Penalización por cada día que un trabajador encadena por encima de su límite
    # personal («max_dias_seguidos_preferido»), que es más estricto que el máximo
    # general del convenio. Objetivo blando: cede ante la cobertura del servicio.
    limite_dias_seguidos_individual: int = 700
    # Reparto de fines de semana, equilibrado a lo largo del AÑO (histórico +
    # mes en curso), no mes a mes. Con 80 no llegaba a competir con el resto de
    # objetivos y el desequilibrio anual no se corregía nunca.
    equilibrio_fines_semana: int = 400
    # Equilibrio ANUAL de festivos: reparte los festivos trabajados de forma pareja
    # entre trabajadores teniendo en cuenta el histórico (festivos ya trabajados).
    # Pesa mucho mas que el resto porque en todo el año solo hay 14 festivos: cada
    # uno cuenta muchisimo en la equidad, mientras que el equilibrio de horas se
    # mide POR HORA. Con 85 el motor daba el festivo a quien ya llevaba 3 con tal
    # de cuadrar unas horas, teniendo libre a quien llevaba 1.
    # Con 1500 el motor seguia dando el festivo a alguien con tres a cuestas
    # teniendo libres a companeros con uno, porque otros objetivos del mes
    # (horas, bloques, fines de semana) sumaban mas que la diferencia.
    equilibrio_festivos: int = 4000
    # Cumplimiento del objetivo individual de fines de semana (p. ej. Luis y
    # Fernando, jefes de equipo: exactamente uno al mes). Peso muy alto para que
    # domine con claridad al resto de objetivos blandos (incluida la compensación
    # histórica) y solo ceda ante la cobertura del servicio. Es, en la práctica,
    # una condición casi obligatoria que solo se incumple por imposibilidad real.
    objetivo_finde_individual: int = 20000
    # Penalización por cada fin de semana por encima del máximo preferente
    # («fines_semana_objetivo_max»). El ajuste existía en la configuración y en el
    # panel, pero el motor solo miraba el tope duro, así que el «máximo 2» no se
    # aplicaba nunca y salía gente con tres.
    exceso_fines_semana: int = 1500
    # Penalización por encadenar el último fin de semana de un mes con el primero
    # del siguiente. Sin esto, el reparto se calcula mes a mes y alguien puede
    # cerrar octubre trabajando y abrir noviembre igual, dos seguidos de hecho.
    findes_encadenados: int = 1500
    # Rotación de puestos. Penaliza encadenar el mismo puesto día tras día y
    # acaparar un puesto durante el mes. Estaba declarado pero el motor no lo
    # usaba, así que el reparto de puestos salía por casualidad: había quien
    # hacía nueve F1 seguidos y luego diez F2 seguidos sin pisar MO ni EX.
    rotacion_puestos: int = 250
    respetar_preferencias: int = 40
    # Reservado: los descansos agrupados (mínimo dos días libres seguidos, sin
    # máximo) se aplican como restricción del motor, no como peso.
    agrupar_descansos: int = 70
    recuperacion_tras_noche: int = 35
    evitar_cambios_bruscos: int = 45
    # Agrupar el mes en bloques: una parte de turnos de dia y otra de noche, en
    # lugar de ir alternando mañana/noche constantemente. Penaliza cada cambio de
    # "fase" (dia <-> noche) a lo largo del mes. Es un objetivo blando: cede ante
    # la cobertura del servicio, pero debe pesar bastante mas que el equilibrio de
    # horas (que se cuenta POR HORA de desviacion), o el motor parte los bloques
    # para cuadrar unas pocas horas. Pero tampoco debe aplastar al reparto de
    # noches. Medido sobre el mismo mes: 120 -> 18 cambios; 1200 -> 13 cambios
    # pero una persona con 17 noches; 800 (con equilibrio_noches=500) -> 12
    # cambios y ninguna por encima de 9 noches.
    agrupar_dia_noche: int = 800
    # Penalización por cada día que le falta a un bloque para llegar al mínimo
    # («dias_minimos_por_bloque»). Complementa a «agrupar_dia_noche»: aquel reduce
    # el NÚMERO de cambios de horario y este cuida que cada bloque sea lo bastante
    # largo, que es lo que de verdad evita el vaivén de horas de sueño. Debe pesar
    # más que el equilibrio de horas (que se cuenta POR HORA: mover un turno son
    # 12 h = 1200) para que el motor no rompa un bloque por cuadrar unas horas.
    bloques_minimos: int = 2000
    # Penalización por cada cambio de horario que un trabajador tenga POR ENCIMA
    # de «max_cambios_dia_noche». Es lo que fuerza el mes partido en dos tramos.
    # Se deja como objetivo blando —no como restricción dura— para que el motor
    # pueda saltárselo antes que dejar un puesto sin cubrir. Debe pesar más que el
    # reparto de noches (2500), o el motor troceará los bloques para cuadrarlas.
    limite_cambios_fase: int = 5000
    # Procurar días libres agrupados justo antes o después de las vacaciones.
    # Objetivo blando: se intenta, pero cede ante la cobertura del servicio. Debe
    # pesar MÁS que mover un turno de sitio (12 h x «equilibrio_horas» = 1200), o
    # al motor le sale barato romper el descanso previo a unas vacaciones con tal
    # de cuadrar unas horas: con 600 dejaba a quien empezaba vacaciones el día 2
    # trabajando la víspera.
    adaptacion_vacaciones: int = 2500
    # Compensación histórica de HORAS y NOCHES entre meses. A 0, cada mes se
    # equilibra por sí mismo (todos con ~las mismas horas extra), sin arrastrar el
    # desequilibrio de meses anteriores. Los FESTIVOS se equilibran aparte, de
    # forma ANUAL (ver «equilibrio_festivos»), y NO se ven afectados por esto.
    tener_en_cuenta_historico: int = 0


@dataclass
class Configuracion:
    """Configuración global de reglas de negocio del generador de cuadrantes."""

    computo_mensual_referencia: float = 162.0
    empresa: str = "NATURGY"
    sede: str = "AV. SAN LUIS - 77"

    # Ubicación para el calendario de festivos (varían por comunidad y municipio).
    comunidad_autonoma: str = "Madrid"
    municipio: str = "Madrid"

    # Reserva del puesto F1 de mañana (MT-F1) a los jefes de equipo en días
    # laborables. En fin de semana o festivo ese puesto lo puede hacer cualquiera.
    # Turnos como máximo en el MISMO puesto a lo largo del mes antes de empezar a
    # penalizar. Con 17-19 turnos al mes, 7 reparte entre dos o tres puestos.
    max_turnos_mismo_puesto: int = 7

    reservar_f1_manana_a_jefes: bool = True

    # El jefe de equipo con MAYOR «prioridad_jefe» hace ESTRICTAMENTE más F1 de
    # mañana que el otro, no solo el día suelto cuando el reparto es impar (que es
    # lo que ocurría antes: con un número par de laborables acababan empatados).
    f1_jefe_prioritario_estricto: bool = True

    # Horas de cómputo que aporta cada día de ausencia computable (vacaciones,
    # permiso retribuido, formación). Reduce el cómputo mensual del trabajador para
    # que las horas extra se calculen correctamente, como en los cuadrantes reales.
    horas_computo_por_dia_ausencia: float = 5.34

    descanso: ParametrosDescanso = field(default_factory=ParametrosDescanso)
    fin_de_semana: ParametrosFinDeSemana = field(default_factory=ParametrosFinDeSemana)
    vacaciones: ParametrosVacaciones = field(default_factory=ParametrosVacaciones)
    pesos: PesosObjetivos = field(default_factory=PesosObjetivos)

    # Límite de tiempo (segundos) para el solver de optimización.
    tiempo_maximo_solver_segundos: int = 30
    # Peso del histórico: cuántos meses previos se tienen en cuenta para el reparto.
    meses_historico_considerados: int = 12

    # ------------------------------------------------------------------
    # Serialización a/desde JSON (se almacena en la tabla de configuración)
    # ------------------------------------------------------------------
    def a_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def desde_json(cls, texto: str) -> "Configuracion":
        datos = json.loads(texto)
        return cls.desde_diccionario(datos)

    @classmethod
    def desde_diccionario(cls, datos: dict) -> "Configuracion":
        """Reconstruye la configuración tolerando claves ausentes (compatibilidad)."""
        config = cls()
        config.computo_mensual_referencia = datos.get(
            "computo_mensual_referencia", config.computo_mensual_referencia
        )
        config.empresa = datos.get("empresa", config.empresa)
        config.sede = datos.get("sede", config.sede)
        config.comunidad_autonoma = datos.get("comunidad_autonoma", config.comunidad_autonoma)
        config.municipio = datos.get("municipio", config.municipio)
        config.tiempo_maximo_solver_segundos = datos.get(
            "tiempo_maximo_solver_segundos", config.tiempo_maximo_solver_segundos
        )
        config.meses_historico_considerados = datos.get(
            "meses_historico_considerados", config.meses_historico_considerados
        )
        config.reservar_f1_manana_a_jefes = datos.get(
            "reservar_f1_manana_a_jefes", config.reservar_f1_manana_a_jefes
        )
        config.horas_computo_por_dia_ausencia = datos.get(
            "horas_computo_por_dia_ausencia", config.horas_computo_por_dia_ausencia
        )
        if "descanso" in datos:
            config.descanso = ParametrosDescanso(**datos["descanso"])
        if "fin_de_semana" in datos:
            config.fin_de_semana = ParametrosFinDeSemana(**datos["fin_de_semana"])
        if "vacaciones" in datos:
            config.vacaciones = ParametrosVacaciones(**datos["vacaciones"])
        if "pesos" in datos:
            config.pesos = PesosObjetivos(**datos["pesos"])
        return config
