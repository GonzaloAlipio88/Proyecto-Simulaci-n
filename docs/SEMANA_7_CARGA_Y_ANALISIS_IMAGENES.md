# SEMANA 7 — CARGA Y ANÁLISIS DE IMÁGENES EXTERNAS JPG/PNG
**Sistema de Detección e Inspección de Vías con Dron Autónomo**

Documentación Técnica de Entrega
Fecha: 19 de Octubre de 2026
Rol: Ingeniero Sénior Full-Stack, FastAPI, Python, OpenCV, React, TypeScript y Visión Artificial

---

## 1. Resumen Ejecutivo y Objetivos Cumplidos

La **Semana 7** implementa la capacidad de carga y análisis de fotografías e imágenes externas (formatos JPG, JPEG y PNG) desde el equipo del usuario hacia el sistema de misión.

### Principio Fundamental de Diseño
La fotografía subida desde el computador pasa **exactamente por el mismo motor de visión artificial (Semana 5)** y la **misma capa de clasificación vial (Semana 6)** que utiliza el dron en su simulación con Webots, **sin crear un segundo sistema de análisis ni duplicar modelos**.

### Independencia Operativa de Webots
La funcionalidad opera de manera 100% desacoplada e independiente de Webots: los operadores pueden cargar fotografías tomadas en campo o imágenes históricas y analizarlas aun cuando el simulador Webots esté completamente cerrado o detenido.

---

## 2. Arquitectura del Flujo de Análisis

```
+-----------------------------------------------------------------------------------+
|                            Dashboard React (Semana 7)                             |
|  - Selector Drag & Drop / Input File (.jpg, .jpeg, .png)                          |
|  - Validación de cliente (tipo MIME, extensión, tamaño <= 10 MB)                  |
|  - Vista previa interactiva y extracción de dimensiones naturales                 |
|  - Selector de umbral de confianza y guardado opcional                            |
+-----------------------------------------------------------------------------------+
                                          |
                                          | multipart/form-data
                                          v
+-----------------------------------------------------------------------------------+
|               FastAPI Endpoint: POST /api/v1/imagenes/analyze                     |
|                                (Alias: /api/v1/images/analyze)                    |
|  1. Sanitización de nombre original (evita Directory Traversal)                   |
|  2. Validación estricta de extensión (.jpg, .jpeg, .png) y Content-Type           |
|  3. Lectura segura por bloques (chunk_size=64KB) con tope en 10 MB (HTTP 413)     |
|  4. Decodificación real OpenCV (cv2.imdecode) contra binarios o MIME falseados    |
|  5. Verificación de integridad de matriz uint8 y dimensiones (ImageProcessor)     |
+-----------------------------------------------------------------------------------+
                                          |
                                          | asyncio.to_thread (No bloquea event loop)
                                          v
+-----------------------------------------------------------------------------------+
|                     Motor de Visión Unificado (Semana 5)                          |
|  - detection_service.process_frame(image, skip_if_busy=False)                     |
|  - VisionModel activo: YOLODetector (yolov8n.pt/best.pt) / HeuristicDetector      |
|  - Generación de imagen anotada con cajas delimitadoras en BGR                    |
+-----------------------------------------------------------------------------------+
                                          |
                                          v raw_detections
+-----------------------------------------------------------------------------------+
|                  Capa de Clasificación e Interpretación (Semana 6)                |
|  - classification_service.classify_detections()                                  |
|  - Normalización: 'poste_luz', 'vegetacion_invasiva', 'obstruccion_via', 'otro'   |
|  - Validación geométrica de Bounding Boxes (BoundingBoxValidator)                 |
|  - Ausencia honesta de ubicación: pos_x=None, pos_y=None, pos_z=None              |
|  - gps_coords = None, simulation_coords = None, has_location = False              |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
|                      Almacenamiento Acotado & Salida                              |
|  - ImageService.save_image() con retención acotada de 60 archivos                 |
|  - Inserción en SQLite (ImageRecord con drone_id='external_upload')               |
|  - Codificación instantánea a Base64 JPEG para renderizado en frontend            |
|  - Construcción de ImageAnalysisResponse estructurada y tipada                    |
+-----------------------------------------------------------------------------------+
```

