"""Etiquetado por triple barrera (López de Prado, simplificado).

Para cada vela se plantea una operación hipotética en la dirección del sesgo
estructural con el mismo stop/objetivo que usaría el sistema (ATR dinámico). Se
mira hacia delante un horizonte máximo y se etiqueta:

    1  -> se alcanza el primer objetivo (TP1) antes que el stop.
    0  -> se alcanza el stop antes que el objetivo.
    NaN-> no se resuelve dentro del horizonte (se descarta del entrenamiento).

Las **features** son causales; solo las **etiquetas** usan el futuro, que es
exactamente lo correcto en aprendizaje supervisado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import ConfiguracionSistema
from ..estructura import analizar_estructura
from ..estructura.analisis import Tendencia
from ..indicadores import atr as _atr


def _sesgo_series(df: pd.DataFrame, ventana: int = 300) -> np.ndarray:
    """Dirección estructural (+1 alcista, -1 bajista, 0 sin sesgo) por vela.

    Se recalcula con una ventana móvil para reflejar la estructura vigente sin
    mirar al futuro.
    """
    n = len(df)
    sesgo = np.zeros(n)
    for i in range(50, n):
        inicio = max(0, i + 1 - ventana)
        est = analizar_estructura(df.iloc[inicio : i + 1])
        if est.tendencia is Tendencia.ALCISTA or est.ultimo_bos == "alcista" or est.ultimo_choch == "alcista":
            sesgo[i] = 1
        elif est.tendencia is Tendencia.BAJISTA or est.ultimo_bos == "bajista" or est.ultimo_choch == "bajista":
            sesgo[i] = -1
    return sesgo


def generar_etiquetas(
    df: pd.DataFrame,
    cfg: ConfiguracionSistema,
    horizonte: int = 48,
) -> pd.Series:
    """Devuelve una serie de etiquetas (1/0/NaN) alineada con ``df``.

    ``horizonte`` es el número máximo de velas para que la operación se resuelva.
    """
    atr = _atr(df, 14).to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    n = len(df)
    sesgo = _sesgo_series(df)

    r = cfg.riesgo
    dist_mult = r.atr_stop_mult
    tp1_r = r.r_objetivos[0]

    etiquetas = np.full(n, np.nan)
    for i in range(n - 1):
        s = sesgo[i]
        if s == 0 or atr[i] <= 0 or np.isnan(atr[i]):
            continue
        entrada = closes[i]
        riesgo = atr[i] * dist_mult
        if s > 0:
            stop = entrada - riesgo
            objetivo = entrada + riesgo * tp1_r
        else:
            stop = entrada + riesgo
            objetivo = entrada - riesgo * tp1_r

        fin = min(i + 1 + horizonte, n)
        resultado = np.nan
        for j in range(i + 1, fin):
            if s > 0:
                if lows[j] <= stop:
                    resultado = 0.0
                    break
                if highs[j] >= objetivo:
                    resultado = 1.0
                    break
            else:
                if highs[j] >= stop:
                    resultado = 0.0
                    break
                if lows[j] <= objetivo:
                    resultado = 1.0
                    break
        etiquetas[i] = resultado

    return pd.Series(etiquetas, index=df.index, name="etiqueta")
