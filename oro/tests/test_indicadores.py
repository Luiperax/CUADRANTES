"""Pruebas de los indicadores técnicos frente a valores de referencia."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from oro.indicadores import atr, calcular_todos, ema, rsi, sma


def test_sma_valor_conocido():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    r = sma(s, 3)
    assert np.isnan(r.iloc[1])
    assert r.iloc[2] == pytest.approx(2.0)
    assert r.iloc[4] == pytest.approx(4.0)


def test_ema_calentamiento_y_monotonia():
    s = pd.Series(range(1, 20), dtype=float)
    r = ema(s, 5)
    # Los primeros (periodo-1) valores son NaN por min_periods.
    assert r.iloc[:4].isna().all()
    assert not np.isnan(r.iloc[4])
    # Con entrada creciente, la EMA es creciente y queda dentro del rango.
    validos = r.dropna()
    assert validos.is_monotonic_increasing
    assert validos.iloc[-1] < s.iloc[-1]  # la EMA va por detrás del precio.


def test_rsi_tendencia_alcista_pura_es_alto():
    s = pd.Series(np.linspace(100, 200, 60))  # sube siempre.
    r = rsi(s, 14).dropna()
    assert (r > 90).all()


def test_rsi_en_rango():
    s = pd.Series(np.cos(np.linspace(0, 20, 200)) * 10 + 100)
    r = rsi(s, 14).dropna()
    assert r.between(0, 100).all()


def test_atr_positivo():
    df = pd.DataFrame({
        "open": np.linspace(100, 110, 50),
        "high": np.linspace(101, 111, 50),
        "low": np.linspace(99, 109, 50),
        "close": np.linspace(100.5, 110.5, 50),
        "volume": np.ones(50) * 10,
    })
    a = atr(df, 14).dropna()
    assert (a > 0).all()


def test_calcular_todos_no_mira_al_futuro(df_pequeno):
    """El indicador en la posición i no debe cambiar si se añaden velas futuras."""
    completo = calcular_todos(df_pequeno)
    parcial = calcular_todos(df_pequeno.iloc[:1000])
    i = 900
    for col in ["ema_50", "rsi_14", "atr_14", "adx", "macd"]:
        a, b = completo[col].iloc[i], parcial[col].iloc[i]
        assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b, rel=1e-9)
