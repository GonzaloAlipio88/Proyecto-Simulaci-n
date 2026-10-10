from backend.app.schemas.dron import DroneCreate, DroneUpdate, DroneResponse, DroneCommand
from backend.app.schemas.telemetria import TelemetryIn, TelemetryResponse
from backend.app.schemas.camera import CameraFrameIn, CameraStatusResponse
from backend.app.schemas.deteccion import BoundingBox, DetectionItem, DetectionResult, DetectionRequest
from backend.app.schemas.imagen import ImageResponse, ImageUploadResponse
from backend.app.schemas.incidente import IncidenteCreate, IncidenteUpdate, IncidenteResponse

__all__ = [
    "DroneCreate", "DroneUpdate", "DroneResponse", "DroneCommand",
    "TelemetryIn", "TelemetryResponse",
    "CameraFrameIn", "CameraStatusResponse",
    "BoundingBox", "DetectionItem", "DetectionResult", "DetectionRequest",
    "ImageResponse", "ImageUploadResponse",
    "IncidenteCreate", "IncidenteUpdate", "IncidenteResponse"
]
