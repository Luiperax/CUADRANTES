"""Modelos de dominio del sistema de trading de XAU/USD.

Son estructuras de datos *puras* (sin dependencias de librerías externas de
cálculo ni de red) para que el resto del sistema dependa de ellas y no al revés.
"""

from __future__ import annotations

from .mercado import Candle, MarketSnapshot, Sesion, sesion_de
from .senal import Direccion, Signal, TakeProfit
from .operacion import EstadoOperacion, Trade

__all__ = [
    "Candle",
    "MarketSnapshot",
    "Sesion",
    "sesion_de",
    "Direccion",
    "Signal",
    "TakeProfit",
    "EstadoOperacion",
    "Trade",
]
