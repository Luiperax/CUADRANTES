"""Pruebas de la gestión de riesgo: lo más crítico del sistema."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from oro.config import cargar_configuracion
from oro.dominio import Direccion, MarketSnapshot
from oro.dominio.mercado import Sesion
from oro.riesgo import calcular_niveles, dimensionar_posicion, evaluar_guardas


def test_stop_por_debajo_en_compra():
    cfg = cargar_configuracion()
    n = calcular_niveles(2000.0, Direccion.COMPRA, atr=5.0, cfg=cfg)
    assert n.stop_loss < 2000.0
    assert all(tp.precio > 2000.0 for tp in n.take_profits)
    # distancia = 1.5 * ATR = 7.5
    assert n.riesgo_por_unidad == pytest.approx(7.5)


def test_stop_por_encima_en_venta():
    cfg = cargar_configuracion()
    n = calcular_niveles(2000.0, Direccion.VENTA, atr=5.0, cfg=cfg)
    assert n.stop_loss > 2000.0
    assert all(tp.precio < 2000.0 for tp in n.take_profits)


def test_dimensionado_arriesga_el_porcentaje_exacto():
    cfg = cargar_configuracion()
    cfg.capital = 10_000.0
    cfg.riesgo.riesgo_por_operacion = 0.005  # 0.5 % => 50 $.
    riesgo_unidad = 7.5
    tam = dimensionar_posicion(riesgo_unidad, cfg)
    # Pérdida potencial = tam * riesgo_unidad debe ser 50 $.
    assert tam * riesgo_unidad == pytest.approx(50.0)


def test_dimensionado_seguro_ante_riesgo_cero():
    cfg = cargar_configuracion()
    assert dimensionar_posicion(0.0, cfg) == 0.0


def _snap(**kw):
    base = dict(momento=datetime.now(timezone.utc), precio=2000.0, spread=0.2,
                atr=5.0, sesion=Sesion.LONDRES)
    base.update(kw)
    return MarketSnapshot(**base)


def test_guardas_bloquean_spread_alto():
    cfg = cargar_configuracion()
    assert evaluar_guardas(_snap(spread=2.0), cfg)  # spread muy alto -> no operar.


def test_guardas_bloquean_volatilidad_extrema_y_plana():
    cfg = cargar_configuracion()
    assert evaluar_guardas(_snap(atr=100.0), cfg)
    assert evaluar_guardas(_snap(atr=0.1), cfg)


def test_guardas_bloquean_noticia_alta():
    cfg = cargar_configuracion()
    assert evaluar_guardas(_snap(riesgo_noticia_alta=True), cfg)


def test_guardas_permiten_condiciones_normales():
    cfg = cargar_configuracion()
    assert evaluar_guardas(_snap(), cfg) == []
