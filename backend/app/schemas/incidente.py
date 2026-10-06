from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime

class IncidenteBase(BaseModel):
    drone_id: str
    tipo: Literal["poste_luz", "vegetacion_invasiva", "obstruccion_via", "otro"]
    severidad: Literal["baja", "media", "alta", "critica"] = "media"
    descripcion: str
    pos_x: float
    pos_y: float
    pos_z: float
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    imagen_id: Optional[int] = None
    estado: Literal["reportado", "en_revision", "atendido", "descartado"] = "reportado"

class IncidenteCreate(IncidenteBase):
    pass

class IncidenteUpdate(BaseModel):
    severidad: Optional[Literal["baja", "media", "alta", "critica"]] = None
    descripcion: Optional[str] = None
    estado: Optional[Literal["reportado", "en_revision", "atendido", "descartado"]] = None

class IncidenteResponse(IncidenteBase):
    id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

