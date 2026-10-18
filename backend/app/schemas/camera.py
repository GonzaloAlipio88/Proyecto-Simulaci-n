from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CameraFrameIn(BaseModel):
    drone_id: str
    image_base64: str
    timestamp: Optional[datetime] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_z: Optional[float] = None
    run_detection: bool = True

class CameraFrameInfoResponse(BaseModel):
    available: bool
    drone_id: str
    annotated: bool
    frame_base64: Optional[str] = None
    captured_at: Optional[datetime] = None
    age_seconds: Optional[float] = None
    is_fresh: bool = False
    width: Optional[int] = None
    height: Optional[int] = None
    format: str = "image/jpeg"

class CameraStatusResponse(BaseModel):
    is_active: bool
    last_frame_timestamp: Optional[datetime] = None
    resolution: str = "640x480"
    fps: float = 0.0
    connected_drones: List[str] = []

