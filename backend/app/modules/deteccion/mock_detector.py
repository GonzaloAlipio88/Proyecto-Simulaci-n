import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import cv2
import numpy as np

from backend.app.modules.deteccion.base import VisionModel
from backend.app.modules.deteccion.image_processor import ImageProcessor
from backend.app.schemas.deteccion import DetectionItem, BoundingBox

logger = logging.getLogger("heuristic_detector")


def _bbox_iou(a: BoundingBox, b: BoundingBox) -> float:
    x_left = max(a.x_min, b.x_min)
    y_top = max(a.y_min, b.y_min)
    x_right = min(a.x_max, b.x_max)
    y_bottom = min(a.y_max, b.y_max)
    if x_right <= x_left or y_bottom <= y_top:
        return 0.0
    inter = (x_right - x_left) * (y_bottom - y_top)
    area_a = max(0.0, (a.x_max - a.x_min) * (a.y_max - a.y_min))
    area_b = max(0.0, (b.x_max - b.x_min) * (b.y_max - b.y_min))
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class HeuristicDetector(VisionModel):
    """
    OpenCV-based heuristic vision detector.
    Uses color-space transformations (HSV), edge detection (Canny),
    and spatial ROI analysis to detect:
    1. Postes de luz (vertical linear high-aspect-ratio structures & Webots 3D emissive luminaires)
    2. Vegetación invasiva (excessive green saturation on road masks)
    3. Obstrucciones de vía (unexpected high-contrast or cargo/rock objects on tracks)
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
                if area > (h * w * 0.015):  # Minimum threshold to qualify as invasive patch
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

            # 2. Detection of light poles:
            # (a) Vertical high-aspect-ratio structures via Canny edges
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 60, 180)
            edge_contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            pole_bboxes: List[BoundingBox] = []
            for cnt in edge_contours:
                x, y, cw, ch = cv2.boundingRect(cnt)
                aspect_ratio = ch / max(cw, 1)
                if aspect_ratio > 2.5 and ch > (h * 0.25):
                    conf = min(0.92, round(0.70 + (aspect_ratio / 10.0), 2))
                    if conf >= confidence_threshold:
                        cand_bbox = BoundingBox(
                            x_min=float(x),
                            y_min=float(y),
                            x_max=float(x + cw),
                            y_max=float(y + ch)
                        )
                        if not any(_bbox_iou(cand_bbox, prev) > 0.4 for prev in pole_bboxes):
                            pole_bboxes.append(cand_bbox)
                            detections.append(DetectionItem(
                                label="poste_luz",
                                class_name="poste_luz",
                                confidence=conf,
                                bbox=cand_bbox,
                                severity="baja",
                                description=f"Poste de luz / columna detectado (relación {aspect_ratio:.1f})",
                                frame_id=frame_id,
                                timestamp=timestamp
                            ))

            # (b) Webots 3D luminaire heads (emissive warm yellow-white Box on roadside poles in inspection_zone.wbt)
            lum_mask = cv2.inRange(hsv, np.array([22, 20, 212]), np.array([42, 185, 255]))
            lum_contours, _ = cv2.findContours(lum_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in lum_contours:
                area = cv2.contourArea(cnt)
                if area >= (h * w * 0.003):
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    cx = x + cw / 2.0
                    cy = y + ch / 2.0
                    # Roadside upper/mid corridor where light poles stand in Webots
                    if (0.12 * h <= cy <= 0.70 * h) and (cx <= 0.38 * w or cx >= 0.62 * w) and cw >= 20 and ch >= 12:
                        # Expand vertically downward to include the pole shaft below the luminaire head
                        y_max_pole = float(min(h - 2, y + max(ch * 3, int(h * 0.22))))
                        cand_bbox = BoundingBox(
                            x_min=float(x),
                            y_min=float(y),
                            x_max=float(x + cw),
                            y_max=y_max_pole
                        )
                        conf = 0.84
                        if conf >= confidence_threshold and not any(_bbox_iou(cand_bbox, prev) > 0.35 for prev in pole_bboxes):
                            pole_bboxes.append(cand_bbox)
                            detections.append(DetectionItem(
                                label="poste_luz",
                                class_name="poste_luz",
                                confidence=conf,
                                bbox=cand_bbox,
                                severity="baja",
                                description="Luminaria y poste de alumbrado público 3D detectado en margen vial (Webots)",
                                frame_id=frame_id,
                                timestamp=timestamp
                            ))

            # 3. Detection of track obstruction / dark solid obstacles or cargo boxes on road ROI
            center_y_start, center_y_end = int(h * 0.3), int(h * 0.90)
            center_x_start, center_x_end = int(w * 0.2), int(w * 0.8)
            road_roi_gray = gray[center_y_start:center_y_end, center_x_start:center_x_end]
            road_roi_hsv = hsv[center_y_start:center_y_end, center_x_start:center_x_end]

            obs_bboxes: List[BoundingBox] = []
            if road_roi_gray.size > 0:
                _, dark_thresh = cv2.threshold(road_roi_gray, 40, 255, cv2.THRESH_BINARY_INV)
                # Also detect CardboardBox / cargo obstacles (high-saturation brown/orange on central grey pavement)
                cargo_mask = cv2.inRange(road_roi_hsv, np.array([5, 145, 50]), np.array([20, 255, 200]))
                combined_obs = cv2.bitwise_or(dark_thresh, cargo_mask)
                kernel = np.ones((5, 5), np.uint8)
                combined_obs = cv2.morphologyEx(combined_obs, cv2.MORPH_CLOSE, kernel)

                obs_contours, _ = cv2.findContours(combined_obs, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in obs_contours:
                    area = cv2.contourArea(cnt)
                    if (h * w * 0.008) < area < (h * w * 0.15):
                        x, y, cw, ch = cv2.boundingRect(cnt)
                        real_x = center_x_start + x
                        real_y = center_y_start + y
                        cand_bbox = BoundingBox(
                            x_min=float(real_x),
                            y_min=float(real_y),
                            x_max=float(real_x + cw),
                            y_max=float(real_y + ch)
                        )
                        conf = min(0.89, round(0.72 + (area / (h * w * 0.1)), 2))
                        if conf >= confidence_threshold and not any(_bbox_iou(cand_bbox, prev) > 0.4 for prev in obs_bboxes):
                            obs_bboxes.append(cand_bbox)
                            detections.append(DetectionItem(
                                label="obstruccion_via",
                                class_name="obstruccion_via",
                                confidence=conf,
                                bbox=cand_bbox,
                                severity="alta",
                                description="Objeto extraño / obstáculo bloqueando vía en zona de tránsito",
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


class HybridDetector(VisionModel):
    """
    Hybrid Vision Detector (Fase 2 - Sección 8).
    Combines real Ultralytics YOLO inference with the OpenCV HeuristicDetector
    so that generic MS-COCO weights (yolov8n.pt) are complemented by OpenCV
    geometric/HSV detection for Webots 3D primitives (poste_luz, vegetacion_invasiva,
    obstruccion_via), without claiming that the generic YOLO weights are custom-trained.
    """

    def __init__(self, primary_yolo: VisionModel, secondary_heuristic: Optional[HeuristicDetector] = None):
        self.primary = primary_yolo
        self.secondary = secondary_heuristic or HeuristicDetector()
        self.is_loaded = self.primary.is_available() and self.secondary.is_available()

    def load_model(self) -> bool:
        p_ok = self.primary.load_model()
        s_ok = self.secondary.load_model()
        self.is_loaded = p_ok and s_ok
        return self.is_loaded

    def is_available(self) -> bool:
        return self.primary.is_available() or self.secondary.is_available()

    def analyze(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5,
        frame_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> List[DetectionItem]:
        yolo_dets = self.primary.analyze(
            image,
            confidence_threshold=confidence_threshold,
            frame_id=frame_id,
            timestamp=timestamp
        ) if self.primary.is_available() else []

        heur_dets = self.secondary.analyze(
            image,
            confidence_threshold=confidence_threshold,
            frame_id=frame_id,
            timestamp=timestamp
        ) if self.secondary.is_available() else []

        merged = list(yolo_dets)
        for h_det in heur_dets:
            if not any(_bbox_iou(h_det.bbox, y_det.bbox) > 0.40 for y_det in merged):
                merged.append(h_det)
        return merged

    def annotate_image(self, image: np.ndarray, detections: List[DetectionItem]) -> np.ndarray:
        return ImageProcessor.annotate_detections(image, detections)

    def get_model_info(self) -> Dict[str, Any]:
        p_info = self.primary.get_model_info() if hasattr(self.primary, "get_model_info") else {}
        return {
            **p_info,
            "model_name": "yolo_opencv_hybrid",
            "backend": "yolo_hybrid",
            "model_mode": "pretrained_generic_hybrid",
            "is_specialized": False,
            "hybrid_complement_active": True,
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
