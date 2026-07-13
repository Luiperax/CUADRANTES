"""Cálculo de métricas de rendimiento a partir de la lista de operaciones."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

from ..dominio import Trade


@dataclass(slots=True)
class Metricas:
    operaciones: int = 0
    ganadoras: int = 0
    perdedoras: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy_r: float = 0.0          # resultado medio por operación, en R.
    sharpe: float = 0.0                # anualizado (aprox.) sobre resultados por operación.
    max_drawdown: float = 0.0          # caída máxima de la curva de capital (fracción).
    rentabilidad_total: float = 0.0    # sobre el capital inicial (fracción).
    cagr: float = 0.0                  # rentabilidad anual compuesta (fracción).
    racha_ganadora_max: int = 0
    racha_perdedora_max: int = 0
    media_r_ganadora: float = 0.0
    media_r_perdedora: float = 0.0
    equity: List[float] = field(default_factory=list)

    def resumen(self) -> str:
        return (
            f"Operaciones: {self.operaciones} | Win rate: {self.win_rate:.1%} | "
            f"Profit Factor: {self.profit_factor:.2f} | Expectancy: {self.expectancy_r:+.3f}R | "
            f"Sharpe: {self.sharpe:.2f} | Max DD: {self.max_drawdown:.1%} | "
            f"Rent.: {self.rentabilidad_total:+.1%} | CAGR: {self.cagr:+.1%} | "
            f"Rachas +{self.racha_ganadora_max}/-{self.racha_perdedora_max}"
        )


def _rachas(resultados: List[bool]) -> tuple[int, int]:
    max_g = max_p = act_g = act_p = 0
    for gano in resultados:
        if gano:
            act_g += 1
            act_p = 0
        else:
            act_p += 1
            act_g = 0
        max_g = max(max_g, act_g)
        max_p = max(max_p, act_p)
    return max_g, max_p


def calcular_metricas(
    operaciones: List[Trade],
    capital_inicial: float,
    anios: float,
) -> Metricas:
    """Calcula las métricas. ``anios`` es el intervalo temporal cubierto por el
    backtest, para anualizar Sharpe y CAGR.
    """
    m = Metricas()
    cerradas = [t for t in operaciones if t.resultado_r is not None]
    m.operaciones = len(cerradas)
    if not cerradas:
        m.equity = [capital_inicial]
        return m

    erres = [t.resultado_r for t in cerradas]
    ganancias = [r for r in erres if r > 0]
    perdidas = [r for r in erres if r <= 0]
    m.ganadoras = len(ganancias)
    m.perdedoras = len(perdidas)
    m.win_rate = m.ganadoras / m.operaciones
    m.media_r_ganadora = sum(ganancias) / len(ganancias) if ganancias else 0.0
    m.media_r_perdedora = sum(perdidas) / len(perdidas) if perdidas else 0.0

    suma_g = sum(ganancias)
    suma_p = abs(sum(perdidas))
    m.profit_factor = (suma_g / suma_p) if suma_p > 0 else math.inf
    m.expectancy_r = sum(erres) / len(erres)

    # Curva de capital compuesta a partir del PnL real de cada operación.
    equity = [capital_inicial]
    for t in cerradas:
        equity.append(equity[-1] + (t.pnl or 0.0))
    m.equity = equity
    m.rentabilidad_total = equity[-1] / capital_inicial - 1.0

    # Máximo drawdown sobre la curva de capital.
    pico = equity[0]
    max_dd = 0.0
    for v in equity:
        pico = max(pico, v)
        if pico > 0:
            max_dd = max(max_dd, (pico - v) / pico)
    m.max_drawdown = max_dd

    # CAGR.
    if anios > 0 and equity[-1] > 0:
        m.cagr = (equity[-1] / capital_inicial) ** (1 / anios) - 1.0

    # Sharpe anualizado (aprox.) sobre los resultados por operación en R.
    n = len(erres)
    media = sum(erres) / n
    var = sum((r - media) ** 2 for r in erres) / n
    desv = math.sqrt(var)
    if desv > 0 and anios > 0:
        ops_por_anio = n / anios
        m.sharpe = (media / desv) * math.sqrt(ops_por_anio)

    m.racha_ganadora_max, m.racha_perdedora_max = _rachas([r > 0 for r in erres])
    return m
