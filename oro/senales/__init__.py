"""Motor de señales: confluencia y filtro de calidad A+.

Integra estructura de mercado, indicadores (confirmación), contexto (sesión,
volatilidad, spread, noticias) y —si está entrenado— el modelo de probabilidad,
para decidir si existe una oportunidad *A+*. Si no la hay, lo dice con claridad
en lugar de forzar una operación.
"""

from __future__ import annotations

from .motor import MotorSenales, ResultadoAnalisis

__all__ = ["MotorSenales", "ResultadoAnalisis"]
