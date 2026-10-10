from abc import ABC, abstractmethod
from typing import List, Tuple
import numpy as np
from backend.app.schemas.deteccion import DetectionItem

class BaseDetector(ABC):
    """Abstract interface for object detection models in the surveillance pipeline."""

    @abstractmethod
    def load_model(self) -> bool:
        """Loads weights and prepares inference engine."""
        pass

    @abstractmethod
    def detect(self, image: np.ndarray, confidence_threshold: float = 0.5) -> List[DetectionItem]:
        """Performs object detection on an RGB/BGR numpy array and returns structured detections."""
        pass

    @abstractmethod
    def annotate_image(self, image: np.ndarray, detections: List[DetectionItem]) -> np.ndarray:
        """Draws bounding boxes and labels onto the image."""
        pass
