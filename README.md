# Sistema de Vigilancia y Escaneo con Dron Autónomo (Webots + FastAPI + React)

Sistema inteligente de vigilancia aérea para inspección de infraestructura ferroviaria y vial mediante simulación robótica en **Webots**, procesamiento de visión artificial con **OpenCV** (arquitectura desacoplada lista para **YOLO**), backend de alta concurrencia en **FastAPI** con **WebSockets** y base de datos relacional en **SQLite**, y panel de control táctico en tiempo real en **React + TypeScript + Vite**.

---

## 🎯 Objetivos de Detección del Sistema

El sistema inspecciona el corredor de vías y detecta automáticamente tres clases de interés:
1. **Postes de luz**: Columnas de iluminación o electrificación a lo largo de las vías.
2. **Vegetación invasiva**: Maleza, ramas o cobertura vegetal excesiva que compromete la vía.
3. **Obstrucción en vías**: Objetos extraños, cargas caídas, rocas o escombros sobre el carril.

---

## 🏗️ Arquitectura del Sistema

```
                      +-----------------------------+
                      |   Simulador Robótico Webots |
                      |    (Mavic 2 Pro / Sensores) |
                      +--------------+--------------+
                                     |
               Telemetría (HTTP) /   |   Fotogramas Base64 (HTTP)
               Comandos (WebSocket)  v
                      +-----------------------------+
                      |     Backend FastAPI (REST)  |
                      |  - SQLite (data.db)         |
                      |  - OpenCV / BaseDetector    |
                      |  - WebSocket Manager (/ws)  |
                      +--------------+--------------+
                                     |
                Streaming Live /     |   Telemetría en Vivo /
                Alertas Incidentes   v   Comandos de Vuelo
                      +-----------------------------+
                      |   Frontend React + TS + Vite|
                      |     (Dashboard Táctico)     |
                      +-----------------------------+
```

---

## 📁 Estructura del Proyecto

```
P.F - Dron De Escaneo/
├── backend/
│   ├── app/
│   │   ├── api/v1/
│   │   │   ├── endpoints/
│   │   │   │   ├── drones.py        # Registro y comandos de drones
│   │   │   │   ├── telemetria.py    # Ingesta y consulta de posición 3D
│   │   │   │   ├── cameras.py       # Recepción de frames y streaming
│   │   │   │   ├── deteccion.py     # Endpoints de visión artificial
│   │   │   │   ├── imagenes.py      # Almacenamiento y entrega de fotos
│   │   │   │   └── incidentes.py    # Gestión del ciclo de incidentes
│   │   │   └── api.py               # Agregador de rutas v1
│   │   ├── core/
│   │   │   ├── config.py            # Variables y configuración BaseSettings
│   │   │   ├── database.py          # Motor SQLite y sesiones SQLAlchemy
│   │   │   └── websocket_manager.py # Manejador de conexiones WebSocket
│   │   ├── models/                  # Modelos de Base de Datos (ORM)
│   │   │   ├── dron.py              # Entidad Drone
│   │   │   ├── telemetria.py        # Entidad TelemetryRecord
│   │   │   ├── imagen.py            # Entidad ImageRecord
│   │   │   └── incidente.py         # Entidad Incidente
│   │   ├── schemas/                 # Esquemas Pydantic (DTOs)
│   │   ├── modules/                 # Capa de Lógica de Negocio Modular
│   │   │   ├── drones/              # Servicio de drones y despacho de comandos
│   │   │   ├── cameras/             # Servicio de video e ingesta de fotogramas
│   │   │   ├── deteccion/           # Pipeline de visión (BaseDetector + YOLO ready)
│   │   │   ├── imagenes/            # Servicio de persistencia de imágenes
│   │   │   ├── incidentes/          # Lógica de anomalías y severidades
│   │   │   └── telemetria/          # Ingesta y broadcast de telemetría
│   │   └── main.py                  # Aplicación FastAPI y WebSocket endpoint
│   ├── storage/
│   │   ├── images/                  # Fotos originales y anotadas
│   │   └── data.db                  # Base de datos SQLite
│   ├── tests/
│   │   └── test_backend.py          # Suite de pruebas automatizadas con pytest
│   ├── requirements.txt             # Dependencias Python
│   └── run.py                       # Script de inicio directo
├── frontend/                        # Dashboard React + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx           # Barra superior con estado del sistema
│   │   │   ├── DroneStatusCard.tsx  # Métricas de vuelo y botones de control
│   │   │   ├── LiveCameraFeed.tsx   # Visor de video con HUD y leyendas
│   │   │   ├── TelemetryPanel.tsx   # Posición espacial 3D y horizonte
│   │   │   ├── DetectionViewer.tsx  # Inspector de anomalías detectadas
│   │   │   └── IncidentLog.tsx      # Tabla reactiva de incidentes SQLite
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts      # Hook con reconexión automática
│   │   ├── services/
│   │   │   └── api.ts               # Cliente REST tipado
│   │   ├── types/                   # Definiciones de tipos TypeScript
│   │   ├── App.tsx                  # Componente principal
│   │   └── App.css                  # Estilos HUD aeroespacial
│   ├── package.json
│   └── vite.config.ts
├── simulation/                      # Proyecto Webots
│   ├── worlds/
│   │   └── inspection_zone.wbt      # Mundo 3D con vía, postes, vegetación y obstáculos
│   ├── controllers/
│   │   └── drone_supervisor/
│   │       ├── drone_supervisor.py  # Controlador del dron para Webots
│   │       ├── communication.py     # Cliente de red para backend
│   │       └── flight_controller.py # Navegación por waypoints
│   └── mock_webots_runner.py        # Ejecutor de simulación autónomo (headless/test)
├── docs/
│   └── architecture.md              # Documentación técnica extendida
└── README.md
```

