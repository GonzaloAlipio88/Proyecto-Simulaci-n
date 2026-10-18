# SEMANA 5 — MOTOR DE VISIÓN ARTIFICIAL (OPENCV Y YOLO)
**Sistema de Detección e Inspección de Vías con Dron Autónomo**

Este documento detalla la arquitectura, configuración, ciclo de vida y contratos de datos del Motor de Visión Artificial implementado en la Semana 5.

---

## 1. Arquitectura del Motor de Visión

El motor implementa el patrón **Adapter / Strategy** desacoplado para permitir intercambiar motores de inferencia visual sin alterar el backend ni el dashboard:

```
                          +-------------------------+
                          |   Entrada de Fotograma   |
                          | (Base64 / BGR / Bytes)  |
                          +-------------------------+
                                       |
                                       v
                    +------------------------------------+
                    |        ImageProcessor (OpenCV)     |
                    | - Validación de dimensiones/uint8  |
                    | - Decodificación segura Base64/BGR |
                    | - Espacio de color (BGR / RGB)     |
                    +------------------------------------+
                                       |
                                       v
                         +---------------------------+
                         |  Interfaz VisionModel     |
                         |  .analyze(image, ...)     |
                         +---------------------------+
                                       |
            +--------------------------+--------------------------+
            |                          |                          |
            v                          v                          v
+-----------------------+  +-----------------------+  +-----------------------+
|   YOLODetector        |  |   HeuristicDetector   |  |  DiagnosticDetector   |
| (Ultralytics v8/v11)  |  |  (OpenCV HSV/Canny)   |  | (Diagnóstico explícito|
| - Carga singleton     |  | - Reglas espaciales   |  |   sin inventar datos) |
| - Soporte CPU/GPU     |  | - Detección funcional |  | - Reporta razón de    |
| - Sin descargas auto  |  | - Fallback seguro     |  |   ausencia de pesos   |
+-----------------------+  +-----------------------+  +-----------------------+
            |                          |                          |
            +--------------------------+--------------------------+
                                       |
                                       v
                     +-----------------------------------+
                     | List[DetectionItem] Estructurado  |
                     | + Latencia (ms) + Anotación BGR   |
                     +-----------------------------------+
```

---

## 2. Requisitos e Instalación

### 2.1 Entorno Base (OpenCV y Procesamiento)
Incluido en `backend/requirements.txt`:
```bash
pip install opencv-python-headless>=4.9.0.80 numpy>=1.26.4 pillow>=10.2.0
```

### 2.2 Entorno con Inferencia YOLO (Opcional / Producción)
Para habilitar inferencia profunda con Ultralytics y PyTorch:
```bash
pip install ultralytics>=8.1.0 torch>=2.0.0 torchvision>=0.15.0
```

> **Compatibilidad de Hardware:**
> El sistema **no requiere GPU NVIDIA**. Por defecto opera en modo CPU de alta compatibilidad. Si el servidor cuenta con CUDA habilitado y controladores NVIDIA, se activa automáticamente asignando `YOLO_DEVICE=cuda` o `YOLO_DEVICE=auto`.

---

## 3. Configuración y Variables de Entorno

Definidas en `backend/app/core/config.py` y parametrizables vía `.env`:

| Variable | Tipo | Default | Descripción |
| :--- | :--- | :--- | :--- |
| `DETECTION_MODEL_TYPE` | `str` | `"heuristic"` | Motor activo: `"heuristic"`, `"yolo"` o `"diagnostic"` |
| `YOLO_WEIGHTS_PATH` | `str` | `"storage/weights/best.pt"` | Ruta del archivo de pesos entrenados (`.pt`) |
| `YOLO_DEVICE` | `str` | `"cpu"` | Dispositivo de cálculo: `"cpu"`, `"cuda"`, o `"auto"` |
| `DETECTION_CONFIDENCE_THRESHOLD` | `float` | `0.50` | Umbral mínimo de confianza (0.0 a 1.0) |
| `DETECTION_FALLBACK_TO_HEURISTIC` | `bool` | `True` | Si falta YOLO o sus pesos, cae a OpenCV heurístico |
| `VISION_SKIP_FRAMES_ON_BUSY` | `bool` | `True` | Descarta frames si el motor está ocupado (evita colas) |
| `VISION_ANALYSIS_INTERVAL_FRAMES`| `int` | `1` | Analiza cada N fotogramas (1 = todos los cuadros) |

