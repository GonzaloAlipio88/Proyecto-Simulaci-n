from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Dict, Any
from backend.app.core.config import settings
from backend.app.schemas.deteccion import (
    DetectionRequest,
    DetectionResult,
    RoadClassificationRequest,
    RoadClassificationBatchResult
)
from backend.app.modules.deteccion.service import detection_service
from backend.app.modules.deteccion.image_processor import ImageProcessor
from backend.app.modules.clasificacion.service import classification_service
from backend.app.modules.clasificacion.rules import (
    TARGET_ROAD_CATEGORIES,
    DEFAULT_CATEGORY_THRESHOLDS
)

from pydantic import BaseModel, Field

router = APIRouter()

class ThresholdUpdateRequest(BaseModel):
    threshold: float = Field(
        ...,
        ge=0.15,
        le=0.50,
        description="Nuevo umbral de confianza en el intervalo [0.15, 0.50]"
    )

class ThresholdResponse(BaseModel):
    confidence_threshold: float
    min_threshold: float = 0.15
    max_threshold: float = 0.50
    default_threshold: float = 0.25
    updated_at: datetime
    message: str

@router.post("/detect", response_model=DetectionResult)
def run_standalone_detection(req: DetectionRequest):
    """
    Run computer vision detection on an arbitrary base64 image.
    Validates image, runs inference through active VisionModel (YOLO / Heuristic / Diagnostic),
    normalizes and interprets categories (Semana 6), and returns structured detections.
    """
    cv_img = ImageProcessor.base64_to_bgr(req.image_base64)
    if cv_img is None:
        raise HTTPException(
            status_code=400,
            detail="Formato de imagen base64 inválido, corrupto o dimensiones insuficientes"
        )

    now_utc = datetime.now(timezone.utc)
    detections, annotated_cv, elapsed_ms = detection_service.process_frame(
        cv_img,
        drone_id=req.drone_id,
        threshold=req.threshold or settings.DETECTION_CONFIDENCE_THRESHOLD,
        frame_id=req.frame_id,
        timestamp=now_utc
    )

    h, w = cv_img.shape[:2]
    # Enriquecer e interpretar detecciones con la capa de clasificación (Semana 6)
    classification_res = classification_service.classify_detections(
        raw_detections=detections,
        drone_id=req.drone_id,
        frame_id=req.frame_id,
        timestamp=now_utc,
        pos_x=req.pos_x,
        pos_y=req.pos_y,
        pos_z=req.pos_z,
        image_dims=(w, h)
    )

    status_info = detection_service.get_status()

    return DetectionResult(
        drone_id=req.drone_id,
        timestamp=now_utc,
        detections=classification_res.detections,
        total_detected=classification_res.total_valid,
        annotated_image_url=None,
        processed_time_ms=round(elapsed_ms + classification_res.processing_time_ms, 2),
        model_name=status_info.get("active_model_name", "unknown"),
        backend_used=status_info.get("backend", "opencv"),
        is_diagnostic=status_info.get("is_diagnostic", False),
        error_message=status_info.get("load_error")
    )

@router.post("/classify", response_model=RoadClassificationBatchResult)
def classify_road_detections(req: RoadClassificationRequest):
    """
    Semana 6: Clasifica, normaliza y valida una lista de detecciones de visión.
    Aplica umbrales configurables por categoría, validación geométrica de BBox,
    diferenciación entre detección e incidente, y deduplicación espacio-temporal.
    """
    now_utc = req.timestamp or datetime.now(timezone.utc)
    return classification_service.classify_detections(
        raw_detections=req.raw_detections,
        drone_id=req.drone_id,
        frame_id=req.frame_id,
        timestamp=now_utc,
        pos_x=req.pos_x,
        pos_y=req.pos_y,
        pos_z=req.pos_z,
        image_id=req.image_id,
        image_dims=(req.image_width or 640, req.image_height or 480),
        custom_thresholds=req.custom_thresholds
    )

