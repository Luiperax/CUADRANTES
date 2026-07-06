@echo off
REM ===================================================================
REM  Crea un ejecutable "Cuadrantes.exe" para Windows.
REM  Una vez creado, el programa se abre con doble clic y NO necesita
REM  tener Python instalado para usarse.
REM
REM  Ejecute este archivo UNA VEZ (haga doble clic). Al terminar, el
REM  programa estara en:  dist\Cuadrantes\Cuadrantes.exe
REM ===================================================================
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>nul && set "PYEXE=py"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo No se ha encontrado Python. Instalelo desde https://www.python.org/downloads/
    echo (marque "Add python.exe to PATH"). Solo hace falta para CREAR el ejecutable.
    pause
    exit /b 1
)

if not exist ".venv\" (
    echo Preparando el entorno...
    %PYEXE% -m venv .venv
    call ".venv\Scripts\activate.bat"
    python -m pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call ".venv\Scripts\activate.bat"
)

echo Instalando el empaquetador (PyInstaller)...
pip install pyinstaller

echo Construyendo el ejecutable (puede tardar varios minutos)...
pyinstaller --noconfirm --windowed --name Cuadrantes ^
    --collect-all ortools ^
    --collect-submodules cuadrantes ^
    main.py

echo.
echo ============================================================
echo  Listo. El programa esta en:
echo     dist\Cuadrantes\Cuadrantes.exe
echo  Puede copiar toda la carpeta "dist\Cuadrantes" a cualquier
echo  PC con Windows y abrirlo con doble clic (sin instalar nada).
echo ============================================================
pause
