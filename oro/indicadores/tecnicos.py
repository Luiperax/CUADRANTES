"""Implementaciones de indicadores técnicos sobre pandas.

Las fórmulas siguen las definiciones estándar (Wilder para RSI/ATR/ADX). Se
evita cualquier fuga de información futura: todos los cálculos usan únicamente
datos hasta la vela actual.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(serie: pd.Series, periodo: int) -> pd.Series:
    """Media móvil exponencial."""
    return serie.ewm(span=periodo, adjust=False, min_periods=periodo).mean()


def sma(serie: pd.Series, periodo: int) -> pd.Series:
    """Media móvil simple."""
    return serie.rolling(periodo, min_periods=periodo).mean()


def rsi(close: pd.Series, periodo: int = 14) -> pd.Series:
    """Índice de fuerza relativa (Wilder)."""
    delta = close.diff()
    ganancia = delta.clip(lower=0.0)
    perdida = -delta.clip(upper=0.0)
    media_g = ganancia.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    media_p = perdida.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    rs = media_g / media_p.replace(0.0, np.nan)
    resultado = 100 - (100 / (1 + rs))
    # Si no hubo pérdidas, RSI = 100; si no hubo ganancias, RSI = 0.
    resultado = resultado.where(media_p != 0, 100.0)
    resultado = resultado.where(media_g != 0, 0.0)
    return resultado


def _true_range(df: pd.DataFrame) -> pd.Series:
    cierre_prev = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - cierre_prev).abs(),
            (df["low"] - cierre_prev).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    """Average True Range (Wilder). Mide la volatilidad en dólares."""
    tr = _true_range(df)
    return tr.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()


def macd(
    close: pd.Series, rapida: int = 12, lenta: int = 26, senal: int = 9
) -> pd.DataFrame:
    """MACD, su línea de señal y el histograma."""
    linea = ema(close, rapida) - ema(close, lenta)
    linea_senal = linea.ewm(span=senal, adjust=False, min_periods=senal).mean()
    return pd.DataFrame(
        {"macd": linea, "senal": linea_senal, "histograma": linea - linea_senal}
    )


def adx(df: pd.DataFrame, periodo: int = 14) -> pd.DataFrame:
    """ADX con +DI/-DI (Wilder). Mide la fuerza de la tendencia."""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_dm = pd.Series(plus_dm, index=df.index)
    minus_dm = pd.Series(minus_dm, index=df.index)

    tr = _true_range(df)
    atr_ = tr.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean() / atr_
    minus_di = 100 * minus_dm.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean() / atr_

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx_ = dx.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    return pd.DataFrame({"adx": adx_, "plus_di": plus_di, "minus_di": minus_di})


def bollinger(close: pd.Series, periodo: int = 20, desv: float = 2.0) -> pd.DataFrame:
    """Bandas de Bollinger y %B (posición relativa dentro de las bandas)."""
    media = sma(close, periodo)
    sigma = close.rolling(periodo, min_periods=periodo).std(ddof=0)
    superior = media + desv * sigma
    inferior = media - desv * sigma
    ancho = (superior - inferior) / media
    pct_b = (close - inferior) / (superior - inferior)
    return pd.DataFrame(
        {"media": media, "superior": superior, "inferior": inferior,
         "ancho": ancho, "pct_b": pct_b}
    )


def vwap(df: pd.DataFrame, reinicio_diario: bool = True) -> pd.Series:
    """VWAP (precio medio ponderado por volumen).

    Si ``reinicio_diario`` es ``True`` (habitual en intradía), el acumulado se
    reinicia cada día natural.
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    vol = df["volume"].replace(0.0, np.nan).fillna(1.0)
    pv = tp * vol
    if reinicio_diario and isinstance(df.index, pd.DatetimeIndex):
        dia = df.index.normalize()
        pv_cum = pv.groupby(dia).cumsum()
        vol_cum = vol.groupby(dia).cumsum()
    else:
        pv_cum = pv.cumsum()
        vol_cum = vol.cumsum()
    return pv_cum / vol_cum


def calcular_todos(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve una copia del DataFrame con las columnas de todos los indicadores.

    Requiere columnas ``open, high, low, close, volume``.
    """
    faltan = {"open", "high", "low", "close", "volume"} - set(df.columns)
    if faltan:
        raise ValueError(f"Faltan columnas OHLCV: {sorted(faltan)}")

    out = df.copy()
    out["ema_20"] = ema(df["close"], 20)
    out["ema_50"] = ema(df["close"], 50)
    out["ema_200"] = ema(df["close"], 200)
    out["sma_20"] = sma(df["close"], 20)
    out["rsi_14"] = rsi(df["close"], 14)
    out["atr_14"] = atr(df, 14)
    macd_df = macd(df["close"])
    out["macd"] = macd_df["macd"]
    out["macd_senal"] = macd_df["senal"]
    out["macd_hist"] = macd_df["histograma"]
    adx_df = adx(df, 14)
    out["adx"] = adx_df["adx"]
    out["plus_di"] = adx_df["plus_di"]
    out["minus_di"] = adx_df["minus_di"]
    bb = bollinger(df["close"])
    out["bb_ancho"] = bb["ancho"]
    out["bb_pct_b"] = bb["pct_b"]
    out["vwap"] = vwap(df)
    return out
