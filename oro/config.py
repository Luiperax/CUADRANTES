"""Configuración central del sistema de trading de XAU/USD.

Todos los parámetros sensibles (riesgo, umbrales de calidad, límites de
operación) están aquí y pueden ajustarse sin tocar la lógica. Los valores por
defecto son conservadores a propósito: la prioridad es proteger el capital.

Se pueden sobreescribir mediante variables de entorno con prefijo ``ORO_``
(p. ej. ``ORO_RIESGO_POR_OPERACION=0.005``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from typing import List


@dataclass(slots=True)
class ConfiguracionRiesgo:
    riesgo_por_operacion: float = 0.005   # 0.5 % del capital por operación.
    riesgo_diario_max: float = 0.02       # tope de riesgo/pérdida diaria (2 %).
    operaciones_max_dia: int = 4          # 2–4 oportunidades A+ al día.
    operaciones_min_dia: int = 0          # nunca se fuerza: puede ser 0.
    r_recompensa_min: float = 1.5         # R:R medio ponderado mínimo aceptable.
    atr_stop_mult: float = 1.5            # stop = 1.5 x ATR desde la entrada.
    # Reparto de la posición entre objetivos parciales (TP1, TP2, TP3).
    reparto_tp: tuple = (0.5, 0.3, 0.2)
    r_objetivos: tuple = (1.0, 2.0, 3.0)  # cada TP en múltiplos de R.


@dataclass(slots=True)
class ConfiguracionCalidad:
    """Umbrales del filtro de calidad A+. Solo se emite señal si se superan."""

    prob_minima: float = 0.58        # probabilidad estimada mínima.
    confianza_minima: float = 0.6    # convicción/confluencia mínima.
    puntuacion_minima: float = 0.65  # puntuación de confluencia normalizada.
    spread_max: float = 0.6          # spread máximo tolerado (USD/oz).
    atr_min: float = 0.8             # por debajo: mercado demasiado plano.
    atr_max: float = 12.0            # por encima: volatilidad extrema, no operar.
    adx_lateral: float = 18.0        # ADX por debajo => mercado lateral.


@dataclass(slots=True)
class ConfiguracionSistema:
    simbolo: str = "XAUUSD"
    capital: float = 10_000.0            # capital de la cuenta (divisa base).
    timeframe: str = "M15"               # marco temporal de trabajo.
    zona_horaria: str = "UTC"

    riesgo: ConfiguracionRiesgo = field(default_factory=ConfiguracionRiesgo)
    calidad: ConfiguracionCalidad = field(default_factory=ConfiguracionCalidad)

    # Fuentes de datos y ML (rutas relativas al directorio de datos).
    directorio_datos: str = "datos_oro"
    ruta_modelo: str = "datos_oro/modelo.pkl"
    ruta_operaciones: str = "datos_oro/operaciones.jsonl"

    def validar(self) -> List[str]:
        """Devuelve una lista de problemas de configuración (vacía si todo OK)."""
        problemas: List[str] = []
        r = self.riesgo
        if not 0 < r.riesgo_por_operacion <= 0.05:
            problemas.append("riesgo_por_operacion debe estar en (0, 0.05].")
        if r.riesgo_diario_max < r.riesgo_por_operacion:
            problemas.append("riesgo_diario_max no puede ser menor que el de una operación.")
        if abs(sum(r.reparto_tp) - 1.0) > 1e-6:
            problemas.append("reparto_tp debe sumar 1.0.")
        if len(r.reparto_tp) != len(r.r_objetivos):
            problemas.append("reparto_tp y r_objetivos deben tener la misma longitud.")
        if r.r_recompensa_min <= 0:
            problemas.append("r_recompensa_min debe ser positivo.")
        return problemas


def cargar_configuracion() -> ConfiguracionSistema:
    """Crea la configuración aplicando sobreescrituras desde el entorno.

    Solo se sobreescriben los campos escalares de primer nivel y los del bloque
    de riesgo/calidad más habituales, que es lo que se ajusta en producción.
    """
    cfg = ConfiguracionSistema()

    def _num(nombre: str, actual: float) -> float:
        bruto = os.getenv(nombre)
        if bruto is None:
            return actual
        try:
            return type(actual)(bruto)
        except (TypeError, ValueError):
            return actual

    cfg.capital = _num("ORO_CAPITAL", cfg.capital)
    cfg.simbolo = os.getenv("ORO_SIMBOLO", cfg.simbolo)
    cfg.riesgo.riesgo_por_operacion = _num(
        "ORO_RIESGO_POR_OPERACION", cfg.riesgo.riesgo_por_operacion
    )
    cfg.riesgo.operaciones_max_dia = int(
        _num("ORO_OPERACIONES_MAX_DIA", cfg.riesgo.operaciones_max_dia)
    )
    cfg.calidad.prob_minima = _num("ORO_PROB_MINIMA", cfg.calidad.prob_minima)
    return cfg


__all__ = [
    "ConfiguracionRiesgo",
    "ConfiguracionCalidad",
    "ConfiguracionSistema",
    "cargar_configuracion",
]
