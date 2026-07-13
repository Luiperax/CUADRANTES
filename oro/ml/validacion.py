"""Validación walk-forward con embargo temporal.

Es la salvaguarda central contra el sobreajuste. El histórico se divide en
bloques cronológicos; el modelo se entrena con el pasado y se evalúa siempre con
el futuro inmediato **dejando un hueco (embargo)** entre entrenamiento y prueba
para que las etiquetas solapadas no filtren información.

Se reporta el AUC dentro y fuera de muestra: si el de entrenamiento es muy
superior al de prueba, hay sobreajuste y el modelo NO debe aceptarse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
import pandas as pd

from .modelo import ModeloProbabilidad


def _auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """AUC ROC por el estadístico de Mann–Whitney (sin dependencias extra)."""
    orden = np.argsort(y_score, kind="mergesort")
    y_true = y_true[orden]
    n_pos = int(y_true.sum())
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    rangos = np.empty(len(y_score))
    y_sorted = np.sort(y_score)
    # Rangos con promedio para empates.
    i = 0
    r = 1
    while i < len(y_sorted):
        j = i
        while j < len(y_sorted) and y_sorted[j] == y_sorted[i]:
            j += 1
        rango_medio = (r + (r + (j - i) - 1)) / 2.0
        rangos[i:j] = rango_medio
        r += (j - i)
        i = j
    suma_rangos_pos = rangos[y_true == 1].sum()
    return (suma_rangos_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


@dataclass(slots=True)
class ResultadoWalkForward:
    auc_train: List[float] = field(default_factory=list)
    auc_test: List[float] = field(default_factory=list)
    n_test: List[int] = field(default_factory=list)

    @property
    def auc_test_medio(self) -> float:
        vals = [a for a in self.auc_test if not np.isnan(a)]
        return float(np.mean(vals)) if vals else float("nan")

    @property
    def auc_train_medio(self) -> float:
        vals = [a for a in self.auc_train if not np.isnan(a)]
        return float(np.mean(vals)) if vals else float("nan")

    @property
    def brecha_sobreajuste(self) -> float:
        """Diferencia AUC(train) − AUC(test). Cuanto mayor, más sobreajuste."""
        return self.auc_train_medio - self.auc_test_medio

    def aceptable(self, auc_min: float = 0.53, brecha_max: float = 0.15) -> bool:
        """Criterio de aceptación: ventaja fuera de muestra y sin sobreajuste severo."""
        return (
            not np.isnan(self.auc_test_medio)
            and self.auc_test_medio >= auc_min
            and self.brecha_sobreajuste <= brecha_max
        )

    def resumen(self) -> str:
        return (
            f"AUC test {self.auc_test_medio:.3f} | AUC train {self.auc_train_medio:.3f} | "
            f"brecha {self.brecha_sobreajuste:+.3f} | folds {len(self.auc_test)} | "
            f"{'ACEPTABLE' if self.aceptable() else 'RECHAZADO (revisar sobreajuste/ventaja)'}"
        )


def walk_forward(
    X: pd.DataFrame,
    y: pd.Series,
    n_folds: int = 5,
    embargo: int = 48,
) -> ResultadoWalkForward:
    """Ejecuta la validación walk-forward.

    ``embargo`` es el número de velas que se descartan entre el fin del bloque de
    entrenamiento y el inicio del de prueba (debe ser >= horizonte de etiquetado).
    """
    mask = y.notna()
    X, y = X[mask], y[mask].astype(int)
    n = len(X)
    resultado = ResultadoWalkForward()
    if n < (n_folds + 1) * 100:
        return resultado

    tam_fold = n // (n_folds + 1)
    for f in range(1, n_folds + 1):
        fin_train = f * tam_fold - embargo
        ini_test = f * tam_fold
        fin_test = min((f + 1) * tam_fold, n)
        if fin_train <= 100 or fin_test - ini_test < 30:
            continue

        X_tr, y_tr = X.iloc[:fin_train], y.iloc[:fin_train]
        X_te, y_te = X.iloc[ini_test:fin_test], y.iloc[ini_test:fin_test]
        if len(np.unique(y_tr)) < 2 or len(np.unique(y_te)) < 2:
            continue

        modelo = ModeloProbabilidad().entrenar(X_tr, y_tr)
        p_tr = modelo.predecir_proba(X_tr)
        p_te = modelo.predecir_proba(X_te)
        resultado.auc_train.append(_auc(y_tr.to_numpy(), p_tr))
        resultado.auc_test.append(_auc(y_te.to_numpy(), p_te))
        resultado.n_test.append(len(y_te))

    return resultado
