# SEMANA 6 — CLASIFICACIÓN DE OBJETOS Y GENERACIÓN DE DETECCIONES VIALES
**Sistema de Detección e Inspección de Vías con Dron Autónomo**

Documentación Técnica de Entrega  
Fecha: 18 de Octubre de 2026  
Rol: Ingeniero Sénior de Visión Artificial, Inspección Vial y Backend FastAPI

---

## 1. Resumen Ejecutivo y Alcance

La **Semana 6** implementa una capa desacoplada de interpretación y clasificación de detecciones visuales para el sistema de inspección vial con dron autónomo. Esta capa se sitúa entre el motor de visión artificial (Semana 5) y los subsistemas de almacenamiento (SQLite), difusión en tiempo real (FastAPI WebSockets) y visualización en el dashboard (React/TypeScript).

```
                      +--------------------------------------------------+
                      |         Motor de Visión Artificial (Sem. 5)      |
                      |        YOLODetector / HeuristicDetector          |
                      |               VisionModel.analyze()              |
                      +--------------------------------------------------+
                                               |
                                               v List[DetectionItem] (en bruto)
                      +--------------------------------------------------+
                      |      RoadClassificationService (Semana 6)        |
                      | - Normalización a categorías viales objetivo     |
                      | - Validación geométrica estricta de Bounding Box |
                      | - Umbrales de confianza configurables            |
                      | - Criterio prudencial: detección vs incidente    |
                      | - Deduplicación espacio-temporal (5s / 2.5m)     |
                      | - Vinculación de posición Webots (no GPS)        |
                      +--------------------------------------------------+
                                       |                 |
             +-------------------------+                 +-------------------------+
             v                                                                     v
+-------------------------------+                                 +-------------------------------+
|  Generación Calificada SQLite |                                 |  Transmisión WebSocket & API  |
| - Tabla 'incidentes' (1499+)  |                                 | - Canal 'camera_stream'       |
| - Coordenadas métricas nulas  |                                 | - Canal 'incident'            |
|   si no hay telemetría        |                                 | - POST /deteccion/classify    |
| - Sin falsear a (0,0,0)       |                                 | - GET  /deteccion/categories  |
+-------------------------------+                                 +-------------------------------+
                                                                                   |
                                                                                   v
                                                                  +-------------------------------+
                                                                  |  Dashboard React (TypeScript) |
                                                                  | - DetectionViewer enriquecido |
                                                                  | - IncidentLog tolerante a null|
                                                                  +-------------------------------+
```

---

## 2. Categorías Objetivo del Proyecto y Normalización

El sistema normaliza cualquier salida del modelo a tres categorías objetivo canónicas y una categoría de reserva segura:

| Categoría Normalizada | Constante | Umbral por Defecto | Criterio de Riesgo / Severidad |
| :--- | :--- | :--- | :--- |
| **Postes de luz** | `poste_luz` | `0.45` | Activo de infraestructura fija. Severidad `baja`. Se registra como detección de inventario sin generar alarma crítica a menos que haya daño estructural. |
| **Vegetación invasiva** | `vegetacion_invasiva` | `0.55` | Maleza, ramas o árboles que invaden la franja central de la vía o gálibo (>5% del encuadre). Severidad `alta` o `media`. La vegetación periférica lateral se cataloga prudentemente como `vegetacion` con revisión pendiente. |
| **Obstrucciones de vía** | `obstruccion_via` | `0.50` | Objetos, rocas, escombros o vehículos bloqueando la circulación en el eje de tránsito. Personas en vía elevan a severidad `critica`. Vehículos a severidad `alta`. |
| **No catalogado / Otro** | `otro` | `0.60` | Clases no reconocidas por el catálogo vial. Se gestionan de forma segura sin provocar excepciones en el servidor y se marcan como `pendiente_revision`. |

