"""Léxico de sentimiento específico para el oro (XAU/USD).

El oro no reacciona como una acción: sube con la incertidumbre, la inflación, la
debilidad del dólar y los recortes de tipos; y baja con dólar fuerte, tipos
altos y apetito por el riesgo. Por eso el léxico está *orientado al oro*, no es
un analizador de sentimiento genérico.

Método: puntuación por diccionario ponderado sobre el titular (rápido, sin
dependencias, auditable). Es una aproximación; para producción puede sustituirse
por un modelo NLP (FinBERT u otro) manteniendo la misma interfaz ``puntuar_texto``.
"""

from __future__ import annotations

import re
from typing import Dict, Tuple

# Peso positivo = alcista para el oro; negativo = bajista. Rango orientativo [-2, 2].
_LEXICO: Dict[str, float] = {
    # --- Alcista para el oro ---
    "inflation": 1.2, "inflación": 1.2, "cpi surge": 1.5, "stagflation": 1.6,
    "rate cut": 1.6, "rate cuts": 1.6, "dovish": 1.4, "recesión": 1.3, "recession": 1.3,
    "safe haven": 1.6, "safe-haven": 1.6, "refugio": 1.5, "haven demand": 1.5,
    "weak dollar": 1.4, "dollar falls": 1.3, "dollar slips": 1.2, "dólar débil": 1.4,
    "geopolitical": 1.3, "war": 1.2, "guerra": 1.2, "conflict": 1.0, "tension": 0.9,
    "central bank buying": 1.5, "record high": 1.2, "all-time high": 1.3, "máximo histórico": 1.3,
    "gold rallies": 1.6, "gold surges": 1.6, "gold jumps": 1.5, "gold climbs": 1.3,
    "gold rises": 1.1, "bullish gold": 1.6, "gold soars": 1.6, "sube el oro": 1.4,
    "uncertainty": 0.9, "incertidumbre": 0.9, "crisis": 1.1, "debt ceiling": 1.0,
    "fed pauses": 1.2, "yields fall": 1.1, "falling yields": 1.1,

    # --- Bajista para el oro ---
    "rate hike": -1.6, "rate hikes": -1.6, "hawkish": -1.4, "subida de tipos": -1.5,
    "strong dollar": -1.4, "dollar rises": -1.2, "dollar surges": -1.4, "dólar fuerte": -1.4,
    "risk-on": -1.1, "risk appetite": -1.0, "rally in stocks": -0.9,
    "yields rise": -1.2, "rising yields": -1.2, "higher yields": -1.2, "treasury yields jump": -1.3,
    "gold falls": -1.5, "gold drops": -1.5, "gold slips": -1.2, "gold tumbles": -1.6,
    "gold plunges": -1.6, "bearish gold": -1.6, "gold retreats": -1.2, "cae el oro": -1.4,
    "profit taking": -0.8, "sell-off": -1.0, "selloff": -1.0, "correction": -0.7,
    "fed hikes": -1.4, "hot inflation eases": -0.6, "disinflation": -0.9,
}

# Eventos macro que, si son inminentes, elevan el riesgo (no operar cerca).
EVENTOS_ALTO_IMPACTO = (
    "fomc", "fed interest rate", "federal funds", "cpi", "core cpi", "pce",
    "non-farm", "nonfarm", "nfp", "unemployment rate", "ecb interest rate",
    "powell", "lagarde", "gdp", "ppi",
)

_PALABRA = re.compile(r"[a-záéíóúñ0-9\-]+", re.IGNORECASE)


def puntuar_texto(texto: str) -> Tuple[float, int]:
    """Puntúa un texto (titular). Devuelve ``(puntuación, nº de coincidencias)``.

    La puntuación es la suma de pesos de las expresiones encontradas, acotada a
    ``[-2, 2]``. ``nº de coincidencias`` sirve para ponderar por relevancia y
    descartar titulares sin señal (ruido).
    """
    if not texto:
        return 0.0, 0
    t = " " + texto.lower() + " "
    total = 0.0
    coincidencias = 0
    for expresion, peso in _LEXICO.items():
        if expresion in t:
            total += peso
            coincidencias += 1
    total = max(-2.0, min(2.0, total))
    return total, coincidencias


def es_evento_alto_impacto(titulo: str) -> bool:
    t = (titulo or "").lower()
    return any(ev in t for ev in EVENTOS_ALTO_IMPACTO)
