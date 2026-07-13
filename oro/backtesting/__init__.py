"""Backtesting event-driven y métricas de rendimiento.

Recorre el histórico vela a vela —sin mirar al futuro— generando señales con el
mismo motor que se usa en producción, simula la gestión de la operación (stops,
objetivos parciales, break-even) y calcula las métricas que exige un proceso de
validación serio: Profit Factor, Drawdown, Expectancy, Sharpe, Win Rate,
rachas, número de operaciones y rentabilidad anualizada.

Advertencia: un buen backtest es condición necesaria pero **no suficiente**.
Antes de operar en real hay que validar fuera de muestra (walk-forward, ver
:mod:`oro.ml`) y en cuenta demo durante meses.
"""

from __future__ import annotations

from .motor import Backtester, ResultadoBacktest
from .metricas import Metricas, calcular_metricas

__all__ = ["Backtester", "ResultadoBacktest", "Metricas", "calcular_metricas"]