### 2.1 Criterio de Calificación Prudencial (Detección vs Incidente)
Cumpliendo la directriz de la sección 4:
- **No toda vegetación es invasiva:** Un árbol o arbusto en los márgenes exteriores de la vía es vegetación lateral normal (`is_incident_candidate=False`, `severidad="baja"`). Únicamente cuando la masa vegetal invade la zona central de tránsito (`(0.25*w) <= center_x <= (0.75*w)`) o supera un área crítica, se califica como incidente vial (`is_incident_candidate=True`).
- **No todo objeto es un obstáculo peligroso:** Un objeto lejano o fuera de la calzada permanece como detección informativa. Si el modelo no cuenta con evidencia concluyente de obstrucción activa, se asigna `review_status="pendiente_revision"`.

---

## 3. Limitaciones Reales del Modelo Configurado

### 3.1 Auditoría de Pesos `yolov8n.pt`
- El archivo `backend/storage/weights/yolov8n.pt` corresponde al modelo oficial YOLOv8n entrenado sobre el dataset **MS-COCO** (80 clases).
- **Limitación honesta:** COCO no incluye clases nativas viales como `poste_luz`, `vegetacion_invasiva` u `obstruccion_via`.
- **Estrategia adoptada:**
  - `YOLODetector` opera en modo `pretrained_generic`, leyendo exactamente las 80 clases COCO.
  - La capa `RoadClassificationService` aplica un mapeo controlado: etiquetas COCO como `car`, `truck`, `bus`, `person` se mapean hacia `obstruccion_via` cuando ocupan la zona de calzada, conservando su etiqueta original en `raw_label` y explicando el motivo en `justification`.
  - `HeuristicDetector` de OpenCV sí implementa análisis de colorimetría HSV, Canny y correlación espacial para detectar directamente las 3 clases viales en la simulación.
  - Cuando se entrene o suministre un modelo especializado (`best.pt`) en la Semana 7, `YOLODetector` detectará automáticamente las clases de infraestructura e intercambiará a modo `specialized_infrastructure`.

---

## 4. Representación Rigurosa de Ubicación y Coordenadas

### 4.1 Coordenadas Locales Webots vs GPS
- **Coordenadas de Simulación:** `pos_x`, `pos_y`, `pos_z` representan metros dentro del marco cartesiano del mundo 3D de Webots (`coordinate_system="simulation_webots_cartesian_meters"`).
- **Garantía:** El sistema **no inventa coordenadas GPS (latitud/longitud)** ficticias a partir de la simulación. El campo `gps_coords` permanece como `None` explícito con aviso documental.
- **Ubicación ausente:** Cuando un fotograma no cuenta con telemetría asociada, las coordenadas se reportan como `None`. No se fuerza `(0, 0, 0)` para evitar falsas concentraciones de incidentes en el origen del mundo.

---

## 5. Validación Geométrica y Deduplicación Espacio-Temporal

### 5.1 Validador de Cajas Delimitadoras (`BoundingBoxValidator`)
Rechaza anomalías de visión:
- Inversiones geométricas: `x_min >= x_max` o `y_min >= y_max`.
- Cajas degeneradas con ancho o alto `< 2.0 px` o área `< 4.0 px²`.
- Coordenadas fuertemente negativas (`< -1.0 px`).
- Valores inválidos `NaN` o `Inf`.

### 5.2 Rastreador de Deduplicación (`DeduplicationTracker`)
- **Ventana temporal:** 5.0 segundos.
- **Rejilla espacial:** 2.5 metros en coordenadas locales de simulación.
- **Clave:** `spatial_{drone_id}_{category}_{grid_x}_{grid_y}` (o `visual_{drone_id}_{category}_{cx}_{cy}` si no hay coordenadas).
- **Comportamiento:** Si un mismo poste u obstáculo es capturado durante 30 frames consecutivos mientras el dron vuela lentamente, el primer frame registra el incidente y los 29 siguientes se etiquetan como `is_duplicate=True` con contador de repeticiones `repetition_count`, evitando saturar la base de datos y la interfaz con miles de alertas idénticas.

---

## 6. Endpoints y Contratos de Datos

