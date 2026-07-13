"""Pruebas del motor de señales, backtesting y features."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from oro.backtesting import Backtester
from oro.config import cargar_configuracion
from oro.dominio import MarketSnapshot, sesion_de
from oro.features import COLUMNAS_FEATURES, construir_features
from oro.indicadores import atr
from oro.senales import MotorSenales


def test_features_columnas_y_causalidad(df_medio):
    f = construir_features(df_medio)
    assert list(f.columns) == COLUMNAS_FEATURES
    # Causalidad: la fila i no cambia al añadir datos futuros.
    parcial = construir_features(df_medio.iloc[:2000])
    i = 1800
    for col in ["rsi_14", "dist_ema50_atr", "adx"]:
        a, b = f[col].iloc[i], parcial[col].iloc[i]
        assert (np.isnan(a) and np.isnan(b)) or a == pytest.approx(b, rel=1e-6)


def test_motor_sin_sesgo_no_opera_en_rango():
    cfg = cargar_configuracion()
    motor = MotorSenales(cfg)
    # Mercado plano: sin estructura clara.
    import pandas as pd
    idx = pd.date_range("2024-01-01", periods=400, freq="15min", tz="UTC")
    precio = 2000 + np.sin(np.linspace(0, 6, 400)) * 0.3
    df = pd.DataFrame({"open": precio, "high": precio + 0.2, "low": precio - 0.2,
                       "close": precio, "volume": np.ones(400)}, index=idx)
    snap = MarketSnapshot(momento=idx[-1].to_pydatetime(), precio=float(precio[-1]),
                          spread=0.2, atr=1.0, sesion=sesion_de(idx[-1].to_pydatetime()))
    r = motor.analizar(df, snap)
    assert not r.hay_operacion


def test_motor_respeta_guardas():
    cfg = cargar_configuracion()
    motor = MotorSenales(cfg)
    from oro.datos import ProveedorSintetico
    df = ProveedorSintetico(velas=600, semilla=1).historico(600)
    snap = MarketSnapshot(momento=df.index[-1].to_pydatetime(), precio=float(df.close.iloc[-1]),
                          spread=5.0,  # spread prohibitivo.
                          atr=5.0, sesion=sesion_de(df.index[-1].to_pydatetime()))
    r = motor.analizar(df, snap)
    assert not r.hay_operacion
    assert any("Spread" in m for m in r.motivos_no)


def test_backtest_produce_metricas_coherentes(df_medio):
    cfg = cargar_configuracion()
    res = Backtester(cfg, calentamiento=250).ejecutar(df_medio)
    m = res.metricas
    assert m.operaciones >= 0
    assert 0.0 <= m.win_rate <= 1.0
    assert 0.0 <= m.max_drawdown <= 1.0
    if m.operaciones > 0:
        assert m.ganadoras + m.perdedoras == m.operaciones
        assert len(m.equity) == m.operaciones + 1


def test_backtest_no_supera_tope_diario():
    cfg = cargar_configuracion()
    cfg.riesgo.operaciones_max_dia = 2
    from oro.datos import ProveedorSintetico
    df = ProveedorSintetico(velas=3000, semilla=2).historico(3000)
    res = Backtester(cfg, calentamiento=250).ejecutar(df)
    from collections import Counter
    por_dia = Counter(t.momento_apertura.date() for t in res.operaciones)
    assert all(v <= 2 for v in por_dia.values())
