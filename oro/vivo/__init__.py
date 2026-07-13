"""Ejecución en vivo: entradas, salidas y notificaciones.

Convierte el motor de análisis en un servicio que vigila el mercado en un bucle,
genera entre 2 y 4 señales A+ al día y **gestiona cada operación hasta su
salida**, avisando en cada evento: entrada, mover el stop a break-even, objetivos
alcanzados y cierre.

* :class:`GestorOperaciones` — máquina de estados de una operación abierta.
* :class:`RunnerVivo` — bucle que compone datos + sentimiento + señales + gestión
  + notificaciones.
"""

from __future__ import annotations

from .gestor import EventoGestion, GestorOperaciones
from .runner import CicloResultado, RunnerVivo

__all__ = ["EventoGestion", "GestorOperaciones", "CicloResultado", "RunnerVivo"]
