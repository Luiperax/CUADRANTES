"""Indicadores técnicos.

Filosofía del sistema: los indicadores son **confirmación**, nunca la decisión.
La decisión nace de la estructura de mercado y el contexto; los indicadores
solo suman o restan convicción.

Todas las funciones operan sobre :class:`pandas.Series`/:class:`pandas.DataFrame`
y devuelven series alineadas con el índice de entrada (con ``NaN`` en el periodo
de calentamiento), para poder encadenarlas sin fugas temporales.
"""

from __future__ import annotations

from .tecnicos import (
    adx,
    atr,
    bollinger,
    ema,
    macd,
    rsi,
    sma,
    vwap,
    calcular_todos,
)

__all__ = [
    "ema",
    "sma",
    "rsi",
    "atr",
    "macd",
    "adx",
    "bollinger",
    "vwap",
    "calcular_todos",
]
