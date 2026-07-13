"""Construcción de características a partir de OHLCV + indicadores.

Todas las features son *causales* (solo usan la vela actual y anteriores) y en su
mayoría adimensionales (ratios, posiciones relativas, distancias en unidades de
ATR), para que el modelo generalice entre distintos niveles de precio del oro.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..indicadores import calcular_todos

COLUMNAS_FEATURES = [
    "ret_1", "ret_5", "ret_20",
    "dist_ema20_atr", "dist_ema50_atr", "dist_ema200_atr",
    "pendiente_ema50",
    "rsi_14", "rsi_norm",
    "macd_hist_norm",
    "adx", "di_diff",
    "bb_pct_b", "bb_ancho",
    "atr_rel", "atr_z",
    "dist_vwap_atr",
    "vol_rel",
    "sesion_sin", "sesion_cos",
    "cuerpo_rel", "mecha_sup_rel", "mecha_inf_rel",
]


def construir_features(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve un DataFrame con las columnas de :data:`COLUMNAS_FEATURES`.

    Requiere OHLCV. Calcula internamente los indicadores. Las filas del periodo
    de calentamiento contienen ``NaN`` y deben filtrarse antes de entrenar.
    """
    d = calcular_todos(df)
    close = d["close"]
    atr = d["atr_14"].replace(0.0, np.nan)

    f = pd.DataFrame(index=d.index)
    # Retornos logarítmicos a varios horizontes.
    f["ret_1"] = np.log(close / close.shift(1))
    f["ret_5"] = np.log(close / close.shift(5))
    f["ret_20"] = np.log(close / close.shift(20))

    # Distancia a las medias, en unidades de ATR (adimensional).
    f["dist_ema20_atr"] = (close - d["ema_20"]) / atr
    f["dist_ema50_atr"] = (close - d["ema_50"]) / atr
    f["dist_ema200_atr"] = (close - d["ema_200"]) / atr
    f["pendiente_ema50"] = d["ema_50"].diff(5) / atr

    f["rsi_14"] = d["rsi_14"]
    f["rsi_norm"] = (d["rsi_14"] - 50.0) / 50.0
    f["macd_hist_norm"] = d["macd_hist"] / atr
    f["adx"] = d["adx"]
    f["di_diff"] = (d["plus_di"] - d["minus_di"]) / 100.0
    f["bb_pct_b"] = d["bb_pct_b"]
    f["bb_ancho"] = d["bb_ancho"]

    # Volatilidad relativa y su z-score sobre ventana larga.
    atr_media = d["atr_14"].rolling(200, min_periods=50).mean()
    atr_std = d["atr_14"].rolling(200, min_periods=50).std(ddof=0)
    f["atr_rel"] = d["atr_14"] / atr_media
    f["atr_z"] = (d["atr_14"] - atr_media) / atr_std.replace(0.0, np.nan)

    f["dist_vwap_atr"] = (close - d["vwap"]) / atr

    vol_media = d["volume"].rolling(50, min_periods=10).mean()
    f["vol_rel"] = d["volume"] / vol_media.replace(0.0, np.nan)

    # Hora del día codificada de forma cíclica (respeta la continuidad 23h→0h).
    minutos = (d.index.hour * 60 + d.index.minute).to_numpy()
    ang = 2 * np.pi * minutos / (24 * 60)
    f["sesion_sin"] = np.sin(ang)
    f["sesion_cos"] = np.cos(ang)

    # Anatomía de la vela.
    rango = (d["high"] - d["low"]).replace(0.0, np.nan)
    f["cuerpo_rel"] = (d["close"] - d["open"]).abs() / rango
    f["mecha_sup_rel"] = (d["high"] - d[["open", "close"]].max(axis=1)) / rango
    f["mecha_inf_rel"] = (d[["open", "close"]].min(axis=1) - d["low"]) / rango

    return f[COLUMNAS_FEATURES].replace([np.inf, -np.inf], np.nan)
