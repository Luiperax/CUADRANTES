"""Ingeniería de características.

Transforma las velas y los indicadores en un conjunto de *features* numéricas,
normalizadas y sin fugas temporales, que alimentan tanto al motor de confluencia
como al modelo de aprendizaje automático. La misma función se usa en
entrenamiento y en producción para garantizar coherencia.
"""

from __future__ import annotations

from .construccion import construir_features, COLUMNAS_FEATURES

__all__ = ["construir_features", "COLUMNAS_FEATURES"]
