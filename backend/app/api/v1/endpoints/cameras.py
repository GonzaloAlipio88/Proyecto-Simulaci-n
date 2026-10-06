from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.camera import CameraFrameIn, CameraStatusResponse
from backend.app.modules.cameras.service import camera_service

router = APIRouter()

@router.post("/frame")
async def ingest_camera_frame(frame: CameraFrameIn, db: Session = Depends(get_db)):
    """Ingest camera frame from drone, trigger vision pipeline, and save image."""
    result = await camera_service.ingest_frame(db, frame)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Error procesando fotograma"))
    return result

@router.get("/status", response_model=CameraStatusResponse)
def get_camera_status():
    """Retrieve operational status of cameras and active drone streams."""
    return camera_service.get_status()

@router.get("/{drone_id}/latest-frame")
def get_latest_frame(drone_id: str, annotated: bool = Query(default=True)):
    """Retrieve the latest base64 JPEG snapshot for a specific drone."""
    b64 = camera_service.get_latest_frame(drone_id, annotated=annotated)
    if not b64:
        raise HTTPException(status_code=404, detail="No hay fotogramas disponibles para este dron")
    return {
        "drone_id": drone_id,
        "annotated": annotated,
        "frame_base64": b64
    }
