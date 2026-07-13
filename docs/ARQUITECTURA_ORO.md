# Arquitectura del sistema de XAU/USD (ORO)

Documento de diseño del paquete `oro/`. Explica **qué** se ha construido, **por
qué** cada decisión técnica y **qué falta** para llevarlo a producción real.

> Recordatorio: es una herramienta de análisis, no un asesor financiero. Ningún
> sistema garantiza aciertos ni elimina el riesgo. Toda estrategia debe validarse
> con backtesting y en demo antes de operar con dinero real.

---

## 1. Principios de diseño

1. **La gestión del riesgo manda.** Ninguna señal se emite sin pasar por las
   guardas de riesgo y el dimensionado que fija la pérdida máxima por operación.
2. **Selectividad sobre frecuencia.** Es preferible 1 operación excelente a 10
   mediocres. El sistema puede —y debe— decir «hoy no hay ventaja».
3. **Transparencia.** Cada señal explica sus motivos a favor, en contra y sus
   riesgos. La probabilidad es una estimación etiquetada como tal.
4. **Causalidad estricta.** En cada instante solo se usa información pasada.
   Verificado con pruebas específicas de no-look-ahead.
5. **Anti-sobreajuste.** El modelo se acepta solo si demuestra ventaja *fuera de
   muestra* (walk-forward con embargo) y sin brecha train/test excesiva.
6. **Capas desacopladas.** Dependencias en una sola dirección
   (dominio ← lógica ← infraestructura) para poder probar y sustituir por piezas.

## 2. Flujo de datos

```
Proveedor de datos (sintético / CSV / adaptador real)
        │  OHLCV (DatetimeIndex UTC, validado)
        ▼
Indicadores  ──┐
Estructura/SMC ─┼─► Features (causales, adimensionales)
Contexto/sesión ┘        │
        │                ▼
        │        Modelo de probabilidad (opcional, validado walk-forward)
        ▼                │
Motor de confluencia ◄───┘
        │  puntuación + probabilidad + confianza
        ▼
Filtro de calidad A+  +  Gestión de riesgo (SL/TP/size + guardas)
        │
        ├─► Señal explicada  ─► Notificaciones (Telegram/email/webhook/push)
        └─► «Hoy no hay ventaja»
```

El mismo camino se usa en backtesting (histórico, vela a vela) y en vivo
(última vela), garantizando coherencia entre lo que se prueba y lo que se opera.

## 3. Decisiones técnicas (justificadas)

- **Python + numpy/pandas** para el núcleo: estándar de facto en cuantitativo,
  vectorizado y con ecosistema de datos/ML. El núcleo no depende de nada más.
- **Estructura de mercado como motor direccional, indicadores como
  confirmación.** Los indicadores son retrasados; la estructura (swings, BOS,
  CHoCH, FVG, order blocks, barridos de liquidez) describe la intención del
  precio. Los indicadores solo suman/restan convicción, nunca deciden solos.
- **Stops y objetivos por ATR** (volatilidad): el riesgo se adapta al régimen de
  mercado. El **tamaño de posición** se calcula para arriesgar un % fijo del
  capital, de modo que la pérdida máxima por operación es constante y conocida.
- **HistGradientBoostingClassifier** para la probabilidad: rápido, robusto a
  escalas, admite `NaN` de forma nativa (útil en el calentamiento de
  indicadores) y regularizable. Alternativas equivalentes: LightGBM/XGBoost.
- **Etiquetado triple barrera** (López de Prado, simplificado): la etiqueta es
  «¿el objetivo se alcanza antes que el stop?», es decir, exactamente lo que el
  sistema intenta lograr. Coherencia total entre entrenamiento y operativa.
- **Walk-forward con embargo** en vez de validación cruzada aleatoria: en series
  temporales, barajar filtra el futuro en el pasado. El embargo (≥ horizonte de
  etiquetado) evita el solape de etiquetas entre train y test.
- **Backtester conservador**: entrada a la apertura de la vela siguiente, stop
  evaluado antes que el objetivo dentro de la vela (hipótesis pesimista),
  break-even tras TP1, una posición a la vez y tope diario. Reduce el sesgo
  optimista habitual en backtests ingenuos.
