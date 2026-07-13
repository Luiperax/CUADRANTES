"""Gestión de riesgo: la prioridad número uno del sistema.

Aquí se calcula, de forma determinista y auditable, cuánto arriesgar, dónde
colocar el stop y los objetivos, y cuándo NO se debe operar bajo ninguna
circunstancia. Ninguna señal se emite sin pasar por estas comprobaciones.
"""

from __future__ import annotations

from .gestion import (
    NivelesOperacion,
    calcular_niveles,
    dimensionar_posicion,
    evaluar_guardas,
)

__all__ = [
    "NivelesOperacion",
    "calcular_niveles",
    "dimensionar_posicion",
    "evaluar_guardas",
]
