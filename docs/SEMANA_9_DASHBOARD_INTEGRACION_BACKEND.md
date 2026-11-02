# SEMANA 9 — DASHBOARD FUNCIONAL E INTEGRACIÓN CON EL BACKEND
**Sistema de Detección e Inspección de Vías de Ciénaga con Dron Autónomo**

Documentación Técnica de Entrega  
Fecha: 1 de Noviembre de 2026  
Rama: `ioan-dev`  
Rol: Desarrollador Sénior Especializado en React, TypeScript, Vite y Sistemas de Visión Artificial

---

## 1. Resumen Ejecutivo

En la **Semana 9**, el dashboard de control de misión en **React + TypeScript + Vite** quedó completamente conectado al backend real en **FastAPI**, **WebSocket** y **SQLite**, integrando los módulos desarrollados en las semanas anteriores:
- **Semana 5:** Motor de Visión Artificial (YOLOv8 / Fallback Heurístico OpenCV / Modo Diagnóstico).
- **Semana 6:** Clasificación Vial Normalizada (`poste_luz`, `vegetacion_invasiva`, `obstruccion_via`, `otro`), validación geométrica de cajas delimitadoras y deduplicación espacio-temporal.
- **Semana 7:** Carga y análisis manual de imágenes externas JPG y PNG (`POST /api/v1/imagenes/analyze`).
- **Semana 8:** Gestión integral de incidentes persistidos en SQLite (`GET/POST/PATCH/DELETE /api/v1/incidentes` y `GET /api/v1/incidentes/stats`).

---

## 2. Variables de Configuración (`.env`)

El frontend utiliza variables de entorno prefijadas con `VITE_` (definidas en `frontend/.env.example`) y cuenta con valores predeterminados seguros para ejecución local sin exponer credenciales ni secretos:

| Variable | Valor por Defecto Local | Descripción |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | URL base del servidor FastAPI REST (`/health` y `/api/v1/...`). |
| `VITE_WS_URL` | `ws://127.0.0.1:8000/ws` | Endpoint WebSocket para telemetría, stream de cámara y alertas de incidentes en tiempo real. |

---

## 3. Endpoints REST y Eventos WebSocket Utilizados

### 3.1 Endpoints HTTP REST (`frontend/src/services/api.ts`)

| Método y Ruta | Componente Consumidor | Propósito y Contrato |
| :--- | :--- | :--- |
| `GET /health` | `App.tsx`, `Header.tsx` | Verifica disponibilidad del servidor FastAPI y conexión SQLite (`status: "online"`). |
| `GET /api/v1/deteccion/status` | `App.tsx`, `Header.tsx`, `DetectionViewer.tsx`, `ImageAnalysisSection.tsx` | Estado real del motor de visión (`yolo_ready`, `active_model`, `device`, `is_fallback`, `is_diagnostic`, `model_mode`). |
| `GET /api/v1/deteccion/categories` | `App.tsx`, `DetectionViewer.tsx` | Catálogo oficial de categorías viales (`poste_luz`, `vegetacion_invasiva`, `obstruccion_via`, `otro`) y umbrales por categoría (`default_thresholds`). |
| `GET /api/v1/drones` | `App.tsx` | Recupera drones registrados y su estado inicial. |
| `POST /api/v1/drones/{drone_id}/command` | `DroneStatusCard.tsx` | Envía comandos operativos (`takeoff`, `hover`, `resume_patrol`, `land`, `return_to_home`). |
| `GET /api/v1/telemetria/{drone_id}/latest` | `App.tsx`, `DroneStatusCard.tsx`, `TelemetryPanel.tsx` | Recupera la última muestra de telemetría 3D en SQLite al iniciar o reconectar. |
| `GET /api/v1/cameras/status` | `App.tsx`, `LiveCameraFeed.tsx` | Estado operativo de cámaras (`is_active`, `resolution`, `fps`, `connected_drones`). |
| `GET /api/v1/cameras/{drone_id}/latest-frame?annotated=true` | `App.tsx`, `LiveCameraFeed.tsx` | Recupera el último fotograma disponible con metadatos (`frame_base64`, `captured_at`, `is_fresh`, `width`, `height`). |
| `POST /api/v1/imagenes/analyze` | `ImageAnalysisSection.tsx` | Sube y analiza imágenes JPG/JPEG/PNG externas devolviendo `ImageAnalysisResponse` con detecciones clasificadas e imagen anotada en Base64. |
| `GET /api/v1/incidentes` | `IncidentLog.tsx` | Consulta incidentes en SQLite con filtros combinados (`tipo`, `severidad`, `estado`, `search`, `has_image`, `limit`). |
| `GET /api/v1/incidentes/stats` | `IncidentLog.tsx` | Obtiene métricas agregadas de SQLite (`total_incidentes`, `por_tipo`, `por_severidad`, `por_estado`, `con_imagen`, `confianza_promedio`). |
| `POST /api/v1/incidentes` | `ImageAnalysisSection.tsx` | Permite registrar una detección de imagen externa como incidente persistido en SQLite. |
| `PATCH /api/v1/incidentes/{id}` | `IncidentLog.tsx` | Actualiza el estado operativo (`reportado`, `en_revision`, `atendido`, `descartado`) o severidad de un incidente. |
| `DELETE /api/v1/incidentes/{id}` | `IncidentLog.tsx` | Elimina permanentemente un incidente de SQLite. |
| `GET /api/v1/incidentes/{id}/imagen?download=true` | `IncidentLog.tsx` | Previsualiza en el panel o descarga la fotografía capturada vinculada al incidente. |

