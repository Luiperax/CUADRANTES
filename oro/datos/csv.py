"""Proveedor que carga histórico OHLCV real desde un fichero CSV.

Formato esperado (cabecera flexible; se admiten sinónimos habituales):
    timestamp, open, high, low, close, volume[, spread]

``timestamp`` puede ser texto ISO 8601 o epoch en segundos/milisegundos.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .base import ProveedorDatos

_ALIAS = {
    "time": "timestamp", "date": "timestamp", "datetime": "timestamp",
    "o": "open", "h": "high", "l": "low", "c": "close",
    "vol": "volume", "v": "volume", "tickvol": "volume",
}


class ProveedorCSV(ProveedorDatos):
    def __init__(self, ruta: str | Path) -> None:
        self._ruta = Path(ruta)
        if not self._ruta.exists():
            raise FileNotFoundError(f"No existe el CSV: {self._ruta}")
        self._df = self._cargar()

    def _cargar(self) -> pd.DataFrame:
        df = pd.read_csv(self._ruta)
        df = df.rename(columns={c: _ALIAS.get(c.lower().strip(), c.lower().strip())
                                for c in df.columns})
        if "timestamp" not in df.columns:
            raise ValueError("El CSV no tiene columna de tiempo (timestamp/date/time).")
        ts = df["timestamp"]
        if pd.api.types.is_numeric_dtype(ts):
            unidad = "ms" if ts.iloc[0] > 10_000_000_000 else "s"
            df["timestamp"] = pd.to_datetime(ts, unit=unidad, utc=True)
        else:
            df["timestamp"] = pd.to_datetime(ts, utc=True)
        if "volume" not in df.columns:
            df["volume"] = 0.0
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        cols = ["open", "high", "low", "close", "volume"]
        if "spread" in df.columns:
            cols.append("spread")
        df = df[cols].dropna(subset=["open", "high", "low", "close"])
        self.validar(df)
        return df

    def historico(self, velas: int) -> pd.DataFrame:
        return self._df.tail(velas).copy()
