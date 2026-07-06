@echo off
REM ===================================================================
REM  Acceso desde el movil SIN alojamiento en la nube (Cloudflare Tunnel)
REM  Arranca la version web y crea una URL publica temporal que apunta a
REM  este ordenador. Requiere tener instalado "cloudflared".
REM  Descargar: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
REM ===================================================================
cd /d "%~dp0"

where cloudflared >nul 2>nul
if errorlevel 1 (
    echo No se ha encontrado "cloudflared". Instalelo desde:
    echo https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    pause
    exit /b 1
)

REM Recomendado: proteger con contrasena al exponer una URL publica.
if "%CUADRANTES_PASSWORD%"=="" (
    set /p CUADRANTES_PASSWORD=Introduzca una contrasena de acceso (recomendado):
)

echo Iniciando el servidor web en segundo plano...
start "Cuadrantes Web" cmd /c "%~dp0ejecutar_movil.bat"

echo Esperando a que el servidor arranque...
timeout /t 10 >nul

echo Creando la URL publica. La direccion https aparecera a continuacion:
cloudflared tunnel --url http://localhost:8000
pause
