@echo off
REM ===================================================================
REM  Version WEB del Generador de Cuadrantes (uso desde el movil)
REM  Haga doble clic para iniciar el servidor. Despues, en el movil
REM  (conectado a la misma red Wi-Fi), abra la direccion
REM  http://IP-DE-ESTE-PC:8000 que aparece en la ventana.
REM ===================================================================
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>nul && set "PYEXE=py"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo No se ha encontrado Python. Instalelo desde https://www.python.org/downloads/
    echo y marque "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist ".venv\" (
    echo Preparando el entorno por primera vez, espere...
    %PYEXE% -m venv .venv
    call ".venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call ".venv\Scripts\activate.bat"
)

python main.py --web
pause
