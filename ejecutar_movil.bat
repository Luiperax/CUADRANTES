@echo off
REM ===================================================================
REM  Version WEB del Generador de Cuadrantes (uso desde el movil)
REM  Haga doble clic para iniciar el servidor. Despues, en el movil
REM  (conectado a la misma red Wi-Fi), abra la direccion
REM  http://IP-DE-ESTE-PC:8000 que aparece en la ventana.
REM ===================================================================
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo No se ha encontrado Python. Instalelo desde https://www.python.org/downloads/
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

python main.py --web
pause
