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


@dataclass
class ParametrosFinDeSemana:
    """Parámetros de reparto de fines de semana."""

    sabado_domingo_mismo_trabajador: bool = True  # S y D los hace la misma persona.
    fines_semana_objetivo_min: int = 1            # Mínimo preferente por trabajador.
    fines_semana_objetivo_max: int = 2            # Máximo preferente por trabajador.
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
    equilibrio_horas_extra: int = 90
    equilibrio_noches: int = 80
    equilibrio_fines_semana: int = 80
    # Equilibrio ANUAL de festivos: reparte los festivos trabajados de forma pareja
    # entre trabajadores teniendo en cuenta el histórico (festivos ya trabajados).
    equilibrio_festivos: int = 85
    # Cumplimiento del objetivo individual de fines de semana (p. ej. Luis y
    # Fernando, jefes de equipo: exactamente uno al mes). Peso muy alto para que
    # domine con claridad al resto de objetivos blandos (incluida la compensación
    # histórica) y solo ceda ante la cobertura del servicio. Es, en la práctica,
    # una condición casi obligatoria que solo se incumple por imposibilidad real.
    objetivo_finde_individual: int = 20000
    rotacion_puestos: int = 30
    respetar_preferencias: int = 40
    # Reservado: los descansos agrupados (mínimo dos días libres seguidos, sin
    # máximo) se aplican como restricción del motor, no como peso.
    agrupar_descansos: int = 70
    recuperacion_tras_noche: int = 35
    evitar_cambios_bruscos: int = 45
    # Procurar días libres agrupados justo antes o después de las vacaciones.
    # Objetivo blando: se intenta, pero cede ante la cobertura y el equilibrio de
    # horas si hiciera falta.
    adaptacion_vacaciones: int = 600
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
    reservar_f1_manana_a_jefes: bool = True

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
