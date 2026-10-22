# Imagen base de python 3.12 version slim
FROM python:3.12-slim

# Variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Carpeta de trabajo dentro de la imagen
WORKDIR /code

# Construimos los requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ahora copiamos el codigo
COPY app/ ./app/

# agregamos un user para no ejecutar como root

RUN useradd --create-home appuser
USER appuser 

# Esto es documental esto no hace nada
EXPOSE 8000

# Iniciamos el app
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]