"""Aprendizaje automático: probabilidad de éxito con validación anti-sobreajuste.

El modelo NO predice el precio. Estima la **probabilidad de que una operación
propuesta por la estrategia termine en beneficio**, a partir del contexto
(features causales). Esa probabilidad es una de las entradas del filtro A+.

Principios para evitar el sobreajuste (*overfitting*), el mayor enemigo del
trading cuantitativo:

* Etiquetado por *triple barrera* coherente con la gestión real de riesgo.
* Validación **walk-forward** con *embargo/purga* temporal: nunca se evalúa con
  datos cercanos a los de entrenamiento.
* Se compara el rendimiento dentro y fuera de muestra; una brecha grande es
  señal de sobreajuste y bloquea la aceptación del modelo.
"""

from __future__ import annotations

from .etiquetado import generar_etiquetas
from .modelo import ModeloProbabilidad, SKLEARN_DISPONIBLE
from .validacion import ResultadoWalkForward, walk_forward

__all__ = [
    "generar_etiquetas",
    "ModeloProbabilidad",
    "SKLEARN_DISPONIBLE",
    "ResultadoWalkForward",
    "walk_forward",
]
