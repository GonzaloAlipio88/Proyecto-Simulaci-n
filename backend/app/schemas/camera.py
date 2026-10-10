from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CameraFrameIn(BaseModel):
    drone_id: str
    image_base64: str
    timestamp: Optional[datetime] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_z: Optional[float] = None
    run_detection: bool = True

class CameraStatusResponse(BaseModel):
    is_active: bool
    last_frame_timestamp: Optional[datetime] = None
    resolution: str = "640x480"
    fps: float = 0.0
    connected_drones: list[str] = []
