"""Interfaz común de los proveedores de datos."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class ProveedorDatos(ABC):
    """Fuente de velas OHLCV de XAU/USD.

    Contrato del DataFrame devuelto:
      * índice ``DatetimeIndex`` en UTC, ordenado ascendentemente y sin duplicados;
      * columnas ``open, high, low, close, volume`` (y opcionalmente ``spread``);
      * sin ``NaN`` en OHLC.
    """

    @abstractmethod
    def historico(self, velas: int) -> pd.DataFrame:
        """Devuelve las últimas ``velas`` velas cerradas."""

    def ultima(self) -> pd.Series:
        """Última vela cerrada disponible."""
        return self.historico(1).iloc[-1]

    @staticmethod
    def validar(df: pd.DataFrame) -> None:
        """Valida que un DataFrame cumple el contrato. Lanza ``ValueError`` si no."""
        columnas = {"open", "high", "low", "close", "volume"}
        if not columnas.issubset(df.columns):
            raise ValueError(f"Faltan columnas OHLCV: {sorted(columnas - set(df.columns))}")
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("El índice debe ser DatetimeIndex.")
        if not df.index.is_monotonic_increasing:
            raise ValueError("El índice temporal debe ser ascendente.")
        if df.index.has_duplicates:
            raise ValueError("El índice temporal tiene duplicados.")
        if df[["open", "high", "low", "close"]].isna().any().any():
            raise ValueError("Hay NaN en columnas OHLC.")
