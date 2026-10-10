from fastapi import APIRouter, HTTPException
from datetime import datetime
from backend.app.core.config import settings
from backend.app.schemas.deteccion import DetectionRequest, DetectionResult
from backend.app.modules.deteccion.service import detection_service
from backend.app.modules.imagenes.service import image_service

router = APIRouter()

@router.post("/detect", response_model=DetectionResult)
def run_standalone_detection(req: DetectionRequest):
    """Run computer vision detection directly on an arbitrary base64 image."""
    cv_img = image_service.base64_to_cv2(req.image_base64)
    if cv_img is None:
        raise HTTPException(status_code=400, detail="Formato de imagen base64 inválido")

    detections, annotated_cv, elapsed_ms = detection_service.process_frame(
        cv_img,
        drone_id=req.drone_id,
        threshold=req.threshold or settings.DETECTION_CONFIDENCE_THRESHOLD
    )

    return DetectionResult(
        drone_id=req.drone_id,
        timestamp=datetime.utcnow(),
        detections=detections,
        total_detected=len(detections),
        annotated_image_url=None,
        processed_time_ms=elapsed_ms
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
    """Status of active computer vision / YOLO detection backend."""
    return {
        "model_type": settings.DETECTION_MODEL_TYPE,
        "is_loaded": getattr(detection_service.detector, "is_loaded", True),
        "confidence_threshold": settings.DETECTION_CONFIDENCE_THRESHOLD,
        "yolo_ready": True
    }
