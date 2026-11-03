from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Literal, Dict
from datetime import datetime
import math

class IncidenteBase(BaseModel):
    drone_id: str = Field(..., min_length=1, max_length=50, description="Identificador del dron emisor")
    tipo: Literal["poste_luz", "vegetacion_invasiva", "obstruccion_via", "otro"] = Field(
        ..., description="Tipo de anomalía detectada en vía"
    )
    severidad: Literal["baja", "media", "alta", "critica"] = Field(
        default="media", description="Nivel de severidad técnica"
    )
    descripcion: str = Field(..., min_length=3, max_length=500, description="Descripción técnica del incidente")
    pos_x: Optional[float] = Field(default=None, description="Coordenada X métrica en simulación Webots")
    pos_y: Optional[float] = Field(default=None, description="Coordenada Y métrica en simulación Webots")
    pos_z: Optional[float] = Field(default=None, description="Coordenada Z métrica en simulación Webots")
    coordenadas_tipo: Optional[str] = Field(default="simulacion_webots", description="Marco espacial de referencia")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Nivel de confianza de la detección (0.0 a 1.0)")
    imagen_id: Optional[int] = Field(default=None, ge=1, description="ID del registro de imagen asociado")
    estado: Literal["reportado", "en_revision", "atendido", "descartado"] = Field(
        default="reportado", description="Estado operativo del incidente"
    )

    @field_validator("drone_id", "descripcion")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("El valor no puede estar vacío ni contener únicamente espacios en blanco")
        return v.strip()

    @field_validator("pos_x", "pos_y", "pos_z")
    @classmethod
    def validate_finite_coords(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and (math.isnan(v) or math.isinf(v)):
            raise ValueError("Las coordenadas espaciales deben ser números finitos válidos (no NaN ni Inf)")
        return v


class IncidenteCreate(IncidenteBase):
    timestamp: Optional[datetime] = Field(
        default=None, description="Fecha y hora del incidente (si se omite, se asigna UTC actual)"
    )


class IncidenteUpdate(BaseModel):
    severidad: Optional[Literal["baja", "media", "alta", "critica"]] = None
    descripcion: Optional[str] = Field(default=None, min_length=3, max_length=500)
    estado: Optional[Literal["reportado", "en_revision", "atendido", "descartado"]] = None

    @field_validator("descripcion")
    @classmethod
    def validate_update_desc(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not v.strip():
                raise ValueError("La descripción no puede estar vacía")
            return v.strip()
        return v


class IncidenteResponse(IncidenteBase):
    id: int
    timestamp: datetime
    imagen_url: Optional[str] = Field(default=None, description="URL pública de consulta para la imagen vinculada")
    model_config = ConfigDict(from_attributes=True)


class IncidenteStatsResponse(BaseModel):
    total_incidentes: int
    por_tipo: Dict[str, int]
    por_severidad: Dict[str, int]
    por_estado: Dict[str, int]
    con_imagen: int
    sin_imagen: int
    confianza_promedio: float
    ultimo_incidente_timestamp: Optional[datetime] = None


class IncidenteDeleteResponse(BaseModel):
    success: bool = True
    message: str
    id: int
