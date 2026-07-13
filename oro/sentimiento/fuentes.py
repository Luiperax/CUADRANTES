"""Obtención de titulares y eventos macro desde fuentes públicas gratuitas.

Todas las funciones son **tolerantes a fallos de red**: ante cualquier error
devuelven una lista vacía en lugar de romper el sistema. El sentimiento es una
señal de apoyo; si no está disponible, el resto del análisis sigue funcionando.

El parseo de RSS usa la librería estándar (``xml.etree``) para no añadir
dependencias.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional
from xml.etree import ElementTree

_UA = {"User-Agent": "Mozilla/5.0 oro/0.1"}
_TIEMPO_ESPERA = 8

_RSS_NOTICIAS = [
    ("Yahoo Finance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=GC=F&region=US&lang=en-US"),
    ("Google News", "https://news.google.com/rss/search?q=gold+price+XAUUSD+OR+fed+OR+inflation+when:2d&hl=en-US&gl=US&ceid=US:en"),
]
_CALENDARIO = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
_DIVISAS_ORO = {"USD", "EUR", "ALL"}  # divisas cuyos eventos mueven el oro.


@dataclass(frozen=True, slots=True)
class Titular:
    titulo: str
    fecha: Optional[datetime]
    fuente: str


@dataclass(frozen=True, slots=True)
class EventoMacro:
    titulo: str
    divisa: str
    impacto: str
    fecha: Optional[datetime]


def _parsear_fecha(texto: str) -> Optional[datetime]:
    try:
        dt = parsedate_to_datetime(texto)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def obtener_titulares(limite: int = 40) -> List[Titular]:
    """Descarga titulares de prensa financiera de las fuentes configuradas."""
    import requests

    titulares: List[Titular] = []
    for fuente, url in _RSS_NOTICIAS:
        try:
            resp = requests.get(url, timeout=_TIEMPO_ESPERA, headers=_UA)
            if not resp.ok:
                continue
            raiz = ElementTree.fromstring(resp.content)
            for item in raiz.iter("item"):
                titulo = (item.findtext("title") or "").strip()
                if not titulo:
                    continue
                fecha = _parsear_fecha(item.findtext("pubDate") or "")
                titulares.append(Titular(titulo, fecha, fuente))
        except Exception:  # noqa: BLE001 — la red puede fallar; no debe romper.
            continue
    return titulares[:limite]


def obtener_eventos_macro() -> List[EventoMacro]:
    """Descarga el calendario económico de la semana (eventos de alto impacto)."""
    import requests

    eventos: List[EventoMacro] = []
    try:
        resp = requests.get(_CALENDARIO, timeout=_TIEMPO_ESPERA, headers=_UA)
        if not resp.ok:
            return eventos
        for e in resp.json():
            divisa = (e.get("country") or "").upper()
            impacto = (e.get("impact") or "").lower()
            fecha = None
            bruto = e.get("date")
            if bruto:
                try:
                    fecha = datetime.fromisoformat(bruto.replace("Z", "+00:00"))
                    if fecha.tzinfo is None:
                        fecha = fecha.replace(tzinfo=timezone.utc)
                    fecha = fecha.astimezone(timezone.utc)
                except ValueError:
                    fecha = None
            eventos.append(EventoMacro(e.get("title", ""), divisa, impacto, fecha))
    except Exception:  # noqa: BLE001
        return eventos
    return eventos


def eventos_alto_impacto_relevantes(eventos: List[EventoMacro]) -> List[EventoMacro]:
    """Filtra los eventos de alto impacto en divisas que afectan al oro."""
    return [
        e for e in eventos
        if e.impacto == "high" and (e.divisa in _DIVISAS_ORO or not e.divisa)
    ]