---

## 3. Especificación Técnica de los Endpoints

El backend expone el endpoint principal y su alias en inglés para máxima compatibilidad:
- **`POST /api/v1/imagenes/analyze`**
- **`POST /api/v1/images/analyze`**

### Parámetros de Entrada (`multipart/form-data`)

| Campo | Tipo | Requerido | Descripción |
| :--- | :--- | :--- | :--- |
| `file` | `UploadFile` | Sí | Archivo binario de la imagen (`.jpg`, `.jpeg`, `.png`). |
| `confidence_threshold` | `float` (query) | No | Umbral de confianza mínimo (0.0 a 1.0). Por defecto toma `settings.DETECTION_CONFIDENCE_THRESHOLD` (0.50). |
| `save_to_storage` | `bool` (query) | No | Indica si la imagen y su versión anotada deben registrarse en SQLite y en disco con retención acotada (por defecto `true`). |

### Validaciones y Medidas de Seguridad Implementadas

1. **Límite de Tamaño (10 MB):**
   - Configurable en `settings.MAX_IMAGE_UPLOAD_SIZE_BYTES` (10,485,760 bytes).
   - Se procesa en streaming por fragmentos de 64 KB sin cargar archivos infinitos en RAM.
   - Si se supera el límite, se cancela la lectura inmediatamente y se responde con `HTTP 413 Content Too Large`.
2. **Rechazo de Archivos Vacíos:**
   - Si el archivo contiene 0 bytes, responde con `HTTP 400 Bad Request`.
3. **Validación de Extensión y MIME:**
   - Admitidos: `.jpg`, `.jpeg`, `.png` y tipos MIME `image/jpeg`, `image/png`, `application/octet-stream`.
   - Archivos ejecutables (`.exe`, `.sh`, `.bat`) o documentos (`.pdf`, `.txt`) son rechazados con `HTTP 400 Bad Request`.
4. **Validación de Contenido Real (Anti-Spoofing):**
   - Se decodifica con `cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)`.
   - Si un archivo binario malicioso o ejecutable tiene extensión `.jpg` cambiada artificialmente, OpenCV retorna `None` y el endpoint responde `HTTP 400 Bad Request` indicando que el contenido está corrupto o no corresponde a una imagen válida.
5. **Prevención de Directory Traversal:**
   - Se sanea el nombre de archivo mediante `Path(filename).name` y expresiones regulares (`re.sub(r'[^a-zA-Z0-9_.-]', '_', safe_name)`).
   - Los nombres internos para almacenamiento se generan con prefijos seguros y UUIDs únicos (`external_upload_YYYYMMDD_HHMMSS_<uuid>.jpg`).
6. **No Bloqueo del Servidor:**
   - La decodificación OpenCV, inferencia de visión y clasificación se ejecutan en subprocesos de trabajo usando `asyncio.to_thread`, manteniendo libre el event loop de FastAPI para la telemetría del dron y WebSockets.
7. **Control de Concurrencia:**
   - El parámetro `skip_if_busy=False` en `process_frame` asegura que una fotografía externa espere el bloqueo de inferencia sin descartarse por desbordamiento de frames.

### Estructura de Respuesta JSON (`ImageAnalysisResponse`)

