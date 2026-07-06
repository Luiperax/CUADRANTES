@echo off
REM ===================================================================
REM  Lanzador del Generador de Cuadrantes de Seguridad Privada (Windows)
REM  Haga doble clic en este archivo para abrir el programa.
REM  La primera vez creará el entorno e instalará las dependencias
REM  (puede tardar unos minutos). Las siguientes veces abrirá directo.
REM ===================================================================
cd /d "%~dp0"

REM Buscar Python: primero el lanzador "py" (siempre disponible aunque no se
REM marcara "Add to PATH"), y si no, "python".
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo.
    echo No se ha encontrado Python en este equipo.
    echo Instalelo desde https://www.python.org/downloads/ y, MUY IMPORTANTE,
    echo marque la casilla "Add python.exe to PATH" durante la instalacion.
    echo.
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

python main.py
if errorlevel 1 pause
