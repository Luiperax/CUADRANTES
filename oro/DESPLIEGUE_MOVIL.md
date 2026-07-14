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

## Opción B — Panel web con URL fija (nube)

Un panel que abres desde el navegador del móvil y muestra, en vivo: precio,
sentimiento de noticias, operaciones abiertas y últimos eventos. Se refresca solo.

### Desplegar en Render (gratis, todo desde el navegador)
1. Sube el repo a GitHub (ya lo tienes) y entra en **render.com** con tu GitHub.
2. **New → Web Service** → elige este repositorio y configura:
   - **Build command:** `pip install -r oro/requirements.txt`
   - **Start command:** `uvicorn oro.web:app --host 0.0.0.0 --port $PORT`
3. En **Environment**, añade (todas opcionales salvo la clave del panel):
   - `ORO_PANEL_CLAVE` → una contraseña para proteger tu panel público.
   - `ORO_TELEGRAM_TOKEN`, `ORO_TELEGRAM_CHAT_ID` → para además recibir avisos.
   - `ORO_INTERVALO` → segundos entre revisiones (por defecto 900 = 15 min).
4. **Create Web Service.** Al terminar tendrás una URL fija tipo
   `https://oro-xauusd.onrender.com` → ábrela en el móvil y añádela a la pantalla
   de inicio. Introduce la clave del panel la primera vez.

> Alternativa con blueprint (un clic): usa el fichero
> [`oro/deploy/render.yaml`](deploy/render.yaml) copiándolo a la raíz del repo.
> Ten en cuenta que sustituiría al blueprint de la app de cuadrantes.

### Nota sobre el plan gratuito
El servicio gratuito se «duerme» tras un rato sin visitas y el motor se pausa; se
reanuda solo al abrir el panel (tarda unos segundos). Para vigilancia **24/7 sin
pausas**, usa un plan de pago de Render (o cualquier VPS) y déjalo siempre activo.

---

## Comprobar que funciona

- Panel: abre la URL (o `http://TU_PC:8010/oro/panel` en local con
  `python -m oro.cli servir --vivo`).
- Estado en JSON: `…/oro/estado?clave=TU_CLAVE`.
- Salud: `…/oro/salud`.
- Forzar un ciclo ahora (para no esperar): `POST …/oro/ciclo?clave=TU_CLAVE`.
