from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
import numpy as np
from backend.app.schemas.deteccion import DetectionItem

class VisionModel(ABC):
    """
    Standard interface for computer vision and object detection models.
    Supports modular model swapping (OpenCV Heuristic, YOLOv8/v11, Diagnostic Mock).
    """

    @abstractmethod
    def load_model(self) -> bool:
        """Loads weights, initializes inference engine, or prepares pipeline."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the model engine and weights are ready for inference."""
        pass

    @abstractmethod
    def analyze(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5,
        frame_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> List[DetectionItem]:
        """
        Executes inference on a validated BGR/RGB numpy array and returns structured detections.
        Each detection contains class_name/label, confidence, bbox, severity, frame_id and timestamp.
        """
        pass

    def detect(self, image: np.ndarray, confidence_threshold: float = 0.5) -> List[DetectionItem]:
        """Backward-compatible alias for analyze."""
        return self.analyze(image, confidence_threshold=confidence_threshold)

    @abstractmethod
    def annotate_image(self, image: np.ndarray, detections: List[DetectionItem]) -> np.ndarray:
        """Draws bounding boxes and labels onto the image."""
        pass

    @abstractmethod
    def get_model_info(self) -> Dict[str, Any]:
        """Returns metadata about the active model, device (CPU/GPU), and status."""
        pass


# Backward-compatible alias
BaseDetector = VisionModel
