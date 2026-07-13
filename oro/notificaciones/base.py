"""Interfaz de notificación y formateo de mensajes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import List

from ..dominio import Signal


class Evento(str, Enum):
    NUEVA_SENAL = "nueva_senal"
    MOVER_STOP = "mover_stop"
    TP_ALCANZADO = "tp_alcanzado"
    CIERRE = "cierre"
    CAMBIO_MERCADO = "cambio_mercado"


def mensaje_de_senal(signal: Signal) -> str:
    """Formatea una señal como mensaje legible para móvil/Telegram/email."""
    lineas = [
        f"🟢 NUEVA SEÑAL XAU/USD — {signal.direccion.value.upper()}"
        if signal.direccion.value == "compra"
        else f"🔴 NUEVA SEÑAL XAU/USD — {signal.direccion.value.upper()}",
        "",
        f"Entrada:  {signal.entrada:.2f}",
        f"Stop:     {signal.stop_loss:.2f}",
    ]
    for k, tp in enumerate(signal.take_profits, 1):
        lineas.append(f"TP{k}:      {tp.precio:.2f}  ({tp.r_multiple:.1f}R, {tp.fraccion:.0%})")
    lineas += [
        "",
        f"Probabilidad estimada: {signal.probabilidad:.0%}  (no es garantía)",
        f"Confianza: {signal.confianza:.0%}   R:R: {signal.riesgo_recompensa:.2f}",
        f"Tamaño sugerido: {signal.tamano_posicion:.2f} oz",
        "",
        "Motivos de entrada:",
    ]
    lineas += [f"  • {m}" for m in signal.motivos_entrada[:5]]
    if signal.riesgos:
        lineas += ["", "Riesgos:"]
        lineas += [f"  • {m}" for m in signal.riesgos[:3]]
    lineas += ["", f"Contexto: {signal.contexto_tecnico}"]
    lineas += ["", "⚠️ Herramienta de análisis, no asesoramiento financiero."]
    return "\n".join(lineas)


class Notificador(ABC):
    @abstractmethod
    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL) -> bool:
        """Envía la notificación. Devuelve ``True`` si tuvo éxito."""

    def notificar_senal(self, signal: Signal) -> bool:
        return self.enviar("Nueva señal XAU/USD", mensaje_de_senal(signal), Evento.NUEVA_SENAL)


class NotificadorMultiple(Notificador):
    """Reenvía a varios canales; no falla si alguno individual falla."""

    def __init__(self, canales: List[Notificador]) -> None:
        self._canales = canales

    def enviar(self, titulo: str, cuerpo: str, evento: Evento = Evento.NUEVA_SENAL) -> bool:
        ok = False
        for canal in self._canales:
            try:
                ok = canal.enviar(titulo, cuerpo, evento) or ok
            except Exception:  # noqa: BLE001 — un canal caído no debe tumbar el resto.
                continue
        return ok
