# Despliegue en la nube (URL fija accesible desde el móvil)

Esta guía explica cómo publicar la versión web en internet para tener una
**dirección fija** (por ejemplo `https://cuadrantes-seguridad.onrender.com`) que
se pueda abrir desde cualquier móvil, en cualquier momento, sin depender de que un
ordenador esté encendido. La base de datos vive en el servidor, de modo que todo
queda siempre sincronizado.

El proyecto ya incluye todo lo necesario:

- `Dockerfile` — empaqueta la aplicación (sin la interfaz de escritorio).
- `render.yaml` — despliegue en Render.
- `fly.toml` — despliegue en Fly.io.
- `Procfile` — despliegue en Railway.
- Autenticación por usuario y contraseña integrada.

> **Seguridad:** como contiene datos de personal, el acceso está protegido con
> contraseña. Defina siempre `CUADRANTES_PASSWORD` al desplegar. El servidor sirve
> además por HTTPS en todos los proveedores indicados.

---

## Opción recomendada A — Render (la más sencilla)

Render permite desplegar conectando el repositorio, sin usar la línea de comandos.

1. Cree una cuenta en <https://render.com> y conéctela con su cuenta de GitHub.
2. En Render: **New → Blueprint** y seleccione el repositorio `luiperax/cuadrantes`.
   Render detectará el fichero `render.yaml`.
3. Pulse **Apply**. Se creará el servicio web con su URL fija.
4. En el servicio, entre en **Environment** y defina el valor de
   **`CUADRANTES_PASSWORD`** (la contraseña que usará para entrar).
5. Espere a que termine el despliegue y abra la URL en el móvil. Le pedirá usuario
   (`admin`) y la contraseña que acaba de poner.

**Persistencia de los datos:** el `render.yaml` incluye un disco en `/data` para
conservar la base de datos. Los discos de Render requieren un plan de pago
(aproximadamente 7 $/mes). En el plan gratuito la aplicación funciona igual, pero
la base de datos se reinicia en cada nuevo despliegue: válido para probar, no para
uso continuado. Si quiere datos permanentes sin coste, use la Opción B.

---

## Opción recomendada B — Fly.io (URL fija con datos permanentes, gratis)

Fly.io ofrece un volumen persistente pequeño sin coste, ideal para este caso.
Requiere instalar una herramienta de línea de comandos (`flyctl`).

1. Instale `flyctl`: <https://fly.io/docs/hands-on/install-flyctl/> y cree una cuenta
   con `fly auth signup`.
2. En la carpeta del proyecto:
   ```bash
   fly launch --no-deploy        # confirme el nombre y la región (mad = Madrid)
   fly volumes create cuadrantes_datos --size 1
   fly secrets set CUADRANTES_PASSWORD=su_contraseña
   fly deploy
   ```
3. Al terminar, `flyctl` mostrará la URL fija
   (`https://<su-app>.fly.dev`). Ábrala desde el móvil.

Los datos se conservan en el volumen entre reinicios y despliegues.

---

## Opción C — Railway

1. Cree una cuenta en <https://railway.app> y un proyecto desde el repositorio.
2. Railway detecta el `Dockerfile` (o el `Procfile`). Deje que construya.
3. Añada un **Volume** montado en `/data`.
4. En **Variables**, defina:
   - `CUADRANTES_DB = /data/cuadrantes.db`
   - `CUADRANTES_PASSWORD = su_contraseña`
5. Genere un dominio público en **Settings → Networking**. Esa es su URL fija.

---

## Variables de entorno

| Variable | Para qué sirve | Ejemplo |
|----------|----------------|---------|
| `CUADRANTES_PASSWORD` | Contraseña de acceso (obligatoria en producción). | `una-clave-larga` |
| `CUADRANTES_USER` | Usuario de acceso (opcional). | `admin` (por defecto) |
| `CUADRANTES_DB` | Ruta del fichero de base de datos. | `/data/cuadrantes.db` |
| `PORT` | Puerto de escucha (lo inyecta el proveedor). | `8000` |

## Después de desplegar

- Abra la URL en el móvil, introduzca usuario y contraseña, y podrá generar
  cuadrantes, registrar ausencias, gestionar el equipo y descargar Excel/PDF.
- Para copias de seguridad, descargue periódicamente los cuadrantes en Excel/PDF, o
  conserve una copia del fichero de la base de datos del volumen.
- La versión de escritorio puede seguir usándose en local; si quiere que comparta
  exactamente los mismos datos que la versión desplegada, ambas deberían apuntar a
  la misma base (véase `docs/USO_MOVIL.md`). Lo habitual es usar la web desplegada
  como sistema principal cuando ya está en la nube.
