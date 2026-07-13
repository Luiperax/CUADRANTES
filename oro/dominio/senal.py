"""Modelo de señal de trading.

Una :class:`Signal` es el producto final del sistema: una oportunidad concreta,
accionable y *explicada*, con todos los niveles de gestión ya calculados. El
sistema solo emite señales que superan el filtro de calidad A+; en caso
contrario, no emite nada (ver :mod:`oro.senales`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List


class Direccion(str, Enum):
    COMPRA = "compra"
    VENTA = "venta"

    @property
    def signo(self) -> int:
        return 1 if self is Direccion.COMPRA else -1


@dataclass(frozen=True, slots=True)
class TakeProfit:
    """Objetivo parcial de beneficio con la fracción de la posición a cerrar."""

    precio: float
    fraccion: float  # 0..1 de la posición a cerrar en este nivel.
    r_multiple: float  # beneficio en múltiplos de riesgo (R) si se alcanza.


@dataclass(frozen=True, slots=True)
class Signal:
    """Oportunidad de trading completamente especificada.

    ``probabilidad`` es una *estimación* del modelo, no una garantía. ``confianza``
    refleja cuánta ventaja/confluencia respalda la señal (0..1).
    """

    momento: datetime
    direccion: Direccion
    entrada: float
    stop_loss: float
    take_profits: List[TakeProfit]

    probabilidad: float          # P(éxito) estimada por el modelo, 0..1.
    confianza: float             # confianza/convicción agregada, 0..1.
    riesgo_recompensa: float     # R:R al primer TP completo (o TP final).
    tamano_posicion: float       # tamaño en lotes/unidades según el riesgo.

    # Explicabilidad: por qué SÍ, por qué NO y qué vigilar.
    contexto_macro: str = ""
    contexto_tecnico: str = ""
    factores_fundamentales: str = ""
    motivos_entrada: List[str] = field(default_factory=list)
    motivos_no_entrada: List[str] = field(default_factory=list)
    riesgos: List[str] = field(default_factory=list)
    duracion_estimada: str = ""
    puntuacion: float = 0.0      # puntuación bruta de confluencia (auditoría).

    def __post_init__(self) -> None:
        if not 0.0 <= self.probabilidad <= 1.0:
            raise ValueError("probabilidad fuera de [0, 1]")
        if not 0.0 <= self.confianza <= 1.0:
            raise ValueError("confianza fuera de [0, 1]")
        # El stop debe estar en el lado correcto de la entrada.
        if self.direccion is Direccion.COMPRA and self.stop_loss >= self.entrada:
            raise ValueError("En COMPRA el stop debe estar por debajo de la entrada.")
        if self.direccion is Direccion.VENTA and self.stop_loss <= self.entrada:
            raise ValueError("En VENTA el stop debe estar por encima de la entrada.")

    @property
    def riesgo_por_unidad(self) -> float:
        """Distancia al stop, en dólares por onza."""
        return abs(self.entrada - self.stop_loss)

    def resumen(self) -> str:
        tps = " / ".join(f"{tp.precio:.2f} ({tp.r_multiple:.1f}R)" for tp in self.take_profits)
        return (
            f"[{self.direccion.value.upper()}] XAU/USD @ {self.entrada:.2f} | "
            f"SL {self.stop_loss:.2f} | TP {tps} | "
            f"P≈{self.probabilidad:.0%} conf {self.confianza:.0%} | "
            f"R:R {self.riesgo_recompensa:.2f}"
        )