### 3.2 Mensajes WebSocket (`ws://127.0.0.1:8000/ws`)

| Evento (`type`) | Dirección | Manejo en `useWebSocket.ts` y Componentes |
| :--- | :--- | :--- |
| `connection_ack` | Servidor → Cliente | Confirma handshake inicial y marca canal como conectado. |
| `ping` / `pong` | Bidireccional | Latido cada 20 s para mantener viva la conexión y detectar caídas. |
| `telemetry` | Servidor → Cliente | Actualiza en tiempo real `DroneStatusCard` y `TelemetryPanel`. |
| `camera_stream` | Servidor → Cliente | Actualiza el visor `LiveCameraFeed` y las detecciones en `DetectionViewer`. |
| `incident` | Servidor → Cliente | Inserta o actualiza por deduplicación un nuevo incidente en `IncidentLog` y refresca estadísticas. |
| `incident_updated` | Servidor → Cliente | Sincroniza cambios de estado o severidad de un incidente en `IncidentLog`. |
| `incident_deleted` | Servidor → Cliente | Remueve en tiempo real el incidente eliminado de `IncidentLog`. |

---

## 4. Mejoras Implementadas en la Semana 9

1. **Eliminación de Datos de Demostración Engañosos (Tarea 8):**
   - `DroneStatusCard` y `TelemetryPanel` ya no muestran `100.0%` de batería ni coordenadas `0.00 m` como si hubiera un dron transmitiendo cuando `telemetry === null`; muestran indicadores explícitos de `SIN SEÑAL` / `--` hasta recibir datos reales.
   - `LiveCameraFeed` ya no muestra la insignia `EN VIVO` cuando no hay fotograma; distingue entre `EN VIVO`, `FOTOGRAMA EN CACHÉ` y `SIN SEÑAL`.
   - `DetectionViewer` distingue entre el estado sin fotograma activo (`Sin fotograma activo en inspección`) y el estado con fotograma analizado sin anomalías (`Vía despejada`).
2. **Visualización Completa de Detecciones Viales (Tarea 4):**
   - Barra de desglose y filtrado rápido por categoría (`Todas`, `Postes`, `Vegetación`, `Obstáculos`, `Otros`).
   - Presentación de todos los campos reales de `RoadDetectionItem`: `normalized_category`, `raw_label`, `confidence`, `severity`, `review_status`, `description`, `justification`, `bbox` con dimensiones en píxeles, `is_incident_candidate`, `incident_id`, `is_duplicate` / `repetition_count`, `simulation_coords` y `frame_id`.
3. **Gestión Completa de Incidentes SQLite (Tarea 5):**
   - Barra de métricas en tiempo real conectada a `GET /api/v1/incidentes/stats`.
   - Filtros combinados por categoría, severidad, estado operativo, presencia de foto y búsqueda por texto en la descripción.
   - Visor integrado de evidencia fotográfica (`GET /api/v1/incidentes/{id}/imagen?download=true`) y sincronización con eventos WebSocket `incident`, `incident_updated` e `incident_deleted`.
4. **Carga Manual de Imágenes JPG/PNG y Promoción a Incidente (Tarea 6):**
   - Validación en cliente y servidor, desglose por categorías viales, visualización de imagen original vs anotada y botón para registrar cualquier detección de una fotografía externa en la tabla `incidentes` de SQLite.
5. **Manejo de Errores de Red y Recuperación de Conexión (Tarea 7):**
   - Banner global de desconexión y reconexión con botón **Reconectar Ahora** y botón **Sincronizar** en la cabecera.
   - Mensajes de error legibles ante caídas de red o respuestas HTTP 4xx/5xx en `api.ts`.
   - Reconexión automática WebSocket con backoff exponencial (`1.5s` a `15s`).

---

## 5. Dependencias del Backend

El backend requiere el entorno Python (3.10+) con las dependencias listadas en `backend/requirements.txt`:
- `fastapi`, `uvicorn[standard]`, `python-multipart`, `websockets`
- `sqlalchemy`, `pydantic`, `pydantic-settings`
- `opencv-python`, `numpy`, `Pillow`
- `ultralytics` (opcional; si no está disponible o no hay pesos, el motor conmuta automáticamente al detector heurístico OpenCV).

