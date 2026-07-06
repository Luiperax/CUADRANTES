# Instrucciones de instalación

## 1. Requisitos previos

- **Python 3.10 o superior** (recomendado 3.11).
- Sistema operativo: Windows 10/11, Linux o macOS.
- Aproximadamente 500 MB de espacio (principalmente por OR-Tools y PySide6).

Comprobar la versión de Python:

```bash
python --version
```

## 2. Instalación de dependencias

Se recomienda utilizar un **entorno virtual** para aislar las dependencias:

```bash
# Crear y activar el entorno virtual
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# Instalar las dependencias
pip install -r requirements.txt
```

### Nota para Linux

PySide6 puede requerir bibliotecas del sistema para la parte gráfica. En
distribuciones basadas en Debian/Ubuntu:

```bash
sudo apt-get install -y libegl1 libgl1 libxkbcommon0 libdbus-1-3
```

## 3. Primer arranque

```bash
python main.py
```

En el primer arranque:
- Se crea la base de datos en `datos/cuadrantes.db`.
- Se carga una **plantilla de ejemplo** de 11 trabajadores con las restricciones
  individuales del pliego.

## 4. Ejecución automática el día 15

### Opción A — Programador interno (aplicación abierta)

```bash
python main.py --programador
```

Mientras la aplicación esté en ejecución, el día 15 a las 09:00 se abrirá
automáticamente el asistente del mes siguiente.

### Opción B — Programador de tareas de Windows (desatendido)

Para que Windows abra la aplicación aunque no esté en ejecución, registrar una
tarea mensual (ejecutar una sola vez, como administrador):

```bat
schtasks /Create /SC MONTHLY /D 15 /TN "GeneradorCuadrantes" ^
  /TR "\"C:\ruta\a\python.exe\" \"C:\ruta\al\proyecto\main.py\" --asistente" ^
  /ST 09:00 /F
```

El proyecto incluye una función auxiliar que genera este comando con las rutas
correctas (`cuadrantes.programador.planificador.generar_tarea_windows`).

## 5. Verificación de la instalación

```bash
python -m tests.test_optimizador
```

Debe mostrar `OPTIMAL`, 0 puestos sin cubrir y confirmar que se respetan las
restricciones individuales.

## 6. Generación de un ejecutable (opcional)

Para distribuir la aplicación sin necesidad de instalar Python, puede empaquetarse
con PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "Cuadrantes" main.py
```

El ejecutable se generará en la carpeta `dist/`.
