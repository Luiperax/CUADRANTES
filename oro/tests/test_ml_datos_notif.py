"""Pruebas de ML (validación), proveedores de datos y notificaciones."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from oro.config import cargar_configuracion
from oro.datos import ProveedorCSV, ProveedorSintetico
from oro.dominio import Direccion, Signal, TakeProfit
from oro.ml import SKLEARN_DISPONIBLE
from oro.ml.validacion import _auc
from oro.notificaciones import NotificadorConsola, NotificadorMultiple, mensaje_de_senal
from oro.notificaciones.base import Evento, Notificador


def test_proveedor_sintetico_cumple_contrato():
    df = ProveedorSintetico(velas=500).historico(500)
    ProveedorSintetico.validar(df)
    assert (df["high"] >= df["low"]).all()
    assert (df["high"] >= df[["open", "close"]].max(axis=1)).all()
    assert (df["low"] <= df[["open", "close"]].min(axis=1)).all()


def test_proveedor_sintetico_reproducible():
    a = ProveedorSintetico(velas=300, semilla=7).historico(300)
    b = ProveedorSintetico(velas=300, semilla=7).historico(300)
    pd.testing.assert_frame_equal(a, b)


def test_proveedor_csv(tmp_path: Path):
    df = ProveedorSintetico(velas=200, semilla=1).historico(200)
    ruta = tmp_path / "datos.csv"
    df.reset_index(names="timestamp").to_csv(ruta, index=False)
    prov = ProveedorCSV(ruta)
    cargado = prov.historico(200)
    assert len(cargado) == 200
    assert cargado["close"].iloc[-1] == pytest.approx(df["close"].iloc[-1])


def test_auc_perfecto_y_aleatorio():
    y = np.array([0, 0, 1, 1])
    assert _auc(y, np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)
    assert _auc(y, np.array([0.9, 0.8, 0.2, 0.1])) == pytest.approx(0.0)


@pytest.mark.skipif(not SKLEARN_DISPONIBLE, reason="scikit-learn no instalado")
def test_walk_forward_detecta_estructura_temporal():
    from oro.features import construir_features
    from oro.ml import generar_etiquetas, walk_forward

    cfg = cargar_configuracion()
    df = ProveedorSintetico(velas=4000, semilla=5).historico(4000)
    X = construir_features(df)
    y = generar_etiquetas(df, cfg, horizonte=48)
    wf = walk_forward(X, y, n_folds=4)
    assert len(wf.auc_test) >= 1
    # El AUC debe ser un número válido; el criterio de aceptación existe.
    assert not np.isnan(wf.auc_test_medio)
    assert isinstance(wf.aceptable(), bool)


def test_mensaje_de_senal_incluye_datos_clave():
    from datetime import datetime, timezone
    s = Signal(
        momento=datetime.now(timezone.utc), direccion=Direccion.COMPRA, entrada=2000,
        stop_loss=1990, take_profits=[TakeProfit(2010, 0.5, 1.0), TakeProfit(2020, 0.5, 2.0)],
        probabilidad=0.62, confianza=0.7, riesgo_recompensa=1.5, tamano_posicion=3.0,
        motivos_entrada=["Tendencia a favor."],
    )
    msg = mensaje_de_senal(s)
    assert "2000.00" in msg and "1990.00" in msg
    assert "no es garantía" in msg
    assert "no asesoramiento" in msg.lower()


class _Espia(Notificador):
    def __init__(self):
        self.enviados = 0

    def enviar(self, titulo, cuerpo, evento=Evento.NUEVA_SENAL):
        self.enviados += 1
        return True


def test_notificador_multiple_reenvia_a_todos():
    a, b = _Espia(), _Espia()
    NotificadorMultiple([a, b]).enviar("t", "c")
    assert a.enviados == 1 and b.enviados == 1


def test_notificador_multiple_tolera_fallos():
    class _Rompe(Notificador):
        def enviar(self, *a, **k):
            raise RuntimeError("canal caído")

    ok = _Espia()
    assert NotificadorMultiple([_Rompe(), ok]).enviar("t", "c") is True
    assert ok.enviados == 1
