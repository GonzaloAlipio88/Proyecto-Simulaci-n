import logging
import numpy as np
from typing import List
from backend.app.modules.deteccion.base import BaseDetector
from backend.app.schemas.deteccion import DetectionItem, BoundingBox

logger = logging.getLogger("yolo_adapter")

class YOLODetector(BaseDetector):
    """
    Adapter for Ultralytics YOLO (v8 / v11) model.
    Designed so that when weights or the ultralytics package are installed,
    no architecture changes are required.
    """

    def __init__(self, weights_path: str = "storage/weights/best.pt"):
        self.weights_path = weights_path
        self.model = None
        self.is_loaded = False
        self.class_mapping = {
            0: "poste_luz",
            1: "vegetacion_invasiva",
            2: "obstruccion_via"
        }

    def load_model(self) -> bool:
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.weights_path)
            self.is_loaded = True
            logger.info(f"YOLO Model loaded successfully from {self.weights_path}")
            return True
        except ImportError:
            logger.warning("ultralytics library not installed yet. Ready for future integration.")
            return False
        except Exception as e:
            logger.warning(f"Could not load YOLO weights from {self.weights_path}: {e}")
            return False

    def detect(self, image: np.ndarray, confidence_threshold: float = 0.5) -> List[DetectionItem]:
        if not self.is_loaded or self.model is None:
            logger.debug("YOLO model not loaded; returning empty detection list.")
            return []

        detections: List[DetectionItem] = []
        try:
            results = self.model.predict(source=image, conf=confidence_threshold, verbose=False)
            for r in results:
                for box in r.boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()
                    label = self.class_mapping.get(cls_id, f"clase_{cls_id}")
                    
                    detections.append(DetectionItem(
                        label=label,
                        confidence=round(conf, 2),
                        bbox=BoundingBox(
                            x_min=xyxy[0],
                            y_min=xyxy[1],
                            x_max=xyxy[2],
                            y_max=xyxy[3]
                        ),
                        severity="alta" if label in ["obstruccion_via", "vegetacion_invasiva"] else "media",
                        description=f"Detección YOLO de {label} (conf: {conf:.2f})"
                    ))
        except Exception as e:
            logger.error(f"Error executing YOLO inference: {e}")

        return detections

    def annotate_image(self, image: np.ndarray, detections: List[DetectionItem]) -> np.ndarray:
        # If YOLO is loaded and has native plot
        if self.model is not None and hasattr(self.model, "plot"):
            # Can use native or fallback to heuristic drawer
            pass
        from backend.app.modules.deteccion.mock_detector import HeuristicDetector
        return HeuristicDetector().annotate_image(image, detections)
