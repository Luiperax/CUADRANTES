# Acceso desde el móvil SIN alojamiento en la nube

Si prefiere no desplegar en Render, Fly.io o Railway, puede usar el programa desde
el móvil ejecutándolo en **su propio ordenador** y accediendo a él de forma
remota. No hace falta contratar nada.

> **Único requisito:** el ordenador que ejecuta el programa debe estar **encendido**
> cuando quiera usarlo desde el móvil. (Esto es precisamente lo que evitaba la nube:
> allí el servidor siempre está disponible.) Si quiere acceso permanente sin depender
> de un PC, puede dejar corriendo el servidor en un equipo que esté siempre
> encendido en casa (un PC viejo o una Raspberry Pi).

Hay tres formas, de la más recomendable a la más simple.

---

## Opción 1 — Tailscale (recomendada: privada, segura y con nombre fijo)

Tailscale crea una pequeña **red privada** entre sus dispositivos. El móvil ve al
ordenador como si estuvieran en la misma red local, esté donde esté (con datos
móviles o cualquier Wi-Fi). Nada queda expuesto a internet, así que es la opción
más segura para datos de personal.

1. Cree una cuenta gratuita en <https://tailscale.com> (uso personal).
2. Instale Tailscale en el **ordenador** y en el **móvil**, e inicie sesión con la
   misma cuenta en ambos.
3. En el ordenador, arranque el programa web:
   - Windows: doble clic en `ejecutar_movil.bat`.
   - Otros: `python main.py --web`.
4. En Tailscale, el ordenador tendrá un **nombre fijo** (por ejemplo
   `mi-pc.tu-tailnet.ts.net`) y una IP fija tipo `100.x.y.z`.
5. En el móvil, abra en el navegador:
   ```
   http://mi-pc.tu-tailnet.ts.net:8000
   ```
   (o `http://100.x.y.z:8000`). Esa dirección es **estable**: sírvela una vez y
   funcionará siempre desde cualquier lugar.

> Consejo: añada la página a la pantalla de inicio del móvil para abrirla como una
> app. Aun siendo una red privada, conviene definir también `CUADRANTES_PASSWORD`.

---

## Opción 2 — Cloudflare Tunnel (URL pública, sin abrir puertos)

Crea una dirección pública `https://…` que apunta a su ordenador, sin tocar el
router ni abrir puertos. Útil si quiere una URL para compartir.

1. Descargue `cloudflared`: <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/>.
2. Arranque el programa web (`ejecutar_movil.bat` o `python main.py --web`).
3. En otra ventana, ejecute:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
4. `cloudflared` mostrará una URL pública tipo
   `https://algo-aleatorio.trycloudflare.com`. Ábrala desde el móvil.

- La modalidad rápida (arriba) **no requiere cuenta**, pero la URL **cambia** cada
  vez. Para una **URL fija**, cree una cuenta gratuita de Cloudflare y un «named
  tunnel» con un dominio (guía de Cloudflare).
- **Seguridad (importante):** al ser una URL pública, defina SIEMPRE una contraseña
  antes de arrancar:
  - Windows: `set CUADRANTES_PASSWORD=su_clave` y luego `ejecutar_movil.bat`.
  - Otros: `CUADRANTES_PASSWORD=su_clave python main.py --web`.

También puede usar **ngrok** (<https://ngrok.com>) de forma equivalente:
`ngrok http 8000` (cuenta gratuita; dominio reservado en el plan de pago).

---

## Opción 3 — Misma red Wi-Fi (lo más simple, solo en casa/oficina)

Si le basta con usarlo desde el móvil cuando está en el mismo sitio que el
ordenador:

1. Arranque `ejecutar_movil.bat` (o `python main.py --web`).
2. La ventana muestra una dirección tipo `http://192.168.1.50:8000`.
3. Abra esa dirección en el móvil, conectado a la **misma Wi-Fi**.

Para que la IP local no cambie, puede reservarla en el router (DHCP estático);
así la dirección será siempre la misma dentro de su red.

---

## Comparativa rápida

| Opción | URL fija | Funciona fuera de casa | Requiere cuenta | Seguridad | PC encendido |
|--------|:-------:|:----------------------:|:---------------:|-----------|:------------:|
| Tailscale | Sí | Sí | Sí (gratis) | Muy alta (privada) | Sí |
| Cloudflare Tunnel | Con dominio | Sí | Rápido: no / Fija: sí | Media-alta (poner contraseña) | Sí |
| Misma Wi-Fi | Sí (local) | No | No | Alta (red local) | Sí |

**Recomendación:** para uso personal y datos sensibles, **Tailscale** es la mejor
combinación de fija, segura y sin exponer nada a internet.
