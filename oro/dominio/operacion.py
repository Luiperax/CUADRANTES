"""Modelo de operación (trade) ejecutada o simulada.

Registra el ciclo de vida completo de una posición: apertura, gestión y cierre.
Es la unidad que se persiste para el aprendizaje continuo y el backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from .senal import Direccion


class EstadoOperacion(str, Enum):
    ABIERTA = "abierta"
    CERRADA_TP = "cerrada_tp"       # cerrada en beneficio.
    CERRADA_SL = "cerrada_sl"       # cerrada en pérdida (stop).
    CERRADA_MANUAL = "cerrada_manual"
    CANCELADA = "cancelada"


@dataclass(slots=True)
class Trade:
    """Una operación con su contexto, para auditoría y aprendizaje.

    El *contexto* (sesión, volatilidad, spread, noticias, estructura...) se guarda
    junto al resultado para que el modelo aprenda en qué condiciones acierta.
    """

    momento_apertura: datetime
    direccion: Direccion
    entrada: float
    stop_loss: float
    take_profit: float
    tamano: float
    riesgo_pct: float

    estado: EstadoOperacion = EstadoOperacion.ABIERTA
    momento_cierre: Optional[datetime] = None
    precio_cierre: Optional[float] = None
    resultado_r: Optional[float] = None   # resultado en múltiplos de R.
    pnl: Optional[float] = None           # beneficio/pérdida en la divisa de la cuenta.

    contexto: dict = field(default_factory=dict)

    @property
    def riesgo_por_unidad(self) -> float:
        return abs(self.entrada - self.stop_loss)

    def cerrar(self, momento: datetime, precio: float, estado: EstadoOperacion) -> None:
        """Cierra la operación y calcula su resultado en R y en PnL."""
        self.momento_cierre = momento
        self.precio_cierre = precio
        self.estado = estado
        riesgo = self.riesgo_por_unidad
        if riesgo <= 0:
            self.resultado_r = 0.0
        else:
            self.resultado_r = self.direccion.signo * (precio - self.entrada) / riesgo
        self.pnl = self.direccion.signo * (precio - self.entrada) * self.tamano

    @property
    def ganadora(self) -> bool:
        return (self.resultado_r or 0.0) > 0
