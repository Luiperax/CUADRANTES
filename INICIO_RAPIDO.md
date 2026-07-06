# Inicio rápido — Cómo empezar a usar el programa

Guía mínima para tener el programa funcionando en su ordenador en pocos minutos.

## Requisito único: Python

Necesita **Python 3.10 o superior** instalado.

- Descárguelo en <https://www.python.org/downloads/>.
- En Windows, durante la instalación marque la casilla **«Add Python to PATH»**.

## Paso 1 — Descargar el programa

1. Entre en el repositorio en GitHub: **`luiperax/cuadrantes`**.
2. Cambie a la rama **`claude/security-shift-scheduler-lnt5ae`**.
3. Pulse el botón verde **«Code» → «Download ZIP»**.
4. Descomprima el ZIP en una carpeta de su equipo (por ejemplo, `Documentos\Cuadrantes`).

> Si prefiere usar Git: `git clone` del repositorio y `git checkout claude/security-shift-scheduler-lnt5ae`.

## Paso 2 — Abrir el programa

### Windows
Haga **doble clic** en el archivo **`ejecutar.bat`**.
- La primera vez preparará todo automáticamente (tarda unos minutos).
- Las siguientes veces abrirá directamente.

### macOS / Linux
Abra un terminal en la carpeta y ejecute:

```bash
./ejecutar.sh
```

(La primera vez, dé permisos con `chmod +x ejecutar.sh`.)

## Paso 3 — Empezar a trabajar

Al abrirse, el programa ya trae cargado el **equipo actual del centro**. A partir de ahí:

1. En el panel izquierdo, elija **mes** y **año** y pulse **«Generar con asistente»**.
2. El asistente le preguntará por vacaciones, bajas, permisos, restricciones e
   incidencias del mes.
3. Al terminar, obtendrá el cuadrante. Revíselo en las pestañas **Calendario**,
   **Auditoría** y **Estadísticas**, edítelo si lo necesita y expórtelo a
   **Excel** o **PDF**.

## Atajos útiles

- **👥 Trabajadores**: añadir o quitar personal del equipo. El botón
  **«🔄 Sincronizar con equipo actual»** ajusta la plantilla al equipo definido.
- **🏖️ Vacaciones/bajas/PR**: registrar ausencias en cualquier momento.
- **⚙️ Configuración**: cambiar reglas y prioridades sin tocar el código.
- **💾 Copia de seguridad**: guardar una copia de todos los datos.

## ¿Problemas?

Consulte la guía completa en [`docs/INSTALACION.md`](docs/INSTALACION.md) y
[`docs/MANUAL_USUARIO.md`](docs/MANUAL_USUARIO.md).
