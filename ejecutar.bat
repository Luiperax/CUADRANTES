@echo off
REM ===================================================================
REM  Lanzador del Generador de Cuadrantes de Seguridad Privada (Windows)
REM  Haga doble clic en este archivo para abrir el programa.
REM  La primera vez creará el entorno e instalará las dependencias
REM  (puede tardar unos minutos). Las siguientes veces abrirá directo.
REM ===================================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se ha encontrado Python. Instalelo desde https://www.python.org/downloads/
    echo Recuerde marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

if not exist ".venv\" (
    echo Preparando el entorno por primera vez, espere...
    python -m venv .venv
    call ".venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call ".venv\Scripts\activate.bat"
)

python main.py
if errorlevel 1 pause
