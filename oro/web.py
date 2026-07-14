"""Punto de entrada para desplegar el panel en vivo en la nube.

Arranque (local o en un proveedor cloud):

    uvicorn oro.web:app --host 0.0.0.0 --port ${PORT:-8010}

Variables de entorno relevantes:
    ORO_INTERVALO           segundos entre ciclos (por defecto 900 = 15 min).
    ORO_PANEL_CLAVE         clave para proteger el panel público (recomendado).
    ORO_TELEGRAM_TOKEN,
    ORO_TELEGRAM_CHAT_ID    para recibir los avisos en el móvil por Telegram.
    ORO_WEBHOOK_URL,
    ORO_SMTP_*              otros canales de notificación (push, email…).
    ORO_CAPITAL,
    ORO_RIESGO_POR_OPERACION, ...  parámetros de riesgo (ver oro/config.py).
"""

from __future__ import annotations

import os

from .api.vivo_web import crear_app_vivo
from .cli import _construir_notificador
from .config import cargar_configuracion
from .vivo import RunnerVivo

_intervalo = int(os.getenv("ORO_INTERVALO", "900"))

# Runner con datos reales (Yahoo) y los canales de notificación disponibles.
_runner = RunnerVivo(cargar_configuracion(), notificador=_construir_notificador())

# App ASGI que uvicorn/gunicorn sirven. El motor arranca solo en segundo plano.
app = crear_app_vivo(_runner, intervalo=_intervalo)
