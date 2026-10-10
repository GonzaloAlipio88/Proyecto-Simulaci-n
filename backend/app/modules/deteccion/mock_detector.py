import cv2
import numpy as np
import logging
from typing import List
from backend.app.modules.deteccion.base import BaseDetector
from backend.app.schemas.deteccion import DetectionItem, BoundingBox

logger = logging.getLogger("heuristic_detector")

class HeuristicDetector(BaseDetector):
    """
    Initial functional vision detector using OpenCV color/contour filtering
    and heuristic spatial inspection to identify:
    1. Postes de luz (vertical linear structures)
    2. Vegetación invasiva (excessive green saturation on road masks)
    3. Obstrucciones de vía (high contrast unexpected objects on tracks)
    """

    def __init__(self):
        self.is_loaded = False
        self.class_colors = {
            "poste_luz": (255, 180, 0),         # Blue/Cyan in BGR
            "vegetacion_invasiva": (60, 220, 60), # Green in BGR
            "obstruccion_via": (40, 40, 230)      # Red in BGR
        }
        self.load_model()

    def load_model(self) -> bool:
        self.is_loaded = True
        logger.info("Heuristic/Computer Vision Detector loaded successfully.")
        return True

    def detect(self, image: np.ndarray, confidence_threshold: float = 0.5) -> List[DetectionItem]:
        if image is None or image.size == 0:
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
                            confidence=conf,
                            bbox=BoundingBox(
                                x_min=float(x),
                                y_min=float(y),
                                x_max=float(x + cw),
                                y_max=float(y + ch)
                            ),
                            severity="alta" if area > (h * w * 0.05) else "media",
                            description=f"Crecimiento vegetal sobre franja de vía ({int(area)} px)"
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
                            confidence=conf,
                            bbox=BoundingBox(
                                x_min=float(x),
                                y_min=float(y),
                                x_max=float(x + cw),
                                y_max=float(y + ch)
                            ),
                            severity="baja",
                            description=f"Poste de luz / columna detectado (relación {aspect_ratio:.1f})"
                        ))

            # 3. Detection of track obstruction / dark solid obstacles
            # Dark or high-contrast central objects
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
                                confidence=conf,
                                bbox=BoundingBox(
                                    x_min=float(real_x),
                                    y_min=float(real_y),
                                    x_max=float(real_x + cw),
                                    y_max=float(real_y + ch)
                                ),
                                severity="alta",
                                description=f"Objeto extraño bloqueando vía en zona de tránsito"
                            ))

        except Exception as e:
            logger.error(f"Error during computer vision heuristic detection: {e}")

        return detections

    def annotate_image(self, image: np.ndarray, detections: List[DetectionItem]) -> np.ndarray:
        if image is None:
            return None
        annotated = image.copy()
        
        for det in detections:
            color = self.class_colors.get(det.label, (0, 255, 255))
            x1, y1 = int(det.bbox.x_min), int(det.bbox.y_min)
            x2, y2 = int(det.bbox.x_max), int(det.bbox.y_max)
            
            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            
            # Draw label banner
            text = f"{det.label}: {int(det.confidence * 100)}%"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x1, max(0, y1 - th - 8)), (x1 + tw + 6, y1), color, -1)
            cv2.putText(annotated, text, (x1 + 3, max(12, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        return annotated