```json
{
  "analysis_id": "4b971a82-f5ce-40de-a5d6-d36c1a851bf2",
  "original_filename": "inspeccion_via_01.jpg",
  "stored_filename": "external_upload_20261019_204718_42920e50.jpg",
  "dimensions": {
    "width": 1920,
    "height": 1080,
    "channels": 3
  },
  "format": "JPEG",
  "size_bytes": 145892,
  "timestamp": "2026-10-19T20:47:18.123456Z",
  "status": "success",
  "detections": [
    {
      "id": "e81d8560-61b6-4b8c-b033-9fb4bf6e9df5",
      "label": "vegetacion_invasiva",
      "class_name": "vegetacion_invasiva",
      "normalized_category": "vegetacion_invasiva",
      "raw_label": "bush",
      "confidence": 0.88,
      "bbox": {
        "x_min": 140.0,
        "y_min": 210.0,
        "x_max": 380.0,
        "y_max": 520.0
      },
      "severity": "alta",
      "review_status": "reportado",
      "description": "Vegetación invasiva ocupando gálibo central de la vía.",
      "frame_id": "ext_4b971a82",
      "timestamp": "2026-10-19T20:47:18.123456Z",
      "drone_id": "external_upload",
      "simulation_coords": null,
      "coordinate_system": "simulation_webots_cartesian_meters",
      "gps_coords": null,
      "image_id": 42,
      "is_incident_candidate": true,
      "validation_passed": true,
      "rejection_reason": null,
      "is_duplicate": false,
      "repetition_count": 1,
      "justification": "Maleza que invade el gálibo ferroviario o vial."
    }
  ],
  "total_detected": 1,
  "total_valid": 1,
  "total_rejected": 0,
  "has_location": false,
  "simulation_coords": null,
  "gps_coords": null,
  "location_notice": "Ubicación geográfica no disponible: Fotografía externa sin coordenadas de simulación ni GPS.",
  "inference_time_ms": 48.25,
  "classification_time_ms": 2.15,
  "processing_time_ms": 53.40,
  "model_info": {
    "name": "yolov8n.pt",
    "backend": "yolo",
    "is_available": true,
    "is_fallback": false,
    "is_diagnostic": false,
    "model_mode": "pretrained_generic",
    "device": "cpu",
    "warnings": [
      "Modelo YOLOv8 preentrenado estándar (COCO 80 clases). Detecciones asociadas a categorías viales según reglas de la Semana 6."
    ]
  },
  "image_id": 42,
  "original_image_url": "/api/v1/imagenes/file/external_upload_20261019_204718_42920e50.jpg",
  "annotated_image_url": "/api/v1/imagenes/file/annotated_external_upload_20261019_204718_42920e50.jpg",
  "annotated_image_base64": "/9j/4AAQSkZJRg..."
}
```

---

## 4. Diferenciación de Estados y Coordenadas

| Condición | Campo `status` | Banner en Frontend | Comportamiento |
| :--- | :--- | :--- | :--- |
| **Detecciones válidas encontradas** | `"success"` | Verde (`CheckCircle2`) | Presenta lista detallada de detecciones, badges de clase, severidad y porcentaje de confianza. |
| **Sin anomalías en la fotografía** | `"no_detections"` | Azul/Cian (`ShieldCheck`) | Informa que la vía está despejada y libre de anomalías. **Se distingue claramente de un fallo**. |
| **Error en archivo o procesamiento** | `"error"` o HTTP 4xx/5xx | Rojo (`AlertTriangle`) | Muestra el detalle seguro del error sin bloquear la interfaz. |

### Política de Coordenadas
Para imágenes externas, se respeta estrictamente el principio de transparencia:
- `has_location`: `false`
- `simulation_coords`: `null`
- `gps_coords`: `null`
- `location_notice`: `"Ubicación geográfica no disponible: Fotografía externa sin coordenadas de simulación ni GPS."`
- **En ningún caso se inventan coordenadas ficticias ni se asigna (0,0,0)**.

---

## 5. Componente Frontend en Dashboard (`ImageAnalysisSection.tsx`)

Se incorporó una nueva sección interactiva en el Dashboard de React sin alterar los componentes existentes:
- **Área Drag & Drop:** Permite arrastrar fotografías o seleccionarlas con explorador de archivos nativo.
- **Validación en Cliente:** Verifica extensión (`.jpg`, `.jpeg`, `.png`) y tamaño (`<= 10 MB`) antes de realizar la petición HTTP.
- **Vista Previa & Metadatos:** Presenta resolución en píxeles (ancho × alto), tamaño en KB/MB y formato.
- **Selector de Umbral:** Slider interactivo para ajustar el umbral de confianza (10% a 90%).
- **Protección contra Doble Envío:** Deshabilita el botón durante el análisis y muestra spinner de carga.
- **Visor Comparativo:** Permite alternar entre la fotografía original y la versión anotada con cajas delimitadoras.
- **Botón de Reset:** "Seleccionar Otra" para limpiar el estado y analizar nuevas imágenes consecutivamente.
- **Reutilización Visual:** Emplea los mismos estilos de tarjeta, insignias de severidad y barras de confianza del `DetectionViewer` de la Semana 6.

