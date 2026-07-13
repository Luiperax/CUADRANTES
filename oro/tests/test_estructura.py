"""Pruebas de la detección de estructura de mercado y SMC."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from oro.estructura import analizar_estructura, detectar_swings
from oro.estructura.analisis import Tendencia, TipoSwing


def _df(precios):
    n = len(precios)
    idx = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = np.array(precios, dtype=float)
    return pd.DataFrame({
        "open": close,
        "high": close + 0.5,
        "low": close - 0.5,
        "close": close,
        "volume": np.ones(n),
    }, index=idx)


def test_detecta_swing_alto_y_bajo():
    # Pico en el centro, valle claro a los lados.
    precios = [10, 11, 12, 15, 12, 11, 10, 9, 6, 9, 10, 11]
    swings = detectar_swings(_df(precios), k=2)
    tipos = {s.tipo for s in swings}
    assert TipoSwing.ALTO in tipos
    assert TipoSwing.BAJO in tipos


def test_tendencia_alcista_por_maximos_y_minimos_crecientes():
    # Serie con HH/HL en zig-zag ascendente.
    base = []
    nivel = 100.0
    for _ in range(8):
        base += [nivel, nivel + 5, nivel + 2, nivel + 7]
        nivel += 6
    est = analizar_estructura(_df(base), k=1)
    assert est.tendencia in (Tendencia.ALCISTA, Tendencia.LATERAL)
    assert est.ultimo_swing_alto is not None


def test_fvg_alcista_se_detecta():
    # Hueco alcista: low de la vela 3 por encima del high de la vela 1.
    from oro.estructura.analisis import _detectar_fvg

    idx = pd.date_range("2024-01-01", periods=5, freq="15min", tz="UTC")
    df = pd.DataFrame({
        "open":  [100, 101, 108, 109, 110],
        "high":  [102, 103, 112, 111, 112],
        "low":   [99, 100, 105, 108, 109],   # low[2]=105 > high[0]=102 -> FVG alcista.
        "close": [101, 102, 110, 110, 111],
        "volume": [1, 1, 1, 1, 1],
    }, index=idx)
    fvgs = _detectar_fvg(df)
    assert any(f.alcista for f in fvgs)
    fvg = next(f for f in fvgs if f.alcista)
    assert fvg.inferior == 102 and fvg.superior == 105  # entre high[0] y low[2].


def test_estructura_no_falla_con_pocos_datos():
    est = analizar_estructura(_df([100, 101, 102]), k=2)
    assert est.tendencia is Tendencia.LATERAL
