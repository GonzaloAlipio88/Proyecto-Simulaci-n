import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import cv2
import numpy as np

from backend.app.modules.deteccion.base import VisionModel
from backend.app.modules.deteccion.image_processor import ImageProcessor
from backend.app.schemas.deteccion import DetectionItem, BoundingBox

logger = logging.getLogger("heuristic_detector")

class HeuristicDetector(VisionModel):
    """
    OpenCV-based heuristic vision detector.
    Uses color-space transformations (HSV), edge detection (Canny),
    and spatial ROI analysis to detect:
    1. Postes de luz (vertical linear high-aspect-ratio structures)
    2. Vegetación invasiva (excessive green saturation on road masks)
    3. Obstrucciones de vía (unexpected high-contrast objects on tracks)
    """

    def __init__(self):
        self.is_loaded = False
        self.load_model()

    def load_model(self) -> bool:
        self.is_loaded = True
        logger.info("Heuristic OpenCV Vision Detector loaded successfully.")
        return True

    def is_available(self) -> bool:
        return self.is_loaded

    def analyze(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5,
        frame_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> List[DetectionItem]:
        valid, err = ImageProcessor.validate_image_array(image)
        if not valid:
            logger.warning(f"HeuristicDetector received invalid image: {err}")
            return []

        h, w = image.shape[:2]
        detections: List[DetectionItem] = []

        try:
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            # 1. Detection of invasive green vegetation: HSV mask for greens
            lower_green = np.array([30, 40, 40])
            upper_green = np.array([85, 255, 255])
            green_mask = cv2.inRange(hsv, lower_green, upper_green)
            green_contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in green_contours:
                area = cv2.contourArea(cnt)
                if area > (h * w * 0.015): # Minimum threshold to qualify as invasive patch
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    conf = min(0.95, round(0.65 + (area / (h * w)), 2))
                    if conf >= confidence_threshold:
                        detections.append(DetectionItem(
                            label="vegetacion_invasiva",
                            class_name="vegetacion_invasiva",
                            confidence=conf,
                            bbox=BoundingBox(
                                x_min=float(x),
                                y_min=float(y),
                                x_max=float(x + cw),
                                y_max=float(y + ch)
                            ),
                            severity="alta" if area > (h * w * 0.05) else "media",
                            description=f"Crecimiento vegetal sobre franja de vía ({int(area)} px)",
                            frame_id=frame_id,
                            timestamp=timestamp
                        ))

            # 2. Detection of light poles / vertical high-aspect ratio features
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 60, 180)
            edge_contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for cnt in edge_contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect_ratio = ch / max(cw, 1)
                # Poles are tall vertical elements
                if aspect_ratio > 2.5 and ch > (h * 0.25):
                    conf = min(0.92, round(0.70 + (aspect_ratio / 10.0), 2))
                    if conf >= confidence_threshold:
                        detections.append(DetectionItem(
                            label="poste_luz",
                            class_name="poste_luz",
                            confidence=conf,
                            bbox=BoundingBox(
                                x_min=float(x),
                                y_min=float(y),
                                x_max=float(x + cw),
                                y_max=float(y + ch)
                            ),
                            severity="baja",
                            description=f"Poste de luz / columna detectado (relación {aspect_ratio:.1f})",
                            frame_id=frame_id,
                            timestamp=timestamp
                        ))

            # 3. Detection of track obstruction / dark solid obstacles
            center_y_start, center_y_end = int(h * 0.3), int(h * 0.8)
            center_x_start, center_x_end = int(w * 0.2), int(w * 0.8)
            road_roi_gray = gray[center_y_start:center_y_end, center_x_start:center_x_end]

            if road_roi_gray.size > 0:
                _, thresh = cv2.threshold(road_roi_gray, 40, 255, cv2.THRESH_BINARY_INV)
                obs_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in obs_contours:
                    area = cv2.contourArea(cnt)
                    if (h * w * 0.008) < area < (h * w * 0.1):
                        x, y, cw, ch = cv2.boundingRect(cnt)
                        real_x = center_x_start + x
                        real_y = center_y_start + y
                        conf = min(0.89, round(0.72 + (area / (h * w * 0.1)), 2))
                        if conf >= confidence_threshold:
                            detections.append(DetectionItem(
                                label="obstruccion_via",
                                class_name="obstruccion_via",
                                confidence=conf,
                                bbox=BoundingBox(
                                    x_min=float(real_x),
                                    y_min=float(real_y),
                                    x_max=float(real_x + cw),
                                    y_max=float(real_y + ch)
                                ),
                                severity="alta",
                                description="Objeto extraño bloqueando vía en zona de tránsito",
                                frame_id=frame_id,
                                timestamp=timestamp
                            ))

        except Exception as e:
            logger.error(f"Error during computer vision heuristic detection: {e}")

        return detections

    def annotate_image(self, image: np.ndarray, detections: List[DetectionItem]) -> np.ndarray:
        return ImageProcessor.annotate_detections(image, detections)

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "opencv_heuristic",
            "backend": "opencv",
            "device": "cpu",
            "is_loaded": self.is_loaded,
            "classes": ["poste_luz", "vegetacion_invasiva", "obstruccion_via"],
            "description": "Detector heurístico basado en filtros HSV, Canny y morfología de OpenCV"
        }


class DiagnosticDetector(VisionModel):
    """
    Explicit Diagnostic Detector.
    Used when a requested deep-learning model (such as YOLO) is not available or weights are missing.
    Strictly follows rule: DOES NOT invent detections. Returns empty results with diagnostic info.
    """

    def __init__(self, reason: str = "Modelo en modo diagnóstico explícito (pesos o biblioteca no disponibles)"):
        self.reason = reason
        self.is_loaded = True

    def load_model(self) -> bool:
        self.is_loaded = True
        return True

    def is_available(self) -> bool:
        return False

    def analyze(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5,
        frame_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> List[DetectionItem]:
        valid, err = ImageProcessor.validate_image_array(image)
        if not valid:
            logger.warning(f"DiagnosticDetector: imagen inválida ({err})")
        # Explicit diagnostic mode does not generate false detections
        return []

    def annotate_image(self, image: np.ndarray, detections: List[DetectionItem]) -> np.ndarray:
        return ImageProcessor.annotate_detections(image, detections)

    def get_model_info(self) -> Dict[str, Any]:
        return {
            "model_name": "diagnostic_mode",
            "backend": "diagnostic",
            "device": "cpu",
            "is_loaded": False,
            "is_diagnostic": True,
            "reason": self.reason,
            "classes": []
        }