- **Notificaciones desacopladas** tras una interfaz: añadir un canal no toca la
  lógica. Credenciales solo por variables de entorno.

## 4. Métricas del backtest

`Profit Factor`, `Win Rate`, `Expectancy` (R media), `Sharpe` (anualizado
aprox.), `Max Drawdown`, rentabilidad total y `CAGR`, número de operaciones y
rachas máximas de ganancias/pérdidas. Todas se calculan sobre la curva de
capital compuesta a partir del PnL real por operación.

## 5. Seguridad

- Sin credenciales en el código: todo por entorno (`ORO_*`).
- La ejecución de órdenes reales está **fuera** de esta base por diseño: se
  entrega análisis y señales; conectar un broker es un paso posterior y deliberado.
- Envíos de red con *timeout* corto y tolerancia a fallos por canal.

## 6. Estado actual vs. hoja de ruta

### Implementado y probado (37 pruebas en verde)
- Dominio, configuración y validación.
- Indicadores técnicos (con pruebas de no-look-ahead).
- Estructura de mercado / SMC (swings, BOS/CHoCH, FVG, order blocks, barridos).
- Ingeniería de features causales.
- Gestión de riesgo (niveles ATR, dimensionado, guardas de no-operar).
- Motor de confluencia y filtro A+ (con salida «no hay ventaja»).
- Backtester event-driven y métricas completas.
- Modelo de probabilidad + etiquetado + **walk-forward que rechaza el
  sobreajuste** (demostrado sobre datos sintéticos).
- Notificaciones (consola, Telegram, email, webhook/push).
- API FastAPI + panel de control + CLI.
- Proveedor sintético (offline, reproducible) y proveedor CSV.

### Datos reales y ejecución en vivo (ya integrados)
- **Precio real del oro**: `oro.datos.ProveedorYahoo` (Yahoo Finance, futuro
  `GC=F` como proxy del spot XAU/USD), sobre la interfaz `ProveedorDatos`.
- **Sentimiento de prensa**: `oro.sentimiento` con Yahoo Finance RSS + Google
  News, léxico orientado al oro, ponderación por relevancia y frescura, y umbral
  mínimo de titulares para filtrar ruido → `MarketSnapshot.sentimiento`.
- **Calendario económico**: ForexFactory; detecta eventos de alto impacto
  (FED/IPC/PCE/NFP) inminentes y activa `riesgo_noticia_alta` para no operar.
- **Motor en vivo**: `oro.vivo.RunnerVivo` compone datos + sentimiento + señales
  + gestión; `oro.vivo.GestorOperaciones` decide y notifica las **salidas**
  (TP parciales, break-even tras TP1, stop, cierre). Tope de 2–4 señales/día.

### Pendiente para producción real (integraciones externas)
Estas piezas requieren cuentas, claves y/o datos de pago:

- **Feed del bróker**: MetaTrader 5 / Interactive Brokers con spread real y 10+
  años de histórico para el backtest largo (Yahoo da meses, no décadas).
- **X (Twitter) / Reddit**: conectores directos (API de pago) para ampliar el
  sentimiento más allá de la prensa agregada; misma interfaz de `fuentes`.
- **Macro cuantitativo**: FRED/BCE/FED (tipos, inflación), DXY y Treasury como
  features numéricas ponderadas, además del calendario ya integrado.
- **Reentrenamiento programado**: job periódico que reetiqueta, revalida
  walk-forward y solo promociona el modelo si supera los umbrales.
- **Ejecución de órdenes**: capa con doble confirmación y modo demo por defecto,
  solo tras validación en demo prolongada.
- **Persistencia analítica**: PostgreSQL + Redis; hoy se persiste en JSONL.

## 7. Cómo extender

- **Nueva fuente de datos**: implementa `oro.datos.ProveedorDatos`.
- **Nuevo canal de aviso**: implementa `oro.notificaciones.Notificador`.
- **Nuevo factor de confluencia**: añádelo en `MotorSenales._puntuar` con su peso.
- **Nuevas features**: amplía `oro.features.construccion` y `COLUMNAS_FEATURES`.
