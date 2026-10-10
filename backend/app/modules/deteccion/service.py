import logging
import time
from typing import List, Tuple
import numpy as np
from backend.app.core.config import settings
from backend.app.modules.deteccion.base import BaseDetector
from backend.app.modules.deteccion.mock_detector import HeuristicDetector
from backend.app.modules.deteccion.yolo_adapter import YOLODetector
from backend.app.schemas.deteccion import DetectionItem, DetectionResult

logger = logging.getLogger("detection_service")

class DetectionService:
    def __init__(self):
        self.detector: BaseDetector = self._initialize_detector()

    def _initialize_detector(self) -> BaseDetector:
        if settings.DETECTION_MODEL_TYPE == "yolo":
            yolo = YOLODetector(settings.YOLO_WEIGHTS_PATH)
            if yolo.load_model():
                return yolo
            logger.warning("YOLO could not be initialized, falling back to heuristic detector.")
        return HeuristicDetector()

    def process_frame(
        self,
        image: np.ndarray,
        drone_id: str,
        threshold: float = None
    ) -> Tuple[List[DetectionItem], np.ndarray, float]:
        if threshold is None:
            threshold = settings.DETECTION_CONFIDENCE_THRESHOLD

        start_time = time.time()
        detections = self.detector.detect(image, confidence_threshold=threshold)
        annotated_image = self.detector.annotate_image(image, detections)
        elapsed_ms = (time.time() - start_time) * 1000.0

        return detections, annotated_image, elapsed_ms

detection_service = DetectionService()
