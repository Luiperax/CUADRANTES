# Imagen para desplegar la versión web del Generador de Cuadrantes.
# Sirve la aplicación en una URL fija, accesible desde cualquier móvil.
FROM python:3.11-slim

WORKDIR /app

# Instalar solo las dependencias del servidor (sin PySide6).
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Copiar el código de la aplicación.
COPY cuadrantes ./cuadrantes
COPY main.py ./

# La base de datos se guarda en /data (monte aquí un disco/volumen persistente
# para conservar los datos entre reinicios y despliegues).
ENV CUADRANTES_DB=/data/cuadrantes.db
RUN mkdir -p /data

EXPOSE 8000

# El proveedor de alojamiento suele inyectar el puerto en la variable PORT.
CMD ["sh", "-c", "uvicorn cuadrantes.web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
