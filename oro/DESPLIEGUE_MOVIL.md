# Usar el sistema de XAU/USD desde el móvil

Hay dos formas de tenerlo en el móvil. Puedes usar una o las dos a la vez.

> Recordatorio: es una herramienta de análisis, no asesoramiento financiero. La
> probabilidad es una estimación, no una garantía. Prueba en demo antes de
> arriesgar dinero real.

---

## Requisito común: el motor debe estar encendido en algún sitio

El programa tiene que estar ejecutándose para vigilar el mercado. Puede ser:

- **Tu PC** (mientras esté encendido), o
- **La nube** (funciona sin tu PC, siempre disponible) → ver Opción B.

---

## Opción A — Avisos por Telegram (lo más simple)

Recibes en el móvil cada entrada y cada salida (mover stop, objetivo, cierre).

### 1. Crea un bot de Telegram (2 minutos)
1. En Telegram, abre **@BotFather** → `/newbot` → elige un nombre. Te da un
   **token** tipo `123456789:AAE...`.
2. Abre un chat con tu nuevo bot y envíale cualquier mensaje (p. ej. "hola").
3. Consigue tu **chat_id**: abre en el navegador
   `https://api.telegram.org/bot<TU_TOKEN>/getUpdates` y busca
   `"chat":{"id":123456789,...}`. Ese número es tu `chat_id`.

### 2. Arranca el motor con tus claves
```bash
export ORO_TELEGRAM_TOKEN="123456789:AAE..."
export ORO_TELEGRAM_CHAT_ID="123456789"
python -m oro.cli vivo
```
Listo: los avisos llegan al móvil en segundos. (Cierra la terminal = se detiene;
para 24/7 usa la nube, Opción B.)

---

## Opción C — En la nube SIN Render (GitHub Actions) ⭐ recomendada si no quieres Render

Usa algo que **ya tienes**: tu repositorio de GitHub. GitHub ejecuta el programa
cada ~15 min en sus servidores y te avisa por Telegram cuándo entrar y salir.
**Sin Render, sin tarjeta, sin servidor que mantener.** Ya está todo listo en el
repo (workflow `.github/workflows/oro-alertas.yml` + `python -m oro.alerta`).

Puesta en marcha (una vez):
1. **Crea el bot de Telegram** y consigue `token` y `chat_id` (ver Opción A, punto 1).
2. **Fusiona esta rama en `main`.** Importante: las tareas programadas de GitHub
   solo se ejecutan desde la rama por defecto.
3. En GitHub: **Settings → Secrets and variables → Actions → New repository
   secret**, y crea dos secretos:
   - `ORO_TELEGRAM_TOKEN`
   - `ORO_TELEGRAM_CHAT_ID`
4. En **Settings → Actions → General**, confirma que Actions está habilitado.
   (Opcional: en la pestaña **Actions → Alertas XAU/USD → Run workflow** puedes
   lanzarlo a mano para probar sin esperar.)

A partir de ahí, recibes los avisos en el móvil. El programa recuerda tus
operaciones abiertas entre ejecuciones guardando el estado en el propio repo
(`oro_estado.json`), así que las salidas (mover stop, objetivos, cierre) se
siguen correctamente.

Limitaciones honestas:
- GitHub puede **retrasar** la tarea varios minutos si sus servidores están
  cargados; no es un tick exacto cada 15 min.
- Si el repo pasa **60 días sin actividad**, GitHub pausa las tareas programadas
  (se reactivan con un commit o desde la pestaña Actions).
- No incluye panel con URL; da las **notificaciones** (que es lo que pediste).
  Si además quieres el panel visual, combínalo con la Opción B.

---

## Opción B — Panel web con URL fija (nube, requiere un host)

Un panel que abres desde el navegador del móvil y muestra, en vivo: precio,
sentimiento de noticias, operaciones abiertas y últimos eventos. Se refresca solo.

### Desplegar en Render (gratis, todo desde el navegador) — RECOMENDADO
Esta ruta **no toca** el despliegue de la app de cuadrantes.

1. Sube el repo a GitHub (ya lo tienes) y entra en **render.com** con tu cuenta
   de GitHub (gratis, sin tarjeta).
2. **New → Web Service** → elige el repositorio `Luiperax/CUADRANTES` y en la
   rama pon `claude/xau-usd-trading-system-d7xtc0` (o `main` si ya lo fusionaste).
3. Configura estos dos campos (cópialos tal cual):
   - **Build command:** `pip install -r oro/requirements-web.txt`
   - **Start command:** `uvicorn oro.web:app --host 0.0.0.0 --port $PORT`
4. En **Environment → Add Environment Variable**, añade:
   - `ORO_PANEL_CLAVE` → una contraseña tuya (para que solo entres tú al panel).
   - `ORO_TELEGRAM_TOKEN` y `ORO_TELEGRAM_CHAT_ID` → si además quieres los avisos
     al móvil (ver Opción A para conseguirlos). Opcionales.
   - `ORO_INTERVALO` → `900` (segundos entre revisiones; 900 = 15 min). Opcional.
5. **Create Web Service.** Cuando termine (unos minutos) tendrás una URL fija tipo
   `https://oro-xauusd.onrender.com`. Ábrela en el móvil, introduce tu clave y
   **añádela a la pantalla de inicio** para tenerla como una app.

> Comprueba que vive: abre `…/oro/salud` (debe decir `"estado":"ok"` y
> `"scheduler_activo":true`).

### Alternativa: blueprint de un clic
Copia [`oro/deploy/render.yaml`](deploy/render.yaml) a la raíz del repo como
`render.yaml` y en Render usa **New → Blueprint → Apply**. Ojo: ese fichero
sustituiría al blueprint de la app de cuadrantes (por eso la ruta recomendada es
la de arriba, que no lo toca).

### Importante sobre el plan gratuito (léelo)
El plan **gratuito de Render se «duerme»** tras ~15 min sin visitas y, al
dormirse, **el motor se pausa** (deja de vigilar el mercado hasta que alguien
vuelve a abrir el panel). Para un vigilante que necesita mirar el mercado de
forma continua, esto es una limitación real. Opciones:

- **24/7 de verdad:** el plan más barato de Render (~7 USD/mes) o cualquier VPS
  económico, que no se duerme.
- **Truco en gratuito:** un servicio externo (p. ej. cron-job.org) que haga una
  petición a `…/oro/salud` cada 10 min para mantenerlo despierto. Es un apaño y
  puede ir contra las condiciones del plan gratuito; para uso serio, mejor el
  plan de pago.
- **Solo avisos, sin panel 24/7:** deja el motor en tu PC con `python -m oro.cli
  vivo` y recibe los avisos por Telegram (Opción A), sin depender de la nube.

---

## Comprobar que funciona

- Panel: abre la URL (o `http://TU_PC:8010/oro/panel` en local con
  `python -m oro.cli servir --vivo`).
- Estado en JSON: `…/oro/estado?clave=TU_CLAVE`.
- Salud: `…/oro/salud`.
- Forzar un ciclo ahora (para no esperar): `POST …/oro/ciclo?clave=TU_CLAVE`.
