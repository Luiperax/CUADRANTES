"""Una única revisión del mercado (para ejecutar de forma programada).

Pensado para GitHub Actions / cron: cada ejecución carga el estado previo
(operaciones abiertas y contador diario), hace UN ciclo del motor en vivo —que
notifica entradas y salidas por los canales configurados (Telegram, etc.)— y
guarda el estado para la siguiente ejecución.

    python -m oro.alerta

Variables de entorno:
    ORO_ESTADO              ruta del fichero de estado (por defecto oro_estado.json).
    ORO_TELEGRAM_TOKEN,
    ORO_TELEGRAM_CHAT_ID    para recibir los avisos en el móvil por Telegram.
    ORO_CAPITAL, ORO_RIESGO_POR_OPERACION, ...  parámetros (ver oro/config.py).
"""

from __future__ import annotations

import os
import sys

from .cli import _construir_notificador
from .config import cargar_configuracion
from .datos import ProveedorYahoo
from .vivo import RunnerVivo


def main() -> int:
    cfg = cargar_configuracion()
    runner = RunnerVivo(
        cfg,
        proveedor=ProveedorYahoo(timeframe=cfg.timeframe),
        notificador=_construir_notificador(),
    )
    ruta = os.getenv("ORO_ESTADO", "oro_estado.json")
    runner.cargar_estado(ruta)
    resultado = runner.ciclo()
    runner.guardar_estado(ruta)

    print(f"[{resultado.momento:%Y-%m-%d %H:%M}] oro={resultado.precio:.2f} | "
          f"{resultado.resumen_sentimiento} | abiertas={resultado.abiertas} "
          f"señales_hoy={resultado.senales_hoy}/{cfg.riesgo.operaciones_max_dia}")
    if resultado.nueva_senal:
        print("→ NUEVA ENTRADA:", resultado.nueva_senal.resumen())
    for ev in resultado.eventos_salida:
        print("→ SALIDA:", ev)
    if not resultado.nueva_senal and not resultado.eventos_salida:
        print("Sin novedades:", resultado.motivo_sin_entrada[:120] or "sin operación A+.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
