"""La configuración guardada con una calibración vieja se recalibra una sola vez."""
import json

from cuadrantes.config.configuracion import VERSION_CALIBRACION, Configuracion
from cuadrantes.servicio import ServicioCuadrantes


def _guardar_vieja(servicio, **pesos):
    """Simula una base de datos creada antes de la última calibración."""
    datos = json.loads(Configuracion().a_json())
    datos.pop("version_calibracion", None)          # sin versión = anterior a la 1
    datos["pesos"].update(pesos)
    datos["empresa"] = "EMPRESA EDITADA"
    servicio.config_repo.bd.conexion.execute(
        "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
        ("principal", json.dumps(datos)))
    servicio.config_repo.bd.conexion.commit()


def test_config_vieja_se_recalibra_y_conserva_lo_demas(tmp_path):
    servicio = ServicioCuadrantes(tmp_path / "t.db")
    defecto = Configuracion().pesos.limite_cambios_fase
    _guardar_vieja(servicio, limite_cambios_fase=1)

    config = servicio.configuracion()
    assert config.pesos.limite_cambios_fase == defecto      # el código manda
    assert config.empresa == "EMPRESA EDITADA"              # lo demás se conserva
    assert config.version_calibracion == VERSION_CALIBRACION
    servicio.cerrar()


def test_config_actual_respeta_las_ediciones(tmp_path):
    servicio = ServicioCuadrantes(tmp_path / "t.db")
    config = servicio.configuracion()
    config.pesos.limite_cambios_fase = 777
    servicio.guardar_configuracion(config)
    assert servicio.configuracion().pesos.limite_cambios_fase == 777
    servicio.cerrar()
