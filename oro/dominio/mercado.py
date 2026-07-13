"""Modelos de mercado: vela (OHLCV), instantánea y sesiones de negociación."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Optional


@dataclass(frozen=True, slots=True)
class Candle:
    """Una vela OHLCV.

    Los precios se expresan en dólares por onza (XAU/USD). ``timestamp`` debe ser
    *timezone-aware* en UTC para evitar ambigüedades entre sesiones.
    """

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    spread: float = 0.0  # spread medio observado en la vela, en dólares.

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise ValueError("Candle.timestamp debe ser timezone-aware (UTC).")
        if not (self.low <= self.open <= self.high and self.low <= self.close <= self.high):
            raise ValueError(
                f"Vela OHLC incoherente: O={self.open} H={self.high} "
                f"L={self.low} C={self.close}"
            )

    @property
    def rango(self) -> float:
        """Rango total (high - low)."""
        return self.high - self.low

    @property
    def cuerpo(self) -> float:
        """Tamaño del cuerpo (|close - open|)."""
        return abs(self.close - self.open)

    @property
    def alcista(self) -> bool:
        return self.close >= self.open


class Sesion(str, Enum):
    """Sesión de negociación (aprox., en UTC). El oro es más líquido en el
    solape Londres–Nueva York; la sesión asiática suele ser más lateral."""

    ASIA = "asia"
    LONDRES = "londres"
    NUEVA_YORK = "nueva_york"
    SOLAPE_LDN_NY = "solape_ldn_ny"
    CIERRE = "cierre"


def sesion_de(momento: datetime) -> Sesion:
    """Clasifica un instante UTC en su sesión de mercado dominante.

    Horas aproximadas (UTC): Asia 00–07, Londres 07–12, solape 12–16,
    Nueva York 16–21, cierre 21–24. Son aproximaciones deliberadamente simples;
    la ventaja real se calcula por sesión a partir del histórico, no de horarios
    fijos.
    """
    t = momento.astimezone(timezone.utc).time()

    def entre(a: int, b: int) -> bool:
        return time(a, 0) <= t < time(b, 0)

    if entre(0, 7):
        return Sesion.ASIA
    if entre(7, 12):
        return Sesion.LONDRES
    if entre(12, 16):
        return Sesion.SOLAPE_LDN_NY
    if entre(16, 21):
        return Sesion.NUEVA_YORK
    return Sesion.CIERRE


@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    """Fotografía del estado del mercado en un instante, tal y como la ve el
    motor de señales. Reúne el precio actual y el contexto que rodea la decisión.
    """

    momento: datetime
    precio: float
    spread: float
    atr: float                      # volatilidad reciente (ATR), en dólares.
    sesion: Sesion
    dxy: Optional[float] = None     # índice del dólar, si se dispone.
    rendimiento_10y: Optional[float] = None  # Treasury 10 años (%), si se dispone.
    riesgo_noticia_alta: bool = False        # evento macro de alto impacto próximo.
    sentimiento: Optional[float] = None      # [-1, 1] agregado de fundamentales/RRSS.
    metadatos: dict = field(default_factory=dict)
