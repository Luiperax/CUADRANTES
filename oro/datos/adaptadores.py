"""Adaptadores a fuentes de datos reales.

:class:`ProveedorYahoo` obtiene velas OHLCV reales del oro desde la API pública
de gráficos de Yahoo Finance. Por defecto usa el futuro continuo del oro
(``GC=F``), que sigue de cerca al XAU/USD al contado y es de acceso gratuito.

Nota de honestidad: no es un feed institucional en tiempo real (tiene un ligero
retardo y es el futuro, no el spot exacto). Para operativa real conviene un feed
del bróker (MetaTrader 5, Interactive Brokers…) implementando esta misma
interfaz :class:`~oro.datos.base.ProveedorDatos`.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from .base import ProveedorDatos

_INTERVALO_YF = {
    "M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "60m", "H4": "60m", "D1": "1d",
}
_RANGO_POR_INTERVALO = {
    "1m": "5d", "5m": "1mo", "15m": "1mo", "30m": "2mo",
    "60m": "3mo", "1d": "2y",
}


class ProveedorYahoo(ProveedorDatos):
    def __init__(self, simbolo: str = "GC=F", timeframe: str = "M15", tiempo_espera: int = 10) -> None:
        self._simbolo = simbolo
        self._intervalo = _INTERVALO_YF.get(timeframe, "15m")
        self._rango = _RANGO_POR_INTERVALO.get(self._intervalo, "1mo")
        self._tiempo_espera = tiempo_espera
        self._cache: pd.DataFrame | None = None

    def _descargar(self) -> pd.DataFrame:
        import requests

        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{self._simbolo}"
        params = {"interval": self._intervalo, "range": self._rango}
        resp = requests.get(
            url, params=params, timeout=self._tiempo_espera,
            headers={"User-Agent": "Mozilla/5.0 oro/0.1"},
        )
        resp.raise_for_status()
        datos = resp.json()["chart"]["result"][0]
        ts = datos["timestamp"]
        q = datos["indicators"]["quote"][0]
        df = pd.DataFrame({
            "open": q["open"], "high": q["high"], "low": q["low"],
            "close": q["close"], "volume": q.get("volume", [0] * len(ts)),
        }, index=pd.to_datetime(ts, unit="s", utc=True))
        # Yahoo devuelve None en velas sin datos (festivos, huecos): se descartan.
        df = df.dropna(subset=["open", "high", "low", "close"])
        df["volume"] = df["volume"].fillna(0.0)
        # Spread aproximado no disponible en Yahoo: se estima pequeño y constante.
        df["spread"] = 0.2
        df = df[~df.index.duplicated(keep="last")].sort_index()
        self.validar(df)
        return df

    def historico(self, velas: int) -> pd.DataFrame:
        if self._cache is None:
            self._cache = self._descargar()
        return self._cache.tail(velas).copy()

    def refrescar(self) -> None:
        """Fuerza una nueva descarga (para uso en el bucle en vivo)."""
        self._cache = self._descargar()
