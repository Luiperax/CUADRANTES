#!/usr/bin/env bash
# ===================================================================
#  Lanzador del Generador de Cuadrantes de Seguridad Privada (Linux/macOS)
#  Uso:  ./ejecutar.sh
#  La primera vez crea el entorno e instala las dependencias.
# ===================================================================
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "No se ha encontrado Python 3. Instálelo desde https://www.python.org/downloads/"
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Preparando el entorno por primera vez, espere..."
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

python main.py