### 6.1 `POST /api/v1/deteccion/classify`
Recibe un lote de detecciones y contexto espacial, aplicando el pipeline completo de la Semana 6:
```json
{
  "drone_id": "drone-webots-01",
  "frame_id": "frame_001",
  "pos_x": 12.5,
  "pos_y": -4.2,
  "pos_z": 6.0,
  "raw_detections": [
    {
      "label": "tree",
      "confidence": 0.85,
      "bbox": { "x_min": 240, "y_min": 200, "x_max": 400, "y_max": 410 }
    }
  ]
}
```
**Respuesta:**
```json
{
  "drone_id": "drone-webots-01",
  "timestamp": "2026-10-18T13:00:00Z",
  "total_input": 1,
  "total_valid": 1,
  "total_rejected": 0,
  "total_incidents_qualified": 1,
  "detections": [
    {
      "id": "e6a21390-1e5b-4cb1-841f-cf92cbb391ec",
      "label": "vegetacion_invasiva",
      "normalized_category": "vegetacion_invasiva",
      "raw_label": "tree",
      "confidence": 0.85,
      "bbox": { "x_min": 240, "y_min": 200, "x_max": 400, "y_max": 410 },
      "severity": "alta",
      "review_status": "reportado",
      "simulation_coords": { "pos_x": 12.5, "pos_y": -4.2, "pos_z": 6.0 },
      "coordinate_system": "simulation_webots_cartesian_meters",
      "gps_coords": null,
      "is_incident_candidate": true,
      "is_duplicate": false,
      "validation_passed": true,
      "justification": "Vegetación invasiva ocupando franja de vía (14.2% del encuadre). Posible invasión de gálibo."
    }
  ],
  "processing_time_ms": 1.25
}
```

### 6.2 `GET /api/v1/deteccion/categories`
Consulta catálogo de categorías, umbrales configurables y estado de sensores.

---

## 7. Guía de Reutilización para el Responsable de la Semana 7

Para el desarrollador encargado de la **Semana 7** (Carga de Imágenes Externas e Ingesta Offline):

### Opción 1: En código Python backend
```python
from backend.app.modules.deteccion.service import detection_service
from backend.app.modules.clasificacion.service import classification_service

# 1. Obtener detecciones con el motor de visión
raw_dets, annotated_cv, inference_ms = detection_service.process_frame(
    image=image_bgr,
    drone_id="external_source_01",
    threshold=0.45
)

# 2. Interpretar y clasificar con la capa de la Semana 6
# (Si no hay telemetría del dron externo, pasar pos_x=None)
result = classification_service.classify_detections(
    raw_detections=raw_dets,
    drone_id="external_source_01",
    pos_x=None, pos_y=None, pos_z=None
)

for det in result.detections:
    print(f"Categoría: {det.normalized_category} ({det.confidence*100:.1f}%)")
    print(f"Estado de revisión: {det.review_status}")
    print(f"¿Es candidato a incidente?: {det.is_incident_candidate}")
```

### Opción 2: A través de HTTP REST
1. Enviar imagen a `POST /api/v1/deteccion/detect`.
2. Para clasificación desacoplada de metadatos, enviar a `POST /api/v1/deteccion/classify`.

---

## 8. Resultados de Verificación y Pruebas Automatizadas

Se ejecutó la suite completa de pruebas unitarias, de integración y de regresión:
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v
```

### Resumen de Pruebas:
- **`test_backend.py`:** 11 pruebas (ciclo de vida del dron, telemetría, ingesta de frames, WebSocket, incidentes). -> **11 PASS**.
- **`test_vision_engine.py`:** 16 pruebas (ImageProcessor, YOLOv8 auténtico, HeuristicDetector, fallback, singleton, resiliencia). -> **16 PASS**.
- **`test_semana_6_classification.py`:** 10 pruebas nuevas cubriendo los 10 requisitos de la sección 8. -> **10 PASS**.
- **Total:** **37 pruebas pasando al 100% (0 fallos, 0 regresiones)** en 6.99 segundos.
