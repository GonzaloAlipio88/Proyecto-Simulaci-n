# AUDITORÍA TÉCNICA PREVIA Y DIAGNÓSTICO DE ARQUITECTURA (SEMANA 6)
**Sistema de Detección e Inspección de Vías con Dron Autónomo**

Fecha de Auditoría: 18 de Octubre de 2026  
Rol: Ingeniero Sénior de Visión Artificial, Inspección Vial y Backend FastAPI  
Fase: Semana 6 — Clasificación de Objetos y Generación de Detecciones Viales

---

## 1. Diagnóstico del Motor de Visión y Contratos de la Semana 5

### 1.1 Interfaz `VisionModel`
- **Ubicación:** `backend/app/modules/deteccion/base.py`
- **Firma verificada:**
  ```python
  def analyze(
      self,
      image: np.ndarray,
      confidence_threshold: float = 0.5,
      frame_id: Optional[str] = None,
      timestamp: Optional[datetime] = None
  ) -> List[DetectionItem]:
  ```
- **Alias retrocompatible:** `detect(image, confidence_threshold)`.
- **Implementaciones disponibles:**
  1. `YOLODetector` (`yolo_adapter.py`): Inferencia sobre Ultralytics YOLOv8 con pesos locales (`storage/weights/yolov8n.pt`).
  2. `HeuristicDetector` (`mock_detector.py`): Reglas de OpenCV basadas en espacio HSV (vegetación), Canny (postes de luz verticales) y ROI de calzada (obstáculos).
  3. `DiagnosticDetector` (`mock_detector.py`): Modo explícito que no inventa datos cuando faltan dependencias o pesos.
  4. `DetectionService` (`service.py`): Administrador central con control de concurrencia y singleton de modelo.

### 1.2 Contrato de Detección `DetectionItem`
- **Ubicación:** `backend/app/schemas/deteccion.py`
- **Campos existentes:** `label`, `class_name` (sincronizados automáticamente), `confidence` (0.0 a 1.0), `bbox` (`BoundingBox` con `x_min, y_min, x_max, y_max`), `severity` (`baja`, `media`, `alta`, `critica`), `description`, `frame_id`, `timestamp`.

---

## 2. Diagnóstico de Telemetría, Ubicación y Coordenadas

### 2.1 Representación Actual de la Ubicación
- **En Telemetría (`models/telemetria.py`):** Los campos `pos_x`, `pos_y`, `pos_z` representan coordenadas métricas cartesianas locales dentro del mundo Webots (origen del mundo Webots en la vía).
- **CRÍTICO - Distinción GPS vs Webots:**
  - Las coordenadas `pos_x`, `pos_y`, `pos_z` **NO son coordenadas geográficas GPS** (latitud, longitud, altitud WGS84).
  - No existe un sensor GPS real configurado en el archivo `.wbt` que emita grados decimales.
  - **Directriz Semana 6:** Se debe indicar explícitamente `coordinate_system = "simulation_webots_cartesian_meters"`. No se deben inventar coordenadas GPS ficticias a partir de las coordenadas de simulación. Cuando no se suministren coordenadas en un fotograma, debe devolverse `None` (valor ausente) y documentarse formalmente.

---

## 3. Diagnóstico de Base de Datos SQLite y Almacenamiento

### 3.1 Base de Datos Existente
- **Archivo:** `backend/storage/data.db` (SQLite 3.50.4).
- **Registros auditados en caliente:**
  - `incidentes`: 1,499 registros históricos.
  - `imagenes`: 1,115 registros.
  - `telemetria`: 4,174 registros.
  - `drones`: 2 registros.
- **Restricción de preservación:** Queda terminantemente prohibido borrar o reiniciar la base de datos `data.db`.
- **Hallazgo técnico en tabla `incidentes`:** Las columnas `pos_x, pos_y, pos_z` tienen restricción histórica `NOT NULL`. Para soportar detecciones sin ubicación conocida de forma natural sin falsear a `(0, 0, 0)`, se aplicará una migración estándar en SQLite que preserve el 100% de las 1,499 filas previas y permita valores nulos.

### 3.2 Almacenamiento de Fotogramas
- Directorio: `backend/storage/images/`.
- Gestión de guardado en `ImageService` (`imagenes/service.py`): Genera imágenes originales y anotadas `.jpg`.

---

## 4. Diagnóstico de Limitaciones Reales del Modelo YOLO

