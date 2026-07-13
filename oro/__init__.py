"""
Sistema de análisis de XAU/USD (ORO)
====================================

Paquete profesional, modular y aislado para el análisis del mercado del oro
(XAU/USD) y la generación de oportunidades de trading de alta calidad (*setups
A+*), con gestión de riesgo estricta, backtesting riguroso y aprendizaje
continuo con validación anti-sobreajuste.

AVISO IMPORTANTE (leer siempre)
-------------------------------
Este software es una herramienta de ANÁLISIS y APOYO A LA DECISIÓN. **No es un
asesor financiero ni una garantía de resultados.** El trading con apalancamiento
conlleva un riesgo elevado de pérdida del capital. Ningún modelo —por avanzado
que sea— puede predecir el mercado con certeza; todos atraviesan rachas de
pérdidas. Toda estrategia debe validarse con *backtesting* y en cuenta demo
durante meses antes de arriesgar dinero real. El uso de este software es
responsabilidad exclusiva del usuario.

Diseño
------
El paquete está deliberadamente separado en capas con dependencias en una sola
dirección (dominio ← lógica ← infraestructura), de modo que cada módulo se pueda
probar de forma aislada y sustituir sin afectar al resto:

    oro.dominio         Modelos puros (Candle, Signal, Trade). Sin dependencias.
    oro.datos           Proveedores de datos (sintético, CSV, adaptadores).
    oro.indicadores     Indicadores técnicos (confirmación, nunca decisión).
    oro.estructura      Estructura de mercado / Smart Money Concepts.
    oro.features        Ingeniería de características para el modelo y el motor.
    oro.riesgo          Gestión de riesgo y dimensionado de posición.
    oro.senales         Motor de confluencia y filtro de calidad A+.
    oro.ml              Modelo de probabilidad con validación walk-forward.
    oro.backtesting     Motor de backtest event-driven y métricas.
    oro.notificaciones  Envío de alertas (Telegram, email, webhook, consola).
    oro.api             API FastAPI y panel de control.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
