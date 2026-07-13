"""Motor de backtesting event-driven.

Modelo de ejecución (deliberadamente conservador para no inflar resultados):

* Las señales se generan con datos **hasta la vela actual** (sin look-ahead).
* La operación se abre al cierre de la vela de señal (o a la apertura de la
  siguiente, según ``entrada_siguiente_apertura``).
* Dentro de cada vela se comprueba **primero el stop** y luego los objetivos
  (hipótesis pesimista: si una vela toca ambos, se asume la pérdida).
* Objetivos parciales: al alcanzar TP1 el stop se mueve a break-even.
* Solo una operación abierta a la vez y tope diario de operaciones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from ..config import ConfiguracionSistema
from ..dominio import (
    Direccion,
    EstadoOperacion,
    MarketSnapshot,
    Signal,
    Trade,
    sesion_de,
)
from ..indicadores import atr as _atr
from ..senales import MotorSenales
from .metricas import Metricas, calcular_metricas


@dataclass(slots=True)
class ResultadoBacktest:
    metricas: Metricas
    operaciones: List[Trade] = field(default_factory=list)

    def resumen(self) -> str:
        return self.metricas.resumen()


class Backtester:
    def __init__(
        self,
        cfg: ConfiguracionSistema,
        motor: Optional[MotorSenales] = None,
        calentamiento: int = 250,
        entrada_siguiente_apertura: bool = True,
        ventana_analisis: int = 400,
    ) -> None:
        self.cfg = cfg
        self.motor = motor or MotorSenales(cfg)
        self.calentamiento = calentamiento
        self.entrada_siguiente_apertura = entrada_siguiente_apertura
        # Ventana de velas que ve el motor en cada paso. Acota el coste a O(n·v)
        # en lugar de O(n²) y refleja el uso real (no se necesita todo el
        # histórico para calcular el estado actual). Debe superar el mayor
        # periodo de calentamiento de los indicadores (EMA 200).
        self.ventana_analisis = max(ventana_analisis, calentamiento)

    def ejecutar(self, df: pd.DataFrame) -> ResultadoBacktest:
        df = df.copy()
        atr_serie = _atr(df, 14)
        highs = df["high"].to_numpy()
        lows = df["low"].to_numpy()
        closes = df["close"].to_numpy()
        opens = df["open"].to_numpy()
        spreads = df["spread"].to_numpy() if "spread" in df.columns else None
        indices = df.index

        operaciones: List[Trade] = []
        i = self.calentamiento
        n = len(df)
        ops_por_dia: dict = {}

        while i < n - 1:
            momento = indices[i].to_pydatetime()
            dia = momento.date()
            if ops_por_dia.get(dia, 0) >= self.cfg.riesgo.operaciones_max_dia:
                i += 1
                continue

            atr_val = float(atr_serie.iloc[i])
            if atr_val <= 0 or pd.isna(atr_val):
                i += 1
                continue

            spread = float(spreads[i]) if spreads is not None else 0.25
            snapshot = MarketSnapshot(
                momento=momento, precio=float(closes[i]), spread=spread,
                atr=atr_val, sesion=sesion_de(momento),
            )
            inicio = max(0, i + 1 - self.ventana_analisis)
            resultado = self.motor.analizar(df.iloc[inicio : i + 1], snapshot)
            if not resultado.hay_operacion or resultado.signal is None:
                i += 1
                continue

            signal = resultado.signal
            idx_entrada = i + 1 if self.entrada_siguiente_apertura else i
            precio_entrada = float(opens[idx_entrada]) if self.entrada_siguiente_apertura else signal.entrada
            trade = self._simular(
                signal, precio_entrada, idx_entrada, highs, lows, indices,
            )
            operaciones.append(trade)
            ops_por_dia[dia] = ops_por_dia.get(dia, 0) + 1
            # Reanudar tras el cierre de la operación (una posición a la vez).
            i = trade.contexto.get("indice_cierre", idx_entrada) + 1

        anios = max((indices[-1] - indices[self.calentamiento]).days / 365.25, 1e-6)
        metricas = calcular_metricas(operaciones, self.cfg.capital, anios)
        return ResultadoBacktest(metricas=metricas, operaciones=operaciones)

    def _simular(
        self,
        signal: Signal,
        entrada: float,
        idx_entrada: int,
        highs,
        lows,
        indices,
    ) -> Trade:
        """Simula la vida de la operación con stop, TPs parciales y break-even."""
        signo = signal.direccion.signo
        riesgo_unidad = abs(entrada - signal.stop_loss)
        # Recolocar stop relativo al precio de entrada real (por si hubo hueco).
        stop = entrada - signo * riesgo_unidad
        tps = [(entrada + signo * riesgo_unidad * tp.r_multiple, tp.fraccion, tp.r_multiple)
               for tp in signal.take_profits]

        tamano_total = signal.tamano_posicion
        restante = 1.0
        realizado_r = 0.0
        pnl = 0.0
        stop_actual = stop
        tps_pendientes = list(tps)
        n = len(highs)

        idx_cierre = idx_entrada
        estado = EstadoOperacion.ABIERTA
        precio_cierre = entrada

        for j in range(idx_entrada, n):
            hi, lo = highs[j], lows[j]
            idx_cierre = j

            # 1) Stop primero (hipótesis pesimista).
            golpea_stop = (lo <= stop_actual) if signo > 0 else (hi >= stop_actual)
            if golpea_stop:
                r_stop = signo * (stop_actual - entrada) / riesgo_unidad
                realizado_r += restante * r_stop
                pnl += restante * tamano_total * signo * (stop_actual - entrada)
                precio_cierre = stop_actual
                estado = (EstadoOperacion.CERRADA_SL if stop_actual == stop
                          else EstadoOperacion.CERRADA_MANUAL)  # break-even.
                restante = 0.0
                break

            # 2) Objetivos en orden.
            while tps_pendientes:
                precio_tp, fraccion, r_mult = tps_pendientes[0]
                alcanzado = (hi >= precio_tp) if signo > 0 else (lo <= precio_tp)
                if not alcanzado:
                    break
                realizado_r += fraccion * r_mult
                pnl += fraccion * tamano_total * signo * (precio_tp - entrada)
                restante -= fraccion
                precio_cierre = precio_tp
                tps_pendientes.pop(0)
                # Tras el primer objetivo, proteger con break-even.
                stop_actual = entrada

            if restante <= 1e-9:
                estado = EstadoOperacion.CERRADA_TP
                break

        if estado is EstadoOperacion.ABIERTA:
            # No se resolvió: cerrar a último precio disponible.
            precio_cierre = float(highs[-1] + lows[-1]) / 2.0
            realizado_r += restante * signo * (precio_cierre - entrada) / riesgo_unidad
            pnl += restante * tamano_total * signo * (precio_cierre - entrada)
            estado = EstadoOperacion.CERRADA_MANUAL

        trade = Trade(
            momento_apertura=indices[idx_entrada].to_pydatetime(),
            direccion=signal.direccion,
            entrada=entrada,
            stop_loss=stop,
            take_profit=tps[-1][0],
            tamano=tamano_total,
            riesgo_pct=self.cfg.riesgo.riesgo_por_operacion,
            estado=estado,
            momento_cierre=indices[idx_cierre].to_pydatetime(),
            precio_cierre=precio_cierre,
            resultado_r=realizado_r,
            pnl=pnl,
            contexto={
                "indice_cierre": idx_cierre,
                "sesion": signal.contexto_tecnico,
                "probabilidad": signal.probabilidad,
                "confianza": signal.confianza,
                "puntuacion": signal.puntuacion,
            },
        )
        return trade
