"""Pruebas de los modelos de dominio."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from oro.dominio import (
    Candle,
    Direccion,
    EstadoOperacion,
    Signal,
    TakeProfit,
    Trade,
    sesion_de,
)
from oro.dominio.mercado import Sesion


def _ahora():
    return datetime(2024, 1, 2, 13, 0, tzinfo=timezone.utc)


def test_candle_valida_ohlc():
    c = Candle(_ahora(), open=2000, high=2010, low=1995, close=2005, volume=100)
    assert c.rango == 15
    assert c.cuerpo == 5
    assert c.alcista


def test_candle_rechaza_ohlc_incoherente():
    with pytest.raises(ValueError):
        Candle(_ahora(), open=2000, high=1990, low=1995, close=2005)


def test_candle_exige_timezone():
    with pytest.raises(ValueError):
        Candle(datetime(2024, 1, 2, 13, 0), open=2000, high=2010, low=1995, close=2005)


def test_sesion_de():
    assert sesion_de(datetime(2024, 1, 2, 3, 0, tzinfo=timezone.utc)) is Sesion.ASIA
    assert sesion_de(datetime(2024, 1, 2, 13, 0, tzinfo=timezone.utc)) is Sesion.SOLAPE_LDN_NY


def test_signal_valida_lado_del_stop():
    with pytest.raises(ValueError):
        Signal(
            momento=_ahora(), direccion=Direccion.COMPRA, entrada=2000,
            stop_loss=2010,  # stop por encima en una compra: inválido.
            take_profits=[TakeProfit(2020, 1.0, 2.0)],
            probabilidad=0.6, confianza=0.7, riesgo_recompensa=2.0, tamano_posicion=1.0,
        )


def test_trade_resultado_ganador_y_perdedor():
    t = Trade(_ahora(), Direccion.COMPRA, entrada=2000, stop_loss=1990,
              take_profit=2020, tamano=2.0, riesgo_pct=0.005)
    t.cerrar(_ahora(), 2020, EstadoOperacion.CERRADA_TP)
    assert t.ganadora
    assert t.resultado_r == pytest.approx(2.0)  # (2020-2000)/10
    assert t.pnl == pytest.approx(40.0)          # 20 * 2 oz

    t2 = Trade(_ahora(), Direccion.VENTA, entrada=2000, stop_loss=2010,
               take_profit=1980, tamano=1.0, riesgo_pct=0.005)
    t2.cerrar(_ahora(), 2010, EstadoOperacion.CERRADA_SL)
    assert not t2.ganadora
    assert t2.resultado_r == pytest.approx(-1.0)
