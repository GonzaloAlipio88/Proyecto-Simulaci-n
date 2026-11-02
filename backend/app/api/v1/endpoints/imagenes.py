
import re
import uuid
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.models.imagen import ImageRecord
from backend.app.schemas.imagen import (
    ImageResponse,
    ImageAnalysisResponse,
    ImageDimensions,
    ModelInfo
)
from backend.app.modules.imagenes.service import image_service
from backend.app.modules.deteccion.service import detection_service
from backend.app.modules.deteccion.image_processor import ImageProcessor
from backend.app.modules.clasificacion.service import classification_service

logger = logging.getLogger("imagenes_endpoint")

router = APIRouter()

@router.get("", response_model=List[ImageResponse])
def list_images(
    drone_id: Optional[str] = None,
    only_with_detections: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List stored surveillance images with metadata."""
    query = db.query(ImageRecord)
    if drone_id:
        query = query.filter(ImageRecord.drone_id == drone_id)
    if only_with_detections:
        query = query.filter(ImageRecord.has_detections == True)

    records = query.order_by(ImageRecord.captured_at.desc()).limit(limit).all()

    response = []
    for r in records:
        response.append(ImageResponse(
            id=r.id,
            drone_id=r.drone_id,
            filename=r.filename,
            url=f"/api/v1/imagenes/file/{r.filename}",
            captured_at=r.captured_at,
            pos_x=r.pos_x,
            pos_y=r.pos_y,
            pos_z=r.pos_z,
            has_detections=r.has_detections,
            detection_count=r.detection_count,
            annotated_url=f"/api/v1/imagenes/file/{r.annotated_filename}" if r.annotated_filename else None
        ))
    return response

@router.get("/{image_id}", response_model=ImageResponse)
def get_image_detail(image_id: int, db: Session = Depends(get_db)):
    """Retrieve metadata of a specific image."""
    record = db.query(ImageRecord).filter(ImageRecord.id == image_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return ImageResponse(
        id=record.id,
        drone_id=record.drone_id,
        filename=record.filename,
        url=f"/api/v1/imagenes/file/{record.filename}",
        captured_at=record.captured_at,
        pos_x=record.pos_x,
        pos_y=record.pos_y,
        pos_z=record.pos_z,
        has_detections=record.has_detections,
        detection_count=record.detection_count,
        annotated_url=f"/api/v1/imagenes/file/{record.annotated_filename}" if record.annotated_filename else None
    )

@router.get("/file/{filename}")
def serve_image_file(filename: str):
    """Serve physical image file (original or annotated)."""
    # Sanitize path to prevent directory traversal
    clean_filename = Path(filename).name
    path = image_service.get_image_path(clean_filename)
    if not path:
        raise HTTPException(status_code=404, detail="Archivo de imagen no encontrado")

    media_type = "image/png" if clean_filename.lower().endswith(".png") else "image/jpeg"
    return FileResponse(path, media_type=media_type)

@router.post("/analyze", response_model=ImageAnalysisResponse)
async def analyze_external_image(
    file: UploadFile = File(..., description="Fotografía JPG, JPEG o PNG subida desde el computador"),
    confidence_threshold: Optional[float] = Query(default=None, ge=0.0, le=1.0, description="Umbral de confianza opcional (0.0 a 1.0)"),
    save_to_storage: bool = Query(default=True, description="Guardar imagen y anotación en almacenamiento local con retención acotada"),
    db: Session = Depends(get_db)
):
    """
    Semana 7: Carga y análisis seguro de imágenes externas JPG/PNG.

    Flujo:
    1. Valida tamaño máximo (10 MB por defecto), extensión y tipo MIME.
    2. Valida decodificación real con OpenCV (rechaza archivos vacíos, ejecutables o corruptos).
    3. Reutiliza el motor de visión de la Semana 5 sin bloquear el bucle de eventos.
    4. Aplica la capa de clasificación vial de la Semana 6 (normalización, BBox, severidad).
    5. Garantiza ausencia honesta de coordenadas ficticias (pos=None, GPS=None).
    6. Almacena en ImageService si corresponde con retención acotada y nombres sanitizados.
    7. Retorna respuesta estructurada con detecciones, estado, tiempos y advertencias de modelo.
    """
    start_total_t = time.perf_counter()
    now_utc = datetime.now(timezone.utc)
    analysis_id = str(uuid.uuid4())

    # 1. Sanitizar nombre de archivo y verificar extensión
    raw_name = file.filename or "image.jpg"
    safe_name = Path(raw_name).name
    # Eliminar caracteres peligrosos del nombre original
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', safe_name)
    if not safe_name or safe_name.startswith('.'):
        safe_name = f"upload_{analysis_id[:8]}.jpg"

    ext = Path(safe_name).suffix.lower()
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensión '{ext}' no admitida. Se admiten únicamente archivos JPG, JPEG y PNG."
        )

    # Validar MIME declarado si viene presente
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in settings.ALLOWED_IMAGE_MIMES and content_type != "application/octet-stream":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de contenido '{file.content_type}' no permitido. Se requiere imagen JPG o PNG."
        )

    # 2. Lectura segura por bloques con límite estricto de tamaño (10 MB)
    max_bytes = settings.MAX_IMAGE_UPLOAD_SIZE_BYTES
    content = bytearray()
    chunk_size = 65536

    try:
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > max_bytes:
                raise HTTPException(
                    status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                    detail=f"El archivo excede el tamaño máximo permitido de {max_bytes // (1024 * 1024)} MB."
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error durante la lectura del archivo subido: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error al leer los datos de la imagen cargada."
        )

    file_size_bytes = len(content)
    if file_size_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo de imagen está vacío (0 bytes)."
        )

    # 3. Decodificación real del contenido con OpenCV (validación de integridad de imagen)
    def decode_image_bytes(raw_bytes: bytes) -> Optional[np.ndarray]:
        nparr = np.frombuffer(raw_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    cv_img = await asyncio.to_thread(decode_image_bytes, bytes(content))
    if cv_img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El contenido del archivo no corresponde a una imagen válida decodificable o está corrupto."
        )

    is_valid, validation_err = ImageProcessor.validate_image_array(cv_img)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La imagen no cumple con las dimensiones o formato requerido: {validation_err}"
        )

    h, w = cv_img.shape[:2]
    channels = cv_img.shape[2] if cv_img.ndim == 3 else 1
    detected_format = "PNG" if ext == ".png" else "JPEG"

    # 4. Inferencia con el Motor de Visión existente (Semana 5)
    # skip_if_busy=False garantiza que una imagen externa espere su turno y no sea descartada
    effective_threshold = confidence_threshold or settings.DETECTION_CONFIDENCE_THRESHOLD
    try:
        raw_detections, annotated_cv, elapsed_inference_ms = await asyncio.to_thread(
            detection_service.process_frame,
            image=cv_img,
            drone_id="external_upload",
            threshold=effective_threshold,
            frame_id=f"ext_{analysis_id[:8]}",
            timestamp=now_utc,
            skip_if_busy=False
        )
    except Exception as e:
        logger.error(f"Fallo durante la inferencia de visión: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno durante el procesamiento del motor de visión artificial."
        )

    # 5. Capa de Clasificación Vial (Semana 6)
    try:
        classification_res = await asyncio.to_thread(
            classification_service.classify_detections,
            raw_detections=raw_detections,
            drone_id="external_upload",
            frame_id=f"ext_{analysis_id[:8]}",
            timestamp=now_utc,
            pos_x=None,
            pos_y=None,
            pos_z=None,
            image_id=None,
            image_dims=(w, h),
            custom_thresholds=None
        )
    except Exception as e:
        logger.error(f"Fallo durante la clasificación vial: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno durante la clasificación vial de detecciones."
        )

    # 6. Almacenamiento seguro opcional (respetando retención existente)
    image_record_id: Optional[int] = None
    stored_filename: Optional[str] = None
    original_url: Optional[str] = None
    annotated_url: Optional[str] = None

    if save_to_storage:
        try:
            record = image_service.save_image(
                db=db,
                image=cv_img,
                drone_id="external_upload",
                pos_x=None,
                pos_y=None,
                pos_z=None,
                has_detections=(classification_res.total_valid > 0),
                detection_count=classification_res.total_valid,
                annotated_image=annotated_cv
            )
            image_record_id = record.id
            stored_filename = record.filename
            original_url = f"/api/v1/imagenes/file/{record.filename}"
            if record.annotated_filename:
                annotated_url = f"/api/v1/imagenes/file/{record.annotated_filename}"
        except Exception as e:
            logger.warning(f"No se pudo guardar la imagen en disco SQLite: {e}")

    # Generar Base64 para visualización instantánea en frontend
    annotated_base64 = None
    target_render_img = annotated_cv if annotated_cv is not None else cv_img
    if target_render_img is not None:
        annotated_base64 = ImageProcessor.bgr_to_base64(target_render_img, quality=85)

    # 7. Información honesta del modelo y advertencias técnicas
    status_info = detection_service.get_status()
    warnings: List[str] = []

    if not status_info.get("yolo_ready", False):
        if status_info.get("is_fallback", False):
            warnings.append(
                "YOLO no disponible en el servidor (pesos ausentes o ultralytics no cargado). "
                "Inferencia ejecutada con detector heurístico OpenCV (Semana 5)."
            )
        elif status_info.get("is_diagnostic", False):
            warnings.append(
                "Modo diagnóstico activo. Modelo YOLO no configurado; no se generan detecciones artificiales."
            )
        else:
            warnings.append("Motor de visión operando en modo alternativo.")
    elif status_info.get("model_mode") == "pretrained_generic":
        warnings.append(
            "Modelo YOLOv8 preentrenado estándar (COCO 80 clases). "
            "Detecciones asociadas a categorías viales según reglas de la Semana 6."
        )

    if status_info.get("load_error"):
        warnings.append(f"Aviso del modelo: {status_info.get('load_error')}")

    # 8. Estado del análisis
    processing_status = "success" if classification_res.total_valid > 0 else "no_detections"
    total_elapsed_ms = (time.perf_counter() - start_total_t) * 1000.0

    return ImageAnalysisResponse(
        analysis_id=analysis_id,
        original_filename=safe_name,
        stored_filename=stored_filename,
        dimensions=ImageDimensions(width=w, height=h, channels=channels),
        format=detected_format,
        size_bytes=file_size_bytes,
        timestamp=now_utc,
        status=processing_status,
        detections=classification_res.detections,
        total_detected=classification_res.total_input,
        total_valid=classification_res.total_valid,
        total_rejected=classification_res.total_rejected,
        has_location=False,
        simulation_coords=None,
        gps_coords=None,
        location_notice="Ubicación geográfica no disponible: Fotografía externa sin coordenadas de simulación ni GPS.",
        inference_time_ms=round(elapsed_inference_ms, 2),
        classification_time_ms=round(classification_res.processing_time_ms, 2),
        processing_time_ms=round(total_elapsed_ms, 2),
        model_info=ModelInfo(
            name=status_info.get("active_model_name", "unknown"),
            backend=status_info.get("backend", "opencv"),
            is_available=status_info.get("is_available", True),
            is_fallback=status_info.get("is_fallback", False),
            is_diagnostic=status_info.get("is_diagnostic", False),
            model_mode=status_info.get("model_mode", "standard"),
            device=status_info.get("device", "cpu"),
            warnings=warnings
        ),
        image_id=image_record_id,
        original_image_url=original_url,
        annotated_image_url=annotated_url,
        annotated_image_base64=annotated_base64
    )
