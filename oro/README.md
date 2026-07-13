# Sistema de análisis de XAU/USD (ORO)

Base **profesional, modular y aislada** para analizar el mercado del oro
(XAU/USD) y generar oportunidades de trading de alta calidad (*setups A+*), con
la gestión del riesgo como prioridad número uno, backtesting riguroso y
aprendizaje continuo con validación anti-sobreajuste.

> Vive como paquete independiente `oro/` dentro de este repositorio. **No
> comparte ni modifica** nada del Generador de Cuadrantes.

---

## ⚠️ Aviso imprescindible

Esto es una **herramienta de análisis y apoyo a la decisión**, no un asesor
financiero ni una promesa de beneficios. El trading apalancado puede hacerte
**perder todo tu capital**. Ningún modelo predice el mercado con certeza; todos
tienen rachas de pérdidas. La probabilidad que muestra el sistema es una
**estimación**, no una garantía. Antes de arriesgar dinero real:

1. valida con **backtesting** sobre datos reales (idealmente 10+ años);
2. haz **forward test en cuenta demo** durante varios meses;
3. asume que el uso es de tu entera responsabilidad.

---

## Qué hace (y qué no)

- **Sí**: mide *ventaja estadística* por confluencia de estructura de mercado
  (SMC/ICT), indicadores de confirmación y contexto; calcula stop, objetivos y
  tamaño de posición; filtra hasta quedarse solo con setups A+; hace backtesting
  con métricas serias; entrena un modelo de probabilidad **validado
  walk-forward**; envía alertas; expone API y panel.
- **No**: no promete aciertos, no fuerza operaciones y, si no hay ventaja, lo
  dice: *«Hoy no existen operaciones con suficiente ventaja estadística.»*

## Instalación

```bash
pip install -r oro/requirements.txt   # numpy y pandas bastan para el núcleo.
```

## Uso rápido

```bash
# Demostración de extremo a extremo con datos SINTÉTICOS (sin conexión):
python -m oro.cli demo

# Analizar el estado de mercado actual y mostrar la señal (o «no hay»):
python -m oro.cli senal

# Backtest (usa --csv ruta.csv para datos reales OHLCV):
python -m oro.cli backtest --velas 8000
python -m oro.cli backtest --csv datos/xauusd_m15.csv

# Entrenar el modelo con validación walk-forward (solo se guarda si es válido):
python -m oro.cli entrenar

# API + panel de control (http://127.0.0.1:8010/oro/panel):
python -m oro.cli servir
```

### Uso como librería

```python
from oro.servicio import ServicioOro
from oro.datos import ProveedorCSV

servicio = ServicioOro(proveedor=ProveedorCSV("datos/xauusd_m15.csv"))
resultado = servicio.analizar_ahora()
if resultado.hay_operacion:
    print(resultado.signal.resumen())
else:
    print(resultado.mensaje)
```

## Estructura del paquete

| Módulo | Responsabilidad |
|--------|-----------------|
| `oro.dominio` | Modelos puros: `Candle`, `MarketSnapshot`, `Signal`, `Trade`. |
| `oro.datos` | Proveedores: sintético, CSV, y base para adaptadores reales. |
| `oro.indicadores` | EMA, SMA, RSI, ATR, MACD, ADX, Bollinger, VWAP (confirmación). |
| `oro.estructura` | Estructura de mercado / SMC: swings, BOS, CHoCH, FVG, OB, barridos. |
| `oro.features` | Ingeniería de características causales y adimensionales. |
| `oro.riesgo` | Niveles (SL/TP por ATR), tamaño de posición y guardas de no-operar. |
| `oro.senales` | Motor de confluencia y filtro de calidad A+. |
| `oro.ml` | Modelo de probabilidad + etiquetado triple barrera + walk-forward. |
| `oro.backtesting` | Motor event-driven y métricas (PF, DD, Sharpe, expectancy…). |
| `oro.notificaciones` | Consola, Telegram, email (SMTP) y webhook/push. |
| `oro.api` | API FastAPI y panel de control. |
| `oro.servicio` | Orquestación (usada por CLI y API). |

## Configuración

Todo se ajusta en `oro/config.py` o por variables de entorno `ORO_*`
(p. ej. `ORO_RIESGO_POR_OPERACION=0.005`, `ORO_CAPITAL=25000`). Valores por
defecto **conservadores**: 0,5 % de riesgo por operación, máx. 4 operaciones/día,
R:R medio mínimo 1,5, y guardas que prohíben operar con spread alto, volatilidad
extrema, mercado plano o noticia de alto impacto próxima.

Notificaciones (credenciales por entorno, nunca en el código):
`ORO_TELEGRAM_TOKEN`, `ORO_TELEGRAM_CHAT_ID`, `ORO_WEBHOOK_URL`, `ORO_SMTP_*`.

## Pruebas

```bash
pytest oro/tests -q
```

## Cómo conectar datos y brokers reales

Implementa la interfaz `oro.datos.ProveedorDatos` (métodos `historico` y
`ultima`) sobre tu fuente (MetaTrader 5, Interactive Brokers, API de datos…) y
pásasela al `ServicioOro`. El resto del sistema no cambia. La ejecución de
órdenes se deja **deliberadamente fuera** de esta base: primero valida, luego
opera en demo, y solo después conecta ejecución real.

## Estado y hoja de ruta

Consulta [`../docs/ARQUITECTURA_ORO.md`](../docs/ARQUITECTURA_ORO.md) para el
diseño completo, las decisiones técnicas justificadas y lo que queda por
integrar (feeds de noticias/macro, análisis de sentimiento de RRSS, adaptadores
de broker, reentrenamiento programado y ejecución).
