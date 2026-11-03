# Multi-stage Dockerfile para Dron de Escaneo de Vías de Ciénaga
# 1. Frontend Build Stage (React + TypeScript + Vite)
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# 2. Backend & Runtime Stage (FastAPI + Python 3.12 + PyTorch CPU + Ultralytics)
FROM python:3.12-slim AS runner

WORKDIR /app

# Instalar dependencias del sistema requeridas por OpenCV headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copiar código fuente
COPY backend/ ./backend/
COPY docs/ ./docs/
COPY simulation/ ./simulation/
COPY webots.yml ./

# Copiar bundle compilado del frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Variables de entorno
ENV PYTHONPATH=/app
ENV PORT=8000
ENV HOST=0.0.0.0
ENV DATABASE_URL="sqlite:///backend/storage/data.db"
ENV DETECTION_MODEL_TYPE="yolo"
ENV DETECTION_CONFIDENCE_THRESHOLD=0.25

# Persistencia de incidentes y evidencias
VOLUME ["/app/backend/storage"]

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