---

## 🚀 Instrucciones de Ejecución

### 1. Requisitos Previos
* **Python**: 3.10 o superior (instalado en el sistema).
* **Node.js**: v18 o superior con `npm`.
* **Webots**: R2022b o compatible (opcional para GUI 3D completa).

### 🚀 Ejecución Rápida en 1-Clic (Sin Comandos)

Puedes iniciar automáticamente todos los componentes del sistema (Backend + Frontend + Navegador + Simulación 3D Webots) con un solo doble clic:

1. Haz doble clic sobre el archivo **`iniciar_sistema.bat`** ubicado en la carpeta raíz del proyecto.
2. El script iniciará los servicios en segundo plano, abrirá el Dashboard en tu navegador (`http://localhost:5173`) y lanzará Webots 3D con la escena del dron.

---

### 2. Ejecución Manual por Pasos (Terminal)

1. Abrir una terminal en el directorio raíz del proyecto:
   ```powershell
   # Activar o usar el entorno virtual
   backend\.venv\Scripts\python backend\run.py
   ```
2. El backend iniciará en:
   * **API REST**: `http://127.0.0.1:8000`
   * **Documentación interactiva Swagger**: `http://127.0.0.1:8000/docs`
   * **Endpoint WebSocket**: `ws://127.0.0.1:8000/ws`
   * **Verificación de salud**: `http://127.0.0.1:8000/health`

---

### 3. Ejecutar el Frontend (React + TypeScript + Vite)

1. En una nueva terminal, ejecutar:
   ```powershell
   npm --prefix frontend run dev
   ```
2. Abrir en el navegador:
   * `http://localhost:5173/`

---

### 4. Ejecutar la Simulación de Vuelo y Escaneo

#### Opción A: Simulación de Vuelo Headless / Prueba Rápida
Ejecuta el ciclo completo de vuelo, navegación por waypoints, generación de escenas visuales sintéticas y envío de telemetría/imágenes al backend:
```powershell
backend\.venv\Scripts\python simulation\mock_webots_runner.py 15
```
*(El argumento `15` indica la duración en segundos del vuelo).*

#### Opción B: Ejecución en Webots GUI Completo
1. Abrir Webots.
2. Ir a `File -> Open World...` y seleccionar:
   `simulation/worlds/inspection_zone.wbt`
3. Iniciar la simulación con el botón `Play`.
4. El controlador `drone_supervisor` despegará el cuadricóptero, navegará a 8 metros de altitud a lo largo de la vía y transmitirá los fotogramas y la telemetría al backend en tiempo real.

---

### 5. Ejecutar las Pruebas Automatizadas

Para validar que todos los componentes, base de datos SQLite, endpoints REST y WebSockets operen al 100%:
```powershell
backend\.venv\Scripts\pytest backend\tests\test_backend.py -v
```

---

## 🧠 Preparación para Integración con YOLO

La arquitectura de visión fue diseñada bajo el patrón **Adapter / Strategy** mediante la interfaz abstracta `BaseDetector`:

* **`BaseDetector`** (`backend/app/modules/deteccion/base.py`):
  Declara los métodos estándar `load_model()`, `detect(image, threshold)` y `annotate_image(image, detections)`.
* **`HeuristicDetector`** (`backend/app/modules/deteccion/mock_detector.py`):
  Implementación operativa actual basada en OpenCV (máscaras de color HSV para vegetación, análisis de contornos y gradientes para postes, e inspección de contraste para obstáculos en vía).
* **`YOLODetector`** (`backend/app/modules/deteccion/yolo_adapter.py`):
  Adaptador preparado para Ultralytics YOLO (`YOLOv8`/`YOLOv11`). Permite cargar pesos entrenados (`storage/weights/best.pt`) y mapea automáticamente las clases detectadas a:
  - Clase 0: `poste_luz`
  - Clase 1: `vegetacion_invasiva`
  - Clase 2: `obstruccion_via`

Para activar YOLO en la siguiente fase:
1. Colocar el archivo de pesos en `backend/storage/weights/best.pt`.
2. En `backend/app/core/config.py`, cambiar `DETECTION_MODEL_TYPE = "yolo"`.
3. No se requiere reorganizar rutas, controladores, base de datos ni componentes del frontend.
