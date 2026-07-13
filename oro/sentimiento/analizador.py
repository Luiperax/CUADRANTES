"""Agregación de sentimiento y contexto informativo del oro.

Convierte titulares sueltos en una señal robusta:

* Pondera cada titular por su *relevancia* (nº de expresiones del léxico que
  activa) y por su *frescura* (las noticias recientes pesan más).
* Exige un mínimo de titulares con señal para no reaccionar al ruido de uno solo.
* Detecta si hay un evento macro de alto impacto dentro de una ventana temporal,
  en cuyo caso marca ``riesgo_noticia_alta`` para que el sistema NO opere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional

from .fuentes import (
    EventoMacro,
    Titular,
    eventos_alto_impacto_relevantes,
    obtener_eventos_macro,
    obtener_titulares,
)
from .lexico import puntuar_texto


@dataclass(slots=True)
class ContextoInformativo:
    """Resultado del análisis informativo en un instante."""

    sentimiento: Optional[float]        # [-1, 1] orientado al oro, o None si no hay señal.
    n_titulares: int
    n_con_senal: int
    riesgo_noticia_alta: bool
    proximo_evento: Optional[str] = None
    minutos_al_evento: Optional[int] = None
    titulares_destacados: List[str] = field(default_factory=list)

    def resumen(self) -> str:
        if self.sentimiento is None:
            base = "Sentimiento: sin señal suficiente"
        else:
            etiqueta = ("alcista" if self.sentimiento > 0.15
                        else "bajista" if self.sentimiento < -0.15 else "neutro")
            base = f"Sentimiento oro: {self.sentimiento:+.2f} ({etiqueta}), {self.n_con_senal}/{self.n_titulares} titulares"
        if self.riesgo_noticia_alta and self.proximo_evento:
            base += f" | ⚠ evento alto impacto en ~{self.minutos_al_evento} min: {self.proximo_evento}"
        return base


class AnalizadorSentimiento:
    def __init__(
        self,
        min_titulares_senal: int = 3,
        ventana_evento_min: int = 60,
        fuente_titulares: Callable[[], List[Titular]] = obtener_titulares,
        fuente_eventos: Callable[[], List[EventoMacro]] = obtener_eventos_macro,
    ) -> None:
        # Las fuentes se inyectan para poder probar sin red.
        self._min_senal = min_titulares_senal
        self._ventana_evento = ventana_evento_min
        self._fuente_titulares = fuente_titulares
        self._fuente_eventos = fuente_eventos

    def analizar(self, ahora: Optional[datetime] = None) -> ContextoInformativo:
        ahora = ahora or datetime.now(timezone.utc)
        titulares = self._fuente_titulares()
        sentimiento, n_senal, destacados = self._agregar(titulares, ahora)
        riesgo, evento, minutos = self._riesgo_evento(ahora)
        return ContextoInformativo(
            sentimiento=sentimiento,
            n_titulares=len(titulares),
            n_con_senal=n_senal,
            riesgo_noticia_alta=riesgo,
            proximo_evento=evento,
            minutos_al_evento=minutos,
            titulares_destacados=destacados,
        )

    def _agregar(self, titulares: List[Titular], ahora: datetime):
        suma_pesos = 0.0
        suma_valores = 0.0
        n_senal = 0
        con_puntuacion = []
        for t in titulares:
            valor, coincidencias = puntuar_texto(t.titulo)
            if coincidencias == 0:
                continue
            n_senal += 1
            # Peso por relevancia (coincidencias) y frescura (decae con las horas).
            peso = float(coincidencias)
            if t.fecha is not None:
                horas = max(0.0, (ahora - t.fecha).total_seconds() / 3600.0)
                peso *= 0.5 ** (horas / 12.0)  # se reduce a la mitad cada 12 h.
            suma_valores += valor * peso
            suma_pesos += peso
            con_puntuacion.append((abs(valor) * peso, t.titulo))

        if n_senal < self._min_senal or suma_pesos <= 0:
            return None, n_senal, []
        # Media ponderada, normalizada de [-2, 2] a [-1, 1].
        sentimiento = max(-1.0, min(1.0, (suma_valores / suma_pesos) / 2.0))
        con_puntuacion.sort(reverse=True)
        destacados = [titulo for _, titulo in con_puntuacion[:3]]
        return round(sentimiento, 3), n_senal, destacados

    def _riesgo_evento(self, ahora: datetime):
        eventos = eventos_alto_impacto_relevantes(self._fuente_eventos())
        proximo = None
        minutos_min = None
        for e in eventos:
            if e.fecha is None:
                continue
            delta = (e.fecha - ahora).total_seconds() / 60.0
            # Ventana simétrica: justo antes y poco después del dato.
            if -15 <= delta <= self._ventana_evento:
                if minutos_min is None or abs(delta) < abs(minutos_min):
                    minutos_min = int(delta)
                    proximo = e.titulo
        return (proximo is not None), proximo, minutos_min
