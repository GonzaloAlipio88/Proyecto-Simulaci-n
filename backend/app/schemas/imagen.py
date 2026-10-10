from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ImageResponse(BaseModel):
    id: int
    drone_id: str
    filename: str
    url: str
    captured_at: datetime
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_z: Optional[float] = None
    has_detections: bool = False
    detection_count: int = 0
    annotated_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ImageUploadResponse(BaseModel):
    image_id: int
    filename: str
    saved: bool
    detections_found: int