@router.get("/categories")
def get_road_categories_config():
    """
    Semana 6: Entrega el catálogo oficial de categorías viales normalizadas,
    umbrales de confianza por categoría, reglas de interpretación y limitaciones del modelo.
    """
    return {
        "target_categories": TARGET_ROAD_CATEGORIES,
        "default_thresholds": classification_service.get_thresholds(),
        "coordinate_system": "simulation_webots_cartesian_meters",
        "gps_available": False,
        "gps_notice": "Entorno Webots emite coordenadas métricas de simulación; no son coordenadas GPS reales.",
        "model_limitations": {
            "yolov8n": "Pesos preentrenados genéricos (COCO 80 clases). No contiene clases viales nativas.",
            "mapping_mode": "Mapeo prudencial de COCO a categorías viales candidatas con revisión técnica.",
            "opencv_heuristic": "Detector heurístico con segmentación de gálibo y morfología."
        }
    }

@router.get("/classes")
def get_target_classes():
    """Retrieve list of target classes monitored by the system."""
    return {
        "classes": settings.TARGET_CLASSES,
        "descriptions": {
            "poste_luz": "Postes de alumbrado o columnas de electrificación a lo largo de las vías",
            "vegetacion_invasiva": "Maleza, ramas o vegetación que invade el gálibo o superficie de vías",
            "obstruccion_via": "Objetos, escombros o materiales que obstaculizan el paso de trenes o vehículos"
        }
    }

@router.get("/status")
def get_detector_status():
    """
    Comprehensive status of active computer vision / YOLO detection backend.
    Maintains backward compatibility while accurately distinguishing:
    - Configured model vs active running model
    - Ultralytics installation and weights existence
    - Device (CPU/GPU)
    - Fallback and diagnostic states
    """
    engine_status = detection_service.get_status()
    is_yolo_active = engine_status.get("yolo_ready", False)

    return {
        # Core & backward-compatible fields
        "model_type": engine_status.get("configured_model_type", settings.DETECTION_MODEL_TYPE),
        "is_loaded": engine_status.get("is_loaded", False),
        "confidence_threshold": engine_status.get("confidence_threshold", settings.DETECTION_CONFIDENCE_THRESHOLD),
        "yolo_ready": is_yolo_active,
        "yolo_model_loaded": is_yolo_active,

        # Precision audit fields (Semana 5)
        "configured_model_type": engine_status.get("configured_model_type"),
        "ultralytics_available": engine_status.get("ultralytics_available", False),
        "weights_path": engine_status.get("weights_path"),
        "weights_exist": engine_status.get("weights_exist", False),
        "active_model": engine_status.get("active_model_name"),
        "backend": engine_status.get("backend"),
        "device": engine_status.get("device"),
        "is_available": engine_status.get("is_available", False),
        "is_fallback": engine_status.get("is_fallback", False),
        "is_diagnostic": engine_status.get("is_diagnostic", False),
        "model_mode": engine_status.get("model_mode"),
        "load_error": engine_status.get("load_error"),
        "last_inference_error": engine_status.get("last_inference_error"),
        "classes": engine_status.get("supported_classes"),
        "total_classes": engine_status.get("total_classes"),
        "skip_on_busy": engine_status.get("skip_on_busy")
    }


@router.get("/threshold", response_model=ThresholdResponse)
def get_detection_confidence_threshold():
    """
    Semana 11: Consulta el umbral de confianza dinámico actual del motor de visión (YOLO/Heurístico).
    """
    val = detection_service.get_confidence_threshold()
    return ThresholdResponse(
        confidence_threshold=val,
        min_threshold=0.15,
        max_threshold=0.50,
        default_threshold=0.25,
        updated_at=datetime.now(timezone.utc),
        message=f"Umbral de confianza activo: {val:.3f}"
    )


@router.put("/threshold", response_model=ThresholdResponse)
@router.post("/threshold", response_model=ThresholdResponse)
def update_detection_confidence_threshold(req: ThresholdUpdateRequest):
    """
    Semana 11: Modifica dinámicamente el umbral de confianza de detección entre 0.15 y 0.50
    sin reiniciar el backend ni la simulación.
    Aplica validación de intervalo y evita condiciones de carrera durante inferencias en curso.
    """
    try:
        updated_val = detection_service.set_confidence_threshold(req.threshold)
        return ThresholdResponse(
            confidence_threshold=updated_val,
            min_threshold=0.15,
            max_threshold=0.50,
            default_threshold=0.25,
            updated_at=datetime.now(timezone.utc),
            message=f"Umbral de confianza actualizado exitosamente a {updated_val:.3f}"
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


