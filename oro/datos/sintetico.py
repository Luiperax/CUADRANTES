"""Proveedor de datos sintéticos para desarrollo, pruebas y backtesting offline.

Genera una serie de precios con:
  * deriva (tendencia) que cambia por tramos (regímenes de mercado);
  * volatilidad estocástica (clústeres de volatilidad, tipo GARCH simplificado);
  * ruido intravela coherente que respeta OHLC.

No pretende replicar el oro real: sirve para ejercitar todo el sistema de punta
a punta de forma reproducible. Para resultados con valor, use datos reales.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .base import ProveedorDatos

_MINUTOS_TF = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


class ProveedorSintetico(ProveedorDatos):
    def __init__(
        self,
        velas: int = 5000,
        precio_inicial: float = 2000.0,
        timeframe: str = "M15",
        semilla: int = 42,
        spread_base: float = 0.25,
    ) -> None:
        self._n = velas
        self._precio_inicial = precio_inicial
        self._tf_min = _MINUTOS_TF.get(timeframe, 15)
        self._semilla = semilla
        self._spread_base = spread_base
        self._df = self._generar()

    def _generar(self) -> pd.DataFrame:
        rng = np.random.default_rng(self._semilla)
        n = self._n

        # Regímenes de deriva: tramos con tendencia distinta.
        deriva = np.zeros(n)
        i = 0
        while i < n:
            tramo = int(rng.integers(150, 600))
            mu = rng.normal(0.0, 0.00035)  # deriva por vela.
            deriva[i : i + tramo] = mu
            i += tramo

        # Volatilidad con agrupamiento (proceso AR(1) sobre log-vol).
        log_vol = np.zeros(n)
        log_vol[0] = np.log(0.0016)
        for t in range(1, n):
            log_vol[t] = 0.97 * log_vol[t - 1] + 0.03 * np.log(0.0016) + rng.normal(0, 0.08)
        vol = np.exp(log_vol)

        retornos = deriva + vol * rng.standard_normal(n)
        cierre = self._precio_inicial * np.exp(np.cumsum(retornos))
        apertura = np.empty(n)
        apertura[0] = self._precio_inicial
        apertura[1:] = cierre[:-1]

        # Mechas proporcionales a la volatilidad de la vela.
        mecha = np.abs(rng.standard_normal(n)) * vol * cierre * 0.8
        cuerpo_alto = np.maximum(apertura, cierre)
        cuerpo_bajo = np.minimum(apertura, cierre)
        high = cuerpo_alto + mecha * rng.uniform(0.2, 1.0, n)
        low = cuerpo_bajo - mecha * rng.uniform(0.2, 1.0, n)

        volumen = (1000 + 8000 * vol / vol.mean() * rng.uniform(0.5, 1.5, n)).round()
        spread = self._spread_base * (1 + 2 * (vol / vol.mean() - 1).clip(0)).round(3)

        fin = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        indices = pd.date_range(
            end=fin, periods=n, freq=f"{self._tf_min}min", tz="UTC"
        )
        df = pd.DataFrame(
            {
                "open": apertura,
                "high": high,
                "low": low,
                "close": cierre,
                "volume": volumen,
                "spread": spread,
            },
            index=indices,
        )
        self.validar(df)
        return df

    def historico(self, velas: int) -> pd.DataFrame:
        return self._df.tail(velas).copy()
