"""
Resolución centralizada de rutas de datos.

Para que la aplicación de escritorio y la versión web estén **sincronizadas**,
ambas deben utilizar exactamente el mismo fichero de base de datos. Este módulo
resuelve esa ruta de forma única y predecible:

1. Si existe la variable de entorno ``CUADRANTES_DB``, se usa su valor. Esto
   permite apuntar ambas aplicaciones a una ubicación compartida (por ejemplo, una
   carpeta sincronizada o una unidad de red) para compartir datos incluso entre
   equipos.
2. En caso contrario, se usa ``<raíz-del-proyecto>/datos/cuadrantes.db`` como ruta
   absoluta, de modo que no dependa del directorio desde el que se lance el
   programa.

Así, arrancar el escritorio (`ejecutar.bat`) y la web (`ejecutar_movil.bat`) en el
mismo equipo comparte automáticamente la misma información.
"""

from __future__ import annotations

import os
from pathlib import Path

# Raíz del proyecto = carpeta que contiene el paquete «cuadrantes».
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
_VARIABLE_ENTORNO = "CUADRANTES_DB"


def ruta_base_datos() -> Path:
    """Devuelve la ruta absoluta y compartida del fichero de base de datos."""
    valor = os.environ.get(_VARIABLE_ENTORNO)
    if valor:
        ruta = Path(valor).expanduser()
    else:
        ruta = RAIZ_PROYECTO / "datos" / "cuadrantes.db"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta.resolve()