### 4.1 Pesos Configurables y Clases Disponibles
- Archivo: `backend/storage/weights/yolov8n.pt` (6.5 MB, COCO 80 clases).
- **Clases reales de `yolov8n.pt`:**
  - Incluye: `person`, `bicycle`, `car`, `motorcycle`, `airplane`, `bus`, `train`, `truck`, `boat`, `traffic light`, `stop sign`, `bench`, `potted plant`, etc.
  - **NO INCLUYE clases nativas de inspección vial:**
    - No existe `poste_luz` en COCO (lo más cercano son `traffic light` o `street light` inexistente en el estándar).
    - No existe `vegetacion_invasiva` en COCO (únicamente `potted plant`).
    - No existe `obstruccion_via` (existen objetos genéricos como `car`, `truck`, `box`, `bench`).
- **Garantía de honestidad técnica (Directriz Sección 5):**
  - **No se inventarán detecciones COCO como si fuesen especializadas de vía.**
  - `YOLODetector` opera en modo `pretrained_generic` (80 clases).
  - `HeuristicDetector` de OpenCV sí implementa heurísticas especializadas para `poste_luz`, `vegetacion_invasiva` y `obstruccion_via`.
  - La nueva capa de interpretación (`RoadClassificationService`) actuará como puente formal:
    1. Normalizará etiquetas reconocidas (sin alterar arbitrariamente las clases incompatibles).
    2. Manejará datos COCO como candidatos prudenciales con estado `pendiente_revision`.
    3. Dejará preparada la interfaz para modelos finetuneados de la Semana 7 (`best.pt`).

---

## 5. Diagnóstico del Dashboard y Comunicación en Tiempo Real

### 5.1 Endpoints y WebSockets
- `POST /api/v1/cameras/frame`: Recibe fotogramas de Webots o fuentes externas. Actualmente crea incidentes de forma acoplada y emite por WebSocket `camera_stream` e `incident`.
- `GET /api/v1/incidentes`: Filtra por tipo, severidad y estado.
- `GET /api/v1/deteccion/status`: Reporta estado del motor de visión.

### 5.2 Componentes del Dashboard (React / Vite)
- `DetectionViewer.tsx`: Renderiza `latestStream?.detections`. Cuenta con badges para `poste_luz`, `vegetacion_invasiva` y `obstruccion_via`. Requiere ampliación para mostrar hora, coordenadas de simulación y estado de revisión sin crear vistas duplicadas.
- `IncidentLog.tsx`: Muestra la tabla de incidentes desde SQLite. Requiere formateo seguro para coordenadas ausentes.

---

## 6. Estado de las Pruebas de Regresión (Semanas 1 a 5)

- Tras instalar en el entorno virtual `.venv` las dependencias especificadas en `requirements.txt` (`ultralytics`, `torch`, `torchvision`), se ejecutaron las pruebas con el siguiente resultado:
  ```
  backend/tests/test_backend.py: 11 tests PASS
  backend/tests/test_vision_engine.py: 16 tests PASS
  Total: 27 passed, 1 warning (deprecation de TestClient) en 21.75s (100% PASS).
  ```

---

## 7. Plan de Implementación de la Semana 6

1. **Crear Módulo Independiente de Clasificación Vial:**
   - `backend/app/modules/clasificacion/rules.py`: Normalizador de categorías, validación de Bounding Boxes, umbrales configurables y deduplicación espacial/temporal.
   - `backend/app/modules/clasificacion/service.py`: `RoadClassificationService` que desacopla la interpretación de las detecciones del endpoint HTTP.
   - `backend/app/modules/clasificacion/__init__.py`: Exportación unificada.
2. **Actualizar Esquemas y Modelos:**
   - `RoadDetectionItem` en `schemas/deteccion.py` (hereda de `DetectionItem`, 100% retrocompatible).
   - Coordenadas opcionales (`None` si ausente) en `schemas/incidente.py` y `models/incidente.py`.
   - Migración segura en caliente de la tabla `incidentes` para relajar NOT NULL sin perder registros.
3. **Integrar con el Flujo de Fotogramas:**
   - Enlazar `CameraService.ingest_frame` con `classification_service` para clasificar y deduplicar antes de generar incidentes.
   - Publicar detecciones enriquecidas en WebSocket y nuevos endpoints REST `/api/v1/deteccion/classify` y `/api/v1/deteccion/categories`.
4. **Actualizar Dashboard:**
   - Reflejar en `DetectionViewer.tsx` y `IncidentLog.tsx` las categorías normalizadas, estado de revisión y coordenadas claras de simulación.
5. **Crear Suite Integral de Pruebas Semana 6:**
   - `backend/tests/test_semana_6_classification.py` cubriendo los 10 casos exigidos.
   - Verificar no regresión sobre los 27 tests previos.
6. **Entrega y Documentación Técnica Final:**
   - Elaborar `docs/SEMANA_6_CLASIFICACION_Y_DETECCIONES.md` y reporte detallado.
