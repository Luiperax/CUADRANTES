"""Notificaciones multicanal.

Interfaz :class:`Notificador` con implementaciones para consola (por defecto y
sin dependencias), Telegram, email (SMTP) y webhook genérico (útil para push,
WhatsApp Business API autorizada, Slack, etc.). Un :class:`NotificadorMultiple`
permite enviar por varios canales a la vez.

Las notificaciones se construyen a partir de una :class:`~oro.dominio.Signal` o
de eventos de gestión (mover stop, TP alcanzado, cierre).
"""

from __future__ import annotations

from .base import Evento, Notificador, NotificadorMultiple, mensaje_de_senal
from .canales import (
    NotificadorConsola,
    NotificadorEmail,
    NotificadorTelegram,
    NotificadorWebhook,
)

__all__ = [
    "Evento",
    "Notificador",
    "NotificadorMultiple",
    "mensaje_de_senal",
    "NotificadorConsola",
    "NotificadorEmail",
    "NotificadorTelegram",
    "NotificadorWebhook",
]