---

## 4. Comportamiento y Resiliencia ante Ausencia de Pesos

1. **Sin descargas no autorizadas:** El sistema **nunca** descarga modelos pre-entrenados grandes por Internet durante el arranque.
2. **Verificación de archivo:** Si `YOLO_WEIGHTS_PATH` no existe en el sistema de archivos o su tamaño es `< 1KB`, el modelo no intenta cargarse y registra una advertencia controlada en log.
3. **Mecanismo de Fallback:**
   - Con `DETECTION_FALLBACK_TO_HEURISTIC=True`: El sistema pasa de forma transparente al detector heurístico de OpenCV.
   - Con `DETECTION_FALLBACK_TO_HEURISTIC=False`: Se activa `DiagnosticDetector`, reportando `is_diagnostic=True` y retornando 0 detecciones (garantía: **no inventa falsos positivos**).

---

## 5. Esquema de Datos y Contrato de Detección

### 5.1 Estructura de Cada Detección (`DetectionItem`)
```json
{
  "class_name": "poste_luz",
  "label": "poste_luz",
  "confidence": 0.88,
  "bbox": {
    "x_min": 440.0,
    "y_min": 100.0,
    "x_max": 454.0,
    "y_max": 380.0
  },
  "severity": "baja",
  "description": "Poste de luz / columna detectado (relación 3.2)",
  "frame_id": "frame_drone-webots-01_12",
  "timestamp": "2026-10-17T23:15:30.123456Z"
}
```

### 5.2 Clases Monitoreadas en Carretera / Vía
1. `poste_luz`: Postes de alumbrado o columnas de catenaria.
2. `vegetacion_invasiva`: Ramas o maleza que invade la calzada o gálibo.
3. `obstruccion_via`: Obstáculos, rocas o cajas bloqueando el tránsito.

---

## 6. Guía para el Responsable de la Semana 6 (Incidentes)

El responsable de la **Semana 6** (Clasificación de Incidentes) puede interactuar con el motor de visión de dos formas:

### Opción A: A través de `detection_service` en código Python
```python
from backend.app.modules.deteccion.service import detection_service

# image_bgr: np.ndarray (OpenCV uint8 de 3 canales)
detections, annotated_image, elapsed_ms = detection_service.process_frame(
    image=image_bgr,
    drone_id="drone-webots-01",
    threshold=0.50,
    frame_id="frame_001"
)

for det in detections:
    print(f"Detectado: {det.class_name} ({det.confidence * 100:.1f}%)")
    print(f"Caja BBox: [{det.bbox.x_min}, {det.bbox.y_min}] -> [{det.bbox.x_max}, {det.bbox.y_max}]")
    print(f"Severidad sugerida: {det.severity}")
    
    # En la Semana 6, mapear a Incidentes según reglas de negocio:
    if det.severity in ["alta", "critica"] or det.confidence > 0.75:
        # Generar alerta formal de incidente
        pass
```

### Opción B: A través de la API REST
- `POST /api/v1/deteccion/detect`: Envía `{ "image_base64": "...", "drone_id": "...", "threshold": 0.5 }` y recibe `DetectionResult` estructurado con metadatos del modelo utilizado (`model_name`, `backend_used`, `processed_time_ms`).
- `GET /api/v1/deteccion/status`: Consulta el modelo activo, dispositivo (`cpu`/`cuda`), clases y estado de carga.

---

## 7. Ejecución de Pruebas Automatizadas

Para validar toda la suite de visión artificial y regresión:
```powershell
python -m pytest backend/tests/ -v
```
**Resultado:** 22 pruebas pasando al 100% (PASS).
