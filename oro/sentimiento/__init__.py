"""Análisis de sentimiento de mercado a partir de noticias y prensa financiera.

Combina fuentes **públicas y gratuitas** que sí son accesibles:

* Titulares de prensa financiera (Yahoo Finance RSS, Google News RSS).
* Calendario económico de alto impacto (ForexFactory) para FED, IPC, NFP, etc.

y produce dos señales que enriquecen la decisión del sistema:

* ``sentimiento`` en ``[-1, 1]`` (negativo = bajista para el oro, positivo =
  alcista), específico del oro (un dólar fuerte / tipos altos es bajista para el
  oro; inflación / refugio / geopolítica es alcista).
* ``riesgo_noticia_alta``: hay un evento macro de alto impacto inminente y, por
  tanto, NO se debe operar (riesgo de spike).

Honestidad sobre el alcance: X (Twitter) y Reddit requieren API de pago o están
bloqueados en muchos entornos; aquí se cubre la **prensa financiera agregada**
(que ya recoge buena parte de esas fuentes). El diseño es extensible: añadir un
conector de X/Reddit es implementar una función que devuelva titulares.
"""

from __future__ import annotations

from .analizador import AnalizadorSentimiento, ContextoInformativo
from .lexico import puntuar_texto

__all__ = ["AnalizadorSentimiento", "ContextoInformativo", "puntuar_texto"]
