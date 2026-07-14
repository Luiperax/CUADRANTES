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
# ⭐ MODO EN VIVO: vigila el mercado real, avisa cuándo ENTRAR y cuándo SALIR
# (2–4 señales/día), con precio real (Yahoo) y sentimiento de prensa:
python -m oro.cli vivo                      # notifica por consola.
python -m oro.cli vivo --intervalo 900      # revisa cada 15 min.

# Ver el sentimiento de prensa y el riesgo de noticias macro AHORA:
python -m oro.cli sentimiento

# Analizar el estado de mercado actual y mostrar la señal (o «no hay»):
python -m oro.cli senal --sintetico         # offline (datos de prueba).

# Backtest (usa --csv ruta.csv para datos reales OHLCV):
python -m oro.cli backtest --sintetico --velas 8000
python -m oro.cli backtest --csv datos/xauusd_m15.csv

# Entrenar el modelo con validación walk-forward (solo se guarda si es válido):
python -m oro.cli entrenar --sintetico

# Demostración de extremo a extremo con datos SINTÉTICOS (sin conexión):
python -m oro.cli demo

# API + panel de control bajo demanda (http://127.0.0.1:8010/oro/panel):
python -m oro.cli servir

# ⭐ PANEL EN VIVO para el móvil: motor en segundo plano + notificaciones:
python -m oro.cli servir --vivo            # abre /oro/panel (se refresca solo)
```

### Acceso desde el móvil

Dos formas (compatibles entre sí), explicadas paso a paso en
[`DESPLIEGUE_MOVIL.md`](DESPLIEGUE_MOVIL.md):

- **Avisos por Telegram**: recibes cada entrada/salida en el móvil. Solo necesitas
  un bot (`ORO_TELEGRAM_TOKEN` + `ORO_TELEGRAM_CHAT_ID`) y dejar el motor
  corriendo (`python -m oro.cli vivo`).
- **En la nube SIN Render (GitHub Actions)**: el workflow
  [`.github/workflows/oro-alertas.yml`](../.github/workflows/oro-alertas.yml)
  ejecuta `python -m oro.alerta` cada ~15 min en los servidores de GitHub y te
  avisa por Telegram. Sin tarjeta ni servidor propio; el estado (operaciones
  abiertas) se guarda en el repo para seguir las salidas entre ejecuciones.
- **Panel web con URL fija (nube)**: despliega `uvicorn oro.web:app` en Render
  (o cualquier VPS) y abre la URL desde el móvil. Muestra precio, sentimiento,
  operaciones abiertas y eventos en vivo; protégelo con `ORO_PANEL_CLAVE`.
  Plantilla lista en [`deploy/render.yaml`](deploy/render.yaml).

### Notificaciones al móvil

El modo `vivo` envía cada evento (entrada, mover stop, objetivo, cierre) por los
canales que tengas configurados. Para recibirlos en el móvil, define las
variables de entorno antes de arrancar (nunca van en el código):

```bash
export ORO_TELEGRAM_TOKEN="123456:AA..."   # bot de Telegram (@BotFather)
export ORO_TELEGRAM_CHAT_ID="987654321"    # tu chat_id
# opcionales:
export ORO_WEBHOOK_URL="https://..."       # push (FCM), WhatsApp Business API, Slack…
export ORO_SMTP_HOST="smtp.gmail.com"; export ORO_SMTP_USUARIO="tu@correo"; export ORO_SMTP_CLAVE="..."; export ORO_SMTP_DESTINO="tu@correo"
python -m oro.cli vivo
```

### Qué fuentes analiza de verdad

- **Precio real del oro**: Yahoo Finance (futuro `GC=F`, proxy del XAU/USD spot).
- **Prensa financiera**: Yahoo Finance RSS + Google News (agrega a Reuters,
  Bloomberg, FXStreet, Investing, etc.) → sentimiento orientado al oro.
- **Calendario económico**: ForexFactory → detecta FED/IPC/PCE/NFP inminentes y
  **bloquea entradas** en la ventana del evento (riesgo de spike).
- **Limitación honesta**: X (Twitter) y Reddit requieren API de pago o están
  bloqueados en muchos entornos; su cobertura directa queda como conector a
  añadir. La prensa agregada ya recoge buena parte de esa información.

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
| `oro.sentimiento` | Prensa (Yahoo/Google News) + calendario macro → sentimiento y riesgo de noticia. |
| `oro.vivo` | Motor en vivo: gestor de salidas y runner (entradas + salidas + avisos). |
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
