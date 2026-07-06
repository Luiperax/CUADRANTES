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


@dataclass
class ParametrosVacaciones:
    """Parámetros de adaptación alrededor de las vacaciones."""

    dias_libres_antes_min: int = 2
    dias_libres_antes_max: int = 4
    dias_libres_despues_min: int = 2
    dias_libres_despues_max: int = 4
    evitar_noche_antes: bool = True
    evitar_noche_al_reincorporarse: bool = True


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
    rotacion_puestos: int = 30
    respetar_preferencias: int = 40
    agrupar_descansos: int = 25
    recuperacion_tras_noche: int = 35
    evitar_cambios_bruscos: int = 45
    adaptacion_vacaciones: int = 50
    tener_en_cuenta_historico: int = 60


@dataclass
class Configuracion:
    """Configuración global de reglas de negocio del generador de cuadrantes."""

    computo_mensual_referencia: float = 162.0
    empresa: str = "NATURGY"
    sede: str = "AV. SAN LUIS - 77"

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
        config.tiempo_maximo_solver_segundos = datos.get(
            "tiempo_maximo_solver_segundos", config.tiempo_maximo_solver_segundos
        )
        config.meses_historico_considerados = datos.get(
            "meses_historico_considerados", config.meses_historico_considerados
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