---

## 6. Resultados de las Pruebas Automatizadas

Se diseñó e implementó la suite completa de pruebas en `backend/tests/test_semana_7_image_upload.py`, complementando las suites de regresión de las semanas anteriores.

### Matriz de Ejecución de Pruebas (51/51 PASSED - 100%)

| Módulo de Pruebas | Casos | Resultado | Alcance Validado |
| :--- | :---: | :---: | :--- |
| **`test_semana_7_image_upload.py`** | **14** | **14 PASSED** | Carga válida JPG, carga válida PNG, archivo vacío (400), imagen corrupta (400), extensiones prohibidas (400), archivo >10MB (413), MIME falseado (400), manejo de excepciones en motor de visión, modo diagnóstico honesto, imagen sin detecciones vs fallo, campos estructurados completos, ausencia de coordenadas ficticias, endpoint alias `/images/analyze`, regresión. |
| **`test_vision_engine.py`** | **16** | **16 PASSED** | Motor de visión Semana 5, validación de arrays uint8 en OpenCV, BGR/RGB, base64, carga de pesos YOLO, inferencia real, conmutación heurística y modo diagnóstico. |
| **`test_semana_6_classification.py`** | **10** | **10 PASSED** | Normalización de categorías viales, validación geométrica de BBox, deduplicación espacio-temporal, criticidad prudencial y tolerancia a coordenadas nulas. |
| **`test_backend.py`** | **11** | **11 PASSED** | Ciclo de vida de drones, telemetría, gestión de incidentes en SQLite, WebSocket en tiempo real y endpoints de cámara. |
| **Total Global del Proyecto** | **51** | **51 PASSED (100%)** | **Cero regresiones. Sistema totalmente operativo y verificado.** |

Comando de verificación ejecutado:
```bash
py -m pytest -v backend/tests/
```

---

## 7. Guía de Integración para el Responsable de la Semana 8 (Registro de Incidentes)

Para el compañero encargado de la **Semana 8** (persistencia avanzada y gestión integral de incidentes), se detalla la integración directa con los análisis de imágenes externas:

1. **Identificador de Imagen (`image_id`):**
   - Cuando el parámetro `save_to_storage=true` está activo, la imagen analizada queda registrada en la tabla `imagenes` de SQLite.
   - La respuesta del análisis retorna `data.image_id`, correspondiente a la clave primaria `ImageRecord.id`.
2. **Candidatos a Incidente (`is_incident_candidate`):**
   - Cada detección en `data.detections` incluye el booleano `is_incident_candidate: bool`.
   - Si `is_incident_candidate` es `true` y `validation_passed` es `true`, la detección califica para ser promovida a la tabla `incidentes`.
3. **Mapeo de Datos Recomendado para Crear un `Incidente`:**
   ```python
   # Esquema para registrar incidente a partir de detección externa:
   incidente_payload = {
       "drone_id": "external_upload",         # Identifica origen fotográfico externo
       "tipo": detection.normalized_category, # 'poste_luz', 'vegetacion_invasiva', 'obstruccion_via'
       "severidad": detection.severity,       # 'baja', 'media', 'alta', 'critica'
       "descripcion": detection.description,   # Criterio explicativo generado por clasificación
       "confidence": detection.confidence,     # Nivel de confianza numérico
       "pos_x": None,                         # None honesto: no inventar coordenadas
       "pos_y": None,
       "pos_z": None,
       "imagen_id": response.image_id,        # Vínculo con registro físico en tabla imagenes
       "estado": "reportado"                  # Estado inicial de ciclo de vida
   }
   ```
4. **Consulta de Fotografías Almacenadas:**
   - La imagen original se puede obtener mediante `GET /api/v1/imagenes/file/{stored_filename}`.
   - La versión con cajas delimitadoras está disponible en `GET /api/v1/imagenes/file/annotated_{stored_filename}`.
