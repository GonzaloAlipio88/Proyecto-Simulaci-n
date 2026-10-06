from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class BoundingBox(BaseModel):
    x_min: float = Field(..., description="Normalized or pixel min X")
    y_min: float = Field(..., description="Normalized or pixel min Y")
    x_max: float = Field(..., description="Normalized or pixel max X")
    y_max: float = Field(..., description="Normalized or pixel max Y")

class DetectionItem(BaseModel):
    label: str = Field(..., description="Target class: 'poste_luz', 'vegetacion_invasiva', 'obstruccion_via'")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: BoundingBox
    severity: str = "media" # baja, media, alta, critica
    description: Optional[str] = None

class DetectionResult(BaseModel):
    drone_id: str
    timestamp: datetime
    detections: List[DetectionItem] = []
    total_detected: int = 0
    annotated_image_url: Optional[str] = None
    processed_time_ms: float = 0.0

class DetectionRequest(BaseModel):
    image_base64: str
    drone_id: str
    pos_x: Optional[float] = 0.0
    pos_y: Optional[float] = 0.0
    pos_z: Optional[float] = 0.0
    threshold: Optional[float] = 0.5
