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

class RoadDetectionItem(DetectionItem):
    """
    Representación estructurada y normalizada de cada detección vial para la Semana 6.
    Integra categoría normalizada, caja validada, metadatos espaciales en coordenadas
    de simulación Webots (distinguidas de GPS), deduplicación y estado de revisión.
    """
    id: str = Field(default="", description="Identificador único UUID de la detección")
    normalized_category: str = Field(default="otro", description="Categoría normalizada: 'poste_luz', 'vegetacion_invasiva', 'obstruccion_via', 'otro'")
    raw_label: str = Field(default="", description="Etiqueta en bruto devuelta por el modelo de visión")
    review_status: str = Field(default="reportado", description="Estado de revisión: 'reportado', 'pendiente_revision', 'confirmado', 'descartado'")
    drone_id: Optional[str] = Field(default=None, description="Identificador único del dron transmisor")
    
    # Coordenadas y ubicación
    simulation_coords: Optional[dict] = Field(default=None, description="Coordenadas métricas cartesianas locales de simulación Webots {pos_x, pos_y, pos_z}")
    coordinate_system: str = Field(default="simulation_webots_cartesian_meters", description="Sistema de referencia espacial (local Webots, no GPS)")
    gps_coords: Optional[dict] = Field(default=None, description="Coordenadas GPS reales (None en entorno de simulación Webots)")
    
    # Referencias multimedia e incidentes
    image_id: Optional[int] = Field(default=None, description="Identificador en base de datos SQLite de la imagen asociada")
    image_url: Optional[str] = Field(default=None, description="Ruta relativa o URL del fotograma")
    is_incident_candidate: bool = Field(default=False, description="Indica si cumple criterios para registrarse como incidente de vía")
    incident_id: Optional[int] = Field(default=None, description="ID del incidente creado en SQLite si aplica")
    
    # Validación y deduplicación
    validation_passed: bool = Field(default=True, description="True si la BBox y confianza superan las reglas de validación")
    rejection_reason: Optional[str] = Field(default=None, description="Razón del rechazo si validation_passed es False")
    is_duplicate: bool = Field(default=False, description="True si coincide con una detección previa dentro de la ventana de deduplicación")
    repetition_count: int = Field(default=1, description="Número de veces consecutivas detectado")
    justification: Optional[str] = Field(default=None, description="Criterio explicable de severidad y clasificación")

class DetectionRequest(BaseModel):
    image_base64: str
    drone_id: str
    pos_x: Optional[float] = 0.0
    pos_y: Optional[float] = 0.0
    pos_z: Optional[float] = 0.0
    threshold: Optional[float] = 0.5
    frame_id: Optional[str] = None

class RoadClassificationRequest(BaseModel):
    drone_id: str
    frame_id: Optional[str] = None
    timestamp: Optional[datetime] = None
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None
    pos_z: Optional[float] = None
    image_id: Optional[int] = None
    image_width: Optional[int] = 640
    image_height: Optional[int] = 480
    raw_detections: List[DetectionItem] = []
    custom_thresholds: Optional[dict] = None

class RoadClassificationBatchResult(BaseModel):
    drone_id: str
    timestamp: datetime
    frame_id: Optional[str] = None
    total_input: int = 0
    total_valid: int = 0
    total_rejected: int = 0
    total_incidents_qualified: int = 0
    detections: List[RoadDetectionItem] = []
    active_thresholds: dict = {}
    processing_time_ms: float = 0.0


