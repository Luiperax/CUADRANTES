"""Detección de estructura de mercado y conceptos de Smart Money.

Todo el análisis es *causal*: para cada instante solo se emplea información
disponible hasta esa vela. Los swings se confirman con retardo (``k`` velas a
cada lado), lo que se respeta en el backtesting para no mirar al futuro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import pandas as pd


class TipoSwing(str, Enum):
    ALTO = "alto"
    BAJO = "bajo"


class Tendencia(str, Enum):
    ALCISTA = "alcista"
    BAJISTA = "bajista"
    LATERAL = "lateral"


@dataclass(frozen=True, slots=True)
class Swing:
    indice: int
    precio: float
    tipo: TipoSwing


@dataclass(frozen=True, slots=True)
class FairValueGap:
    """Ineficiencia de precio de 3 velas (hueco entre vela 1 y vela 3)."""

    indice: int
    inferior: float
    superior: float
    alcista: bool

    @property
    def tamano(self) -> float:
        return self.superior - self.inferior


@dataclass(frozen=True, slots=True)
class OrderBlock:
    """Última vela contraria antes de un movimiento impulsivo que rompe estructura."""

    indice: int
    inferior: float
    superior: float
    alcista: bool  # True: order block de demanda; False: de oferta.


@dataclass(slots=True)
class EstructuraMercado:
    tendencia: Tendencia
    swings: List[Swing] = field(default_factory=list)
    ultimo_bos: Optional[str] = None      # "alcista" | "bajista" | None
    ultimo_choch: Optional[str] = None    # "alcista" | "bajista" | None
    fvgs: List[FairValueGap] = field(default_factory=list)
    order_blocks: List[OrderBlock] = field(default_factory=list)
    barrido_liquidez: Optional[str] = None  # "alto" | "bajo" | None
    ultimo_swing_alto: Optional[float] = None
    ultimo_swing_bajo: Optional[float] = None


def detectar_swings(df: pd.DataFrame, k: int = 2) -> List[Swing]:
    """Detecta swings por fractales: un máximo (mínimo) es swing si es el mayor
    (menor) de las ``k`` velas a cada lado. La confirmación exige ``k`` velas
    posteriores, por lo que el swing "existe" solo a partir de ``indice + k``.
    """
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    n = len(df)
    swings: List[Swing] = []
    for i in range(k, n - k):
        ventana_h = highs[i - k : i + k + 1]
        ventana_l = lows[i - k : i + k + 1]
        if highs[i] == ventana_h.max() and (ventana_h.argmax() == k):
            swings.append(Swing(i, float(highs[i]), TipoSwing.ALTO))
        elif lows[i] == ventana_l.min() and (ventana_l.argmin() == k):
            swings.append(Swing(i, float(lows[i]), TipoSwing.BAJO))
    return swings


def _detectar_fvg(df: pd.DataFrame, min_tamano: float = 0.0) -> List[FairValueGap]:
    """FVG de 3 velas. Alcista: low[i] > high[i-2]. Bajista: high[i] < low[i-2]."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    fvgs: List[FairValueGap] = []
    for i in range(2, len(df)):
        if lows[i] > highs[i - 2] and (lows[i] - highs[i - 2]) > min_tamano:
            fvgs.append(FairValueGap(i, float(highs[i - 2]), float(lows[i]), True))
        elif highs[i] < lows[i - 2] and (lows[i - 2] - highs[i]) > min_tamano:
            fvgs.append(FairValueGap(i, float(highs[i]), float(lows[i - 2]), False))
    return fvgs


def _order_block_antes(df: pd.DataFrame, indice_impulso: int, alcista: bool) -> Optional[OrderBlock]:
    """Busca hacia atrás la última vela contraria antes de un impulso.

    Para un impulso alcista, el order block de demanda es la última vela bajista
    previa; para uno bajista, la última vela alcista previa.
    """
    o = df["open"].to_numpy()
    c = df["close"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    for j in range(indice_impulso - 1, max(indice_impulso - 12, -1), -1):
        vela_bajista = c[j] < o[j]
        if alcista and vela_bajista:
            return OrderBlock(j, float(l[j]), float(h[j]), True)
        if not alcista and not vela_bajista:
            return OrderBlock(j, float(l[j]), float(h[j]), False)
    return None


def analizar_estructura(df: pd.DataFrame, k: int = 2) -> EstructuraMercado:
    """Análisis completo de estructura sobre el histórico proporcionado.

    Devuelve el estado estructural *al final* del DataFrame: tendencia vigente,
    último BOS/CHoCH, FVGs y order blocks recientes, y si la última vela barrió
    liquidez de un swing previo.
    """
    swings = detectar_swings(df, k=k)
    estructura = EstructuraMercado(tendencia=Tendencia.LATERAL, swings=swings)
    if len(swings) < 4:
        return estructura

    altos = [s for s in swings if s.tipo is TipoSwing.ALTO]
    bajos = [s for s in swings if s.tipo is TipoSwing.BAJO]
    if altos:
        estructura.ultimo_swing_alto = altos[-1].precio
    if bajos:
        estructura.ultimo_swing_bajo = bajos[-1].precio

    # Tendencia por secuencia de swings (HH+HL = alcista; LH+LL = bajista).
    if len(altos) >= 2 and len(bajos) >= 2:
        hh = altos[-1].precio > altos[-2].precio
        hl = bajos[-1].precio > bajos[-2].precio
        lh = altos[-1].precio < altos[-2].precio
        ll = bajos[-1].precio < bajos[-2].precio
        if hh and hl:
            estructura.tendencia = Tendencia.ALCISTA
        elif lh and ll:
            estructura.tendencia = Tendencia.BAJISTA
        else:
            estructura.tendencia = Tendencia.LATERAL

    # BOS / CHoCH: ¿el cierre reciente rompió el último swing relevante?
    cierre = float(df["close"].iloc[-1])
    if estructura.ultimo_swing_alto and cierre > estructura.ultimo_swing_alto:
        if estructura.tendencia is Tendencia.BAJISTA:
            estructura.ultimo_choch = "alcista"
        else:
            estructura.ultimo_bos = "alcista"
    if estructura.ultimo_swing_bajo and cierre < estructura.ultimo_swing_bajo:
        if estructura.tendencia is Tendencia.ALCISTA:
            estructura.ultimo_choch = "bajista"
        else:
            estructura.ultimo_bos = "bajista"

    # FVGs recientes (últimas ~50 velas) y order block asociado al último impulso.
    todos_fvg = _detectar_fvg(df)
    n = len(df)
    estructura.fvgs = [f for f in todos_fvg if f.indice >= n - 50]
    if estructura.fvgs:
        ultimo = estructura.fvgs[-1]
        ob = _order_block_antes(df, ultimo.indice, alcista=ultimo.alcista)
        if ob is not None:
            estructura.order_blocks.append(ob)

    # Barrido de liquidez: la última vela perfora un swing previo pero cierra
    # de vuelta (mecha por encima del máximo / por debajo del mínimo).
    ultima = df.iloc[-1]
    if estructura.ultimo_swing_alto and ultima["high"] > estructura.ultimo_swing_alto \
            and ultima["close"] < estructura.ultimo_swing_alto:
        estructura.barrido_liquidez = "alto"
    elif estructura.ultimo_swing_bajo and ultima["low"] < estructura.ultimo_swing_bajo \
            and ultima["close"] > estructura.ultimo_swing_bajo:
        estructura.barrido_liquidez = "bajo"

    return estructura
