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

Para validar que todos los componentes, motor de visión, clasificación vial, ingesta de imágenes externas y regresión operen al 100%:
```powershell
# Ejecutar la suite completa de pruebas (Semanas 1 a 7)
py -m pytest backend/tests/ -v

# Ejecutar específicamente las pruebas de carga y análisis de imágenes (Semana 7)
py -m pytest backend/tests/test_semana_7_image_upload.py -v
```

---

## 📷 Semana 7: Carga y Análisis de Imágenes Externas (JPG/PNG)

El sistema permite cargar fotografías externas desde el computador del usuario para analizarlas con el mismo motor de visión artificial y clasificación vial, sin necesidad de tener Webots abierto.

* **Endpoints**:
  * `POST /api/v1/imagenes/analyze` (y alias `POST /api/v1/images/analyze`)
  * Parámetros: `file` (multipart/form-data, JPG/PNG, máx. 10 MB), `confidence_threshold` (0.0 a 1.0), `save_to_storage` (booleano).
* **Seguridad & Integridad**:
  * Decodificación real OpenCV contra archivos corruptos o extensiones falseadas.
  * Límites estrictos de memoria por lectura en bloques (64 KB).
  * Reporte honesto de ubicación: `simulation_coords=null`, `gps_coords=null`, `has_location=false`.
* **Dashboard React**:
  * Sección dedicada con Drag & Drop, vista previa, barra de confianza y visualizador comparativo (original vs anotado).

---

## 🚨 Semana 8: Gestión de Incidentes y Persistencia SQLite

El sistema cuenta con un módulo robusto de registro, consulta y mantenimiento de anomalías viales calificadas por visión artificial o cargadas manualmente, persistidas de forma duradera en SQLite.

* **Endpoints Principales (`/api/v1/incidentes`)**:
  * `POST /api/v1/incidentes`: Registro con deduplicación espacio-temporal automática (5 s / 2.5 m). Soporta `allow_duplicate=true`.
  * `GET /api/v1/incidentes`: Consulta con filtros combinados (`tipo`, `severidad`, `estado`, `drone_id`, `min_confidence`, `has_image`, `search`, `order_by`, `skip`, `limit`).
  * `GET /api/v1/incidentes/stats`: Estadísticas consolidadas (totales, por tipo, severidad, estado, confianza promedio).
  * `GET /api/v1/incidentes/{id}`: Detalle de incidente por ID.
  * `GET /api/v1/incidentes/{id}/imagen`: Metadatos y descarga de fotografía vinculada (`?download=true`).
  * `PATCH /api/v1/incidentes/{id}`: Actualización del estado operativo (`reportado`, `en_revision`, `atendido`, `descartado`), severidad o descripción.
  * `DELETE /api/v1/incidentes/{id}`: Eliminación controlada de incidentes.
* **Resiliencia & Integridad**:
  * Manejo seguro de errores de base de datos con `db.rollback()` para proteger la continuidad del servidor FastAPI.
  * Validación exhaustiva de entradas con Pydantic v2 (bloqueo de NaN, Inf, strings vacíos y valores fuera de rango).
  * Migración idempotente no destructiva para preservar registros históricos en `data.db`.
* **Pruebas Automatizadas**:
  * Ejecución de tests: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_semana_8_incidentes.py -v` (12 tests pasando al 100%).
  * Suite completa de regresión: `backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v` (63 tests pasando al 100%).

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
1. Colocar el archivo de pesos en `backend/storage/weights/yolov8n.pt` o `best.pt`.
2. En `backend/app/core/config.py`, cambiar `DETECTION_MODEL_TYPE = "yolo"`.
3. No se requiere reorganizar rutas, controladores, base de datos ni componentes del frontend.

---

## 🎮 Semana 10: Control de Vuelo, Waypoints y Failsafe de Batería Crítica

* **Máquina de Estados de Vuelo (`flight_controller.py`)**:
  - `READY_ON_GROUND`: Estado seguro de inicio con motores completamente detenidos (`0.0 rad/s`). El dron espera la orden `TAKEOFF` del dashboard.
  - `TAKEOFF`: Ascenso vertical controlado hasta altitud de crucero (6.0 m) y transición autónoma a navegación.
  - `NAVIGATING`: Recorrido ordenado por los 5 waypoints del corredor vial de Ciénaga.
  - `HOVER`: Mantenimiento de posición e inspección visual con amortiguación horizontal activa.
  - `RETURNING`: Retorno autónomo a la estación base de despegue.
  - `LANDING` / `LANDED`: Aterrizaje suave y parada total de motores.
  - Soporte de re-despegue tras `LANDED` para misiones consecutivas.
* **Failsafe de Batería Crítica (< 20%)**:
  - Disparo automático de `RETURN_TO_HOME` al detectar nivel de batería inferior al 20.0%.
  - Prioridad absoluta: los comandos `RESUME_PATROL` y `TAKEOFF` quedan formalmente bloqueados por seguridad.
  - Prevención de comandos repetidos mediante flag de un solo disparo.
  - Compatibilidad de aterrizaje forzoso: el operador conserva la potestad de ejecutar `LAND` en cualquier momento.

---

## ⚡ Semana 11: Rendimiento, Estabilidad y Preparación Final

* **Reconexión Automática WebSocket con Backoff Exponencial (`useWebSocket.ts`)**:
  - Detección reactiva de desconexiones sin exigir recargar la página.
  - Intervalos incrementales progresivos (1.5s a 15s) con jitter anti-colisiones.
  - Limpieza rigurosa de listeners para evitar conexiones o fugas de memoria duplicadas.
  - Resuscripción automática a canales de telemetría, video e incidentes tras reconectar.
* **Indicador Visual de Rumbo y Vector de Velocidad en Mapa 2D (`RoadMap2D.tsx`)**:
  - Visualización del vector de velocidad horizontal escalado dinámicamente con la telemetría real del dron.
  - Flecha indicadora de rumbo basada en ángulo `yaw` y desplazamiento sobre el corredor vial.
  - Anillo de amortiguación visual durante estados de `HOVER`.
  - Distintivo dinámico de velocidad en m/s sobre el dron y en la barra de telemetría inferior.
* **Control Dinámico del Umbral de Confianza YOLO (0.15 a 0.50)**:
  - Selector deslizante y accesos rápidos (0.20 Sensible, 0.25 Equilibrado, 0.40 Conservador) en `DetectionViewer.tsx`.
  - Endpoints REST `GET /api/v1/deteccion/threshold` y `PUT /api/v1/deteccion/threshold`.
  - Actualización atómica en el motor de inferencia sin reiniciar FastAPI ni Webots.
* **Despliegue y Reproducibilidad**:
  - **Docker**: `Dockerfile` multi-etapa (Node 20 + Python 3.12) y `.dockerignore`.
  - **Webots Cloud**: Archivo de configuración oficial `webots.yml` apuntando a `simulation/worlds/inspection_zone.wbt`.
  - **Instrucciones para Terceros**: Ejecución en un solo paso mediante `iniciar_sistema.bat` o contenedores Docker.

