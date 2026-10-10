from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.schemas.camera import CameraFrameIn, CameraStatusResponse, CameraFrameInfoResponse
from backend.app.modules.cameras.service import camera_service

router = APIRouter()

@router.post("/frame")
async def ingest_camera_frame(frame: CameraFrameIn, db: Session = Depends(get_db)):
    """Ingest camera frame from drone, validate, trigger vision pipeline, and save image."""
    result = await camera_service.ingest_frame(db, frame)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Error procesando fotograma"))
    return result

@router.get("/status", response_model=CameraStatusResponse)
def get_camera_status():
    """Retrieve operational status of cameras and active drone streams."""
    return camera_service.get_status()

@router.get("/{drone_id}/latest-frame", response_model=CameraFrameInfoResponse)
def get_latest_frame(drone_id: str, annotated: bool = Query(default=True)):
    """
    Retrieve the latest base64 JPEG snapshot for a specific drone,
    including capture timestamp, age in seconds, and freshness indicator.
    """
    info = camera_service.get_latest_frame_info(drone_id, annotated=annotated)
    if not info.get("available") or not info.get("frame_base64"):
        raise HTTPException(status_code=404, detail="No hay fotogramas disponibles para este dron")
    return info

@router.get("/{drone_id}/frame-info")
@router.get("/frame-info/{drone_id}")
def get_latest_frame_info(drone_id: str, annotated: bool = Query(default=True)):
    """Retrieve metadata of the latest frame without transferring large base64 payload."""
    info = camera_service.get_latest_frame_info(drone_id, annotated=annotated)
    if not info.get("available"):
        return {
            "available": False,
            "drone_id": drone_id,
            "annotated": annotated,
            "captured_at": None,
            "age_seconds": None,
            "is_fresh": False,
            "width": None,
            "height": None,
            "format": None
        }
    # Return metadata without heavy base64 string
    return {
        "available": info["available"],
        "drone_id": info["drone_id"],
        "annotated": info["annotated"],
        "captured_at": info["captured_at"],
        "age_seconds": info["age_seconds"],
        "is_fresh": info["is_fresh"],
        "width": info["width"],
        "height": info["height"],
        "format": info["format"]
    }


