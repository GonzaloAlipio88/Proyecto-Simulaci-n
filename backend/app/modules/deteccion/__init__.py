from backend.app.modules.deteccion.base import BaseDetector
from backend.app.modules.deteccion.mock_detector import HeuristicDetector
from backend.app.modules.deteccion.yolo_adapter import YOLODetector
from backend.app.modules.deteccion.service import detection_service, DetectionService

__all__ = ["BaseDetector", "HeuristicDetector", "YOLODetector", "detection_service", "DetectionService"]
