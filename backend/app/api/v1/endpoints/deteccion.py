from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from backend.app.core.config import settings
from backend.app.schemas.deteccion import DetectionRequest, DetectionResult
from backend.app.modules.deteccion.service import detection_service
from backend.app.modules.deteccion.image_processor import ImageProcessor

router = APIRouter()

@router.post("/detect", response_model=DetectionResult)
def run_standalone_detection(req: DetectionRequest):
    """
    Run computer vision detection on an arbitrary base64 image.
    Validates image, runs inference through active VisionModel (YOLO / Heuristic / Diagnostic),
    and returns structured detections with bounding boxes and latency.
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

    status_info = detection_service.get_status()

    return DetectionResult(
        drone_id=req.drone_id,
        timestamp=now_utc,
        detections=detections,
        total_detected=len(detections),
        annotated_image_url=None,
        processed_time_ms=round(elapsed_ms, 2),
        model_name=status_info.get("active_model_name", "unknown"),
        backend_used=status_info.get("backend", "opencv"),
        is_diagnostic=status_info.get("is_diagnostic", False),
        error_message=status_info.get("load_error")
    )

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

