"""Fixtures compartidas de las pruebas."""

from __future__ import annotations

import pytest

from oro.config import cargar_configuracion
from oro.datos import ProveedorSintetico


@pytest.fixture(scope="session")
def cfg():
    return cargar_configuracion()


@pytest.fixture(scope="session")
def df_pequeno():
    """Histórico sintético pequeño para pruebas rápidas."""
    return ProveedorSintetico(velas=1500, semilla=123).historico(1500)


@pytest.fixture(scope="session")
def df_medio():
    return ProveedorSintetico(velas=4000, semilla=123).historico(4000)
