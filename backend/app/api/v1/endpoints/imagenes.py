from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.core.database import get_db
from backend.app.models.imagen import ImageRecord
from backend.app.schemas.imagen import ImageResponse
from backend.app.modules.imagenes.service import image_service

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
    path = image_service.get_image_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Archivo de imagen no encontrado")
    return FileResponse(path, media_type="image/jpeg")
