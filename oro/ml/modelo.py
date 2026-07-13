"""Modelo de probabilidad de éxito.

Usa Gradient Boosting sobre histogramas (``HistGradientBoostingClassifier``):
rápido, robusto, admite valores ausentes de forma nativa (útil por el
calentamiento de indicadores) y con regularización para contener el sobreajuste.

Si scikit-learn no está instalado, el sistema sigue funcionando sin modelo (el
motor de señales usa entonces la probabilidad derivada de la confluencia).
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..features import COLUMNAS_FEATURES

try:  # scikit-learn es opcional.
    from sklearn.ensemble import HistGradientBoostingClassifier
    SKLEARN_DISPONIBLE = True
except ImportError:  # pragma: no cover
    HistGradientBoostingClassifier = None  # type: ignore
    SKLEARN_DISPONIBLE = False


class ModeloProbabilidad:
    """Envoltorio del clasificador con una interfaz estable para el resto del sistema."""

    def __init__(self, **hiperparametros) -> None:
        if not SKLEARN_DISPONIBLE:
            raise RuntimeError(
                "scikit-learn no está instalado; el modelo ML no está disponible."
            )
        # Hiperparámetros conservadores (menos capacidad => menos sobreajuste).
        defaults = dict(
            max_depth=3,
            learning_rate=0.05,
            max_iter=300,
            l2_regularization=1.0,
            min_samples_leaf=50,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
        )
        defaults.update(hiperparametros)
        self._clf = HistGradientBoostingClassifier(**defaults)
        self._entrenado = False
        self._prob_base = 0.5

    def entrenar(self, X: pd.DataFrame, y: pd.Series) -> "ModeloProbabilidad":
        X = X[COLUMNAS_FEATURES]
        mask = y.notna()
        X, y = X[mask], y[mask].astype(int)
        if len(np.unique(y)) < 2:
            raise ValueError("Se necesitan ambas clases (éxito/fracaso) para entrenar.")
        self._clf.fit(X.to_numpy(), y.to_numpy())
        self._prob_base = float(y.mean())
        self._entrenado = True
        return self

    def predecir_proba(self, X: pd.DataFrame) -> np.ndarray:
        """P(éxito) para cada fila. Antes de entrenar devuelve la base (0.5)."""
        if not self._entrenado:
            return np.full(len(X), self._prob_base)
        X = X[COLUMNAS_FEATURES]
        return self._clf.predict_proba(X.to_numpy())[:, 1]

    @property
    def entrenado(self) -> bool:
        return self._entrenado

    def guardar(self, ruta: str | Path) -> None:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with open(ruta, "wb") as fh:
            pickle.dump({"clf": self._clf, "prob_base": self._prob_base,
                         "entrenado": self._entrenado}, fh)

    @classmethod
    def cargar(cls, ruta: str | Path) -> "ModeloProbabilidad":
        with open(ruta, "rb") as fh:
            datos = pickle.load(fh)
        modelo = cls.__new__(cls)  # evita reconstruir hiperparámetros.
        modelo._clf = datos["clf"]
        modelo._prob_base = datos["prob_base"]
        modelo._entrenado = datos["entrenado"]
        return modelo
