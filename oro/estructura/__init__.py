"""Estructura de mercado y Smart Money Concepts (SMC).

Este es el *núcleo direccional* del sistema. A diferencia de los indicadores
(retrasados por naturaleza), la estructura describe lo que el precio está
haciendo realmente: máximos/mínimos, rupturas de estructura y zonas de interés
institucional.

Implementa, con reglas explícitas y auditables:

* Swings (máximos y mínimos relevantes) por fractales.
* BOS  (Break of Structure)     — continuación de tendencia.
* CHoCH (Change of Character)    — posible giro de tendencia.
* FVG  (Fair Value Gap)          — desequilibrios/ineficiencias de precio.
* Order Blocks                   — última vela contraria antes de un impulso.
* Liquidity sweeps               — barridos de liquidez sobre máx./mín. previos.
"""

from __future__ import annotations

from .analisis import (
    EstructuraMercado,
    FairValueGap,
    OrderBlock,
    Swing,
    analizar_estructura,
    detectar_swings,
)

__all__ = [
    "EstructuraMercado",
    "FairValueGap",
    "OrderBlock",
    "Swing",
    "analizar_estructura",
    "detectar_swings",
]
