from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Any
from datetime import datetime

class BoundingBox(BaseModel):
    x_min: float = Field(..., description="Normalized or pixel min X")
    y_min: float = Field(..., description="Normalized or pixel min Y")
    x_max: float = Field(..., description="Normalized or pixel max X")
    y_max: float = Field(..., description="Normalized or pixel max Y")

class DetectionItem(BaseModel):
    label: str = Field(default="", description="Target class: 'poste_luz', 'vegetacion_invasiva', 'obstruccion_via'")
    class_name: Optional[str] = Field(default=None, description="Equivalent to label for VisionModel standard interface")
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: BoundingBox
    severity: str = "media" # baja, media, alta, critica
    description: Optional[str] = None
    frame_id: Optional[str] = None
    timestamp: Optional[datetime] = None

    @model_validator(mode="before")
    @classmethod
    def sync_label_and_class_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync label and class_name
            lbl = data.get("label")
            cname = data.get("class_name")
            if not lbl and cname:
                data["label"] = cname
            elif not cname and lbl:
                data["class_name"] = lbl
            elif not lbl and not cname:
                data["label"] = "desconocido"
                data["class_name"] = "desconocido"
        return data

class DetectionResult(BaseModel):
    drone_id: str
    timestamp: datetime
    detections: List[DetectionItem] = []
    total_detected: int = 0
    annotated_image_url: Optional[str] = None
    processed_time_ms: float = 0.0
    model_name: Optional[str] = "heuristic"
    backend_used: Optional[str] = "opencv"
    is_diagnostic: bool = False
    error_message: Optional[str] = None

class DetectionRequest(BaseModel):
    image_base64: str
    drone_id: str
    pos_x: Optional[float] = 0.0
    pos_y: Optional[float] = 0.0
    pos_z: Optional[float] = 0.0
    threshold: Optional[float] = 0.5
    frame_id: Optional[str] = None

