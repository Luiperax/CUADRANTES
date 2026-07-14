"""Pruebas del panel web en vivo (sin red: runner con datos sintéticos)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from oro.api.vivo_web import crear_app_vivo
from oro.config import cargar_configuracion
from oro.datos import ProveedorSintetico
from oro.dominio import Direccion, Signal, TakeProfit
from oro.sentimiento import AnalizadorSentimiento
from oro.vivo import GestorOperaciones, RunnerVivo

fastapi = pytest.importorskip("fastapi")
try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None

pytestmark = pytest.mark.skipif(TestClient is None, reason="TestClient/httpx no disponible")


def _runner():
    an = AnalizadorSentimiento(fuente_titulares=lambda: [], fuente_eventos=lambda: [])
    return RunnerVivo(cargar_configuracion(),
                      proveedor=ProveedorSintetico(velas=4000, semilla=3),
                      analizador=an, usar_sentimiento=False)


def test_gestor_resumen_estado_serializable():
    s = Signal(momento=datetime(2026, 1, 2, tzinfo=timezone.utc), direccion=Direccion.COMPRA,
               entrada=2000, stop_loss=1990,
               take_profits=[TakeProfit(2010, 0.5, 1.0), TakeProfit(2020, 0.5, 2.0)],
               probabilidad=0.6, confianza=0.7, riesgo_recompensa=1.5, tamano_posicion=3.0)
    est = GestorOperaciones(s).resumen_estado(precio_actual=2005)
    assert est["direccion"] == "compra"
    assert est["stop_actual"] == 1990
    assert len(est["objetivos"]) == 2
    assert est["r_flotante"] == pytest.approx(0.5, abs=1e-6)  # (2005-2000)/10 * 1.0 restante.


def test_web_salud_estado_panel():
    app = crear_app_vivo(_runner(), arrancar_scheduler=False)
    c = TestClient(app)
    assert c.get("/oro/salud").json()["estado"] == "ok"
    assert c.get("/oro/panel").status_code == 200
    assert c.get("/").status_code == 200
    # Forzar un ciclo llena el estado.
    est = c.post("/oro/ciclo").json()
    assert est["precio"] is not None
    assert "senales_hoy" in est and "abiertas" in est and "historial" in est


def test_web_protegido_por_clave():
    app = crear_app_vivo(_runner(), clave="secreta", arrancar_scheduler=False)
    c = TestClient(app)
    assert c.get("/oro/estado").status_code == 401
    assert c.get("/oro/estado?clave=mala").status_code == 401
    assert c.get("/oro/estado?clave=secreta").status_code == 200


def test_modulo_web_construye_app():
    # Importar oro.web no debe requerir red (Yahoo solo se consulta al hacer ciclo).
    import oro.web as web
    assert web.app is not None
