# Uso desde el móvil (versión web)

El programa incluye una **versión web** que reutiliza exactamente el mismo motor
de optimización, base de datos, auditoría y exportadores que la versión de
escritorio, pero se maneja desde el **navegador**, incluido el del móvil.

Como cualquier página web, necesita un **servidor en marcha**. Hay dos formas de
tenerlo, según dónde quiera usarlo.

## Opción A — En casa / la oficina (misma red Wi-Fi)

La más sencilla y sin coste. El servidor se ejecuta en un ordenador y el móvil lo
abre a través de la red Wi-Fi.

1. En el ordenador, inicie la versión web:
   - **Windows:** doble clic en `ejecutar_movil.bat`.
   - **Otros:** `python main.py --web`.
2. La ventana mostrará una dirección como:
   ```
   Desde el móvil/red:  http://192.168.1.50:8000
   ```
3. En el móvil (conectado a la **misma red Wi-Fi**), abra esa dirección en el
   navegador. Ya puede generar cuadrantes, registrar ausencias, ver el resultado y
   descargar el Excel o el PDF.

> Consejo: añada la página a la pantalla de inicio del móvil para abrirla como si
> fuera una app.

## Opción B — Desde cualquier lugar (alojamiento en la nube)

Si quiere usarlo fuera de la red local (por ejemplo, desde la calle), el servidor
debe estar alojado en internet. La aplicación es un servicio estándar
FastAPI/uvicorn, por lo que puede desplegarse en cualquier proveedor que admita
Python (Render, Railway, Fly.io, un VPS…). Pasos generales:

1. Suba el repositorio al proveedor.
2. Instale dependencias: `pip install -r requirements.txt`.
3. Arranque con: `uvicorn cuadrantes.web.app:app --host 0.0.0.0 --port $PORT`.
4. Proteja el acceso (usuario/contraseña o red privada), ya que contiene datos de
   personal.

> Recomendación de seguridad: al exponer la aplicación en internet, añada siempre
> autenticación y HTTPS. Para uso interno del centro, la **Opción A** es suficiente
> y no expone nada fuera de su red.

## Qué se puede hacer desde el móvil

- Generar el cuadrante del mes.
- Consultar el calendario, la auditoría y las estadísticas.
- Registrar vacaciones, bajas y permisos.
- Añadir o desactivar trabajadores y sincronizar el equipo.
- Descargar el cuadrante en Excel o PDF y los informes.

## Sincronización entre la web y el programa de escritorio

Ambas aplicaciones están **sincronizadas** porque comparten la misma base de
datos:

- Por defecto, tanto el escritorio como la web usan el mismo fichero
  `datos/cuadrantes.db` de la carpeta del proyecto (ruta absoluta, independiente de
  desde dónde se lancen). Lo que se genera o edita en una aparece en la otra.
- El programa de escritorio se **actualiza automáticamente** al volver a activar su
  ventana (por ejemplo, tras usar el móvil) y también con el botón **«🔄
  Actualizar»**.
- La base de datos funciona en modo WAL con espera ante escrituras simultáneas, de
  modo que ambas aplicaciones pueden estar abiertas a la vez sin conflictos.

### Compartir los datos entre equipos o carpetas sincronizadas

Si desea que la web (en un equipo o servidor) y el escritorio (en otro) usen los
mismos datos, defina la variable de entorno `CUADRANTES_DB` con la ruta a un
fichero en una ubicación común (una carpeta sincronizada tipo OneDrive/Dropbox o
una unidad de red) **en ambas aplicaciones**:

```bash
# Windows (ejemplo)
set CUADRANTES_DB=Z:\cuadrantes\cuadrantes.db
python main.py            # escritorio
python main.py --web      # web (en el equipo servidor)
```

> Nota: con carpetas sincronizadas en la nube, evite tener ambas escribiendo a la
> vez sobre el mismo fichero para que el servicio de sincronización no genere copias
> en conflicto. Para uso simultáneo intensivo, lo ideal es una única máquina que
> ejecute la web y comparta el resto por red.
