from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from backend.app.schemas.deteccion import RoadDetectionItem

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

class ModelInfo(BaseModel):
    name: str = "unknown"
    backend: str = "opencv"
    is_available: bool = True
    is_fallback: bool = False
    is_diagnostic: bool = False
    model_mode: Optional[str] = "standard"
    device: str = "cpu"
    warnings: List[str] = []

class ImageDimensions(BaseModel):
    width: int
    height: int
    channels: int = 3

class ImageAnalysisResponse(BaseModel):
    analysis_id: str = Field(..., description="Identificador único UUID del análisis")
    original_filename: str = Field(..., description="Nombre original saneado del archivo")
    stored_filename: Optional[str] = Field(default=None, description="Nombre interno asignado si se guardó en disco")
    dimensions: ImageDimensions = Field(..., description="Dimensiones de la imagen en píxeles")
    format: str = Field(..., description="Formato o extensión de la imagen (JPEG, PNG)")
    size_bytes: int = Field(..., description="Tamaño del archivo en bytes")
    timestamp: datetime = Field(..., description="Fecha y hora UTC del análisis")
    status: str = Field(..., description="Estado del análisis: 'success', 'no_detections', 'error'")

    # Detecciones normalizadas (Semana 6)
    detections: List[RoadDetectionItem] = Field(default=[], description="Lista de detecciones validadas y clasificadas")
    total_detected: int = Field(default=0, description="Total de anomalías detectadas")
    total_valid: int = Field(default=0, description="Total de detecciones válidas que superaron umbrales")
    total_rejected: int = Field(default=0, description="Detecciones rechazadas por umbral o BBox inválida")

    # Coordenadas y ubicación
    has_location: bool = Field(default=False, description="False para fotografías externas sin telemetría de dron")
    simulation_coords: Optional[Dict[str, float]] = Field(default=None, description="None en imágenes externas")
    gps_coords: Optional[Dict[str, float]] = Field(default=None, description="None en simulación e imágenes externas")
    location_notice: str = Field(default="Ubicación geográfica no disponible para imágenes externas", description="Aclaración honesta sobre coordenadas")

    # Tiempos de procesamiento
    inference_time_ms: float = Field(default=0.0, description="Tiempo de inferencia del motor de visión (ms)")
    classification_time_ms: float = Field(default=0.0, description="Tiempo de normalización y clasificación (ms)")
    processing_time_ms: float = Field(default=0.0, description="Tiempo total de análisis (ms)")

    # Información del modelo y advertencias
    model_info: ModelInfo = Field(..., description="Detalles del modelo y limitaciones encontradas")

    # Recursos visuales
    image_id: Optional[int] = Field(default=None, description="ID en SQLite si la imagen fue almacenada")
    original_image_url: Optional[str] = Field(default=None, description="URL para servir la imagen original")
    annotated_image_url: Optional[str] = Field(default=None, description="URL para servir la imagen con cajas delimitadoras")
    annotated_image_base64: Optional[str] = Field(default=None, description="Representación Base64 JPEG de la imagen anotada para renderizado instantáneo")

