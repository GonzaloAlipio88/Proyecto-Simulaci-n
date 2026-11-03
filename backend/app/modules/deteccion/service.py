import time
import logging
import threading
import importlib.util
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timezone
import numpy as np

from backend.app.core.config import settings
from backend.app.modules.deteccion.base import VisionModel
from backend.app.modules.deteccion.image_processor import ImageProcessor
from backend.app.modules.deteccion.mock_detector import HeuristicDetector, HybridDetector, DiagnosticDetector
from backend.app.modules.deteccion.yolo_adapter import YOLODetector
from backend.app.schemas.deteccion import DetectionItem

logger = logging.getLogger("detection_service")

class DetectionService:
    """
    Central vision engine manager.
    Coordinates model selection (YOLO, Hybrid YOLO+OpenCV, OpenCV Heuristic, Diagnostic),
    executes inference with latency tracking, concurrency control,
    and annotation generation.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._is_processing = False
        self.is_fallback = False
        self.last_error: Optional[str] = None
        self._confidence_threshold: float = float(getattr(settings, "DETECTION_CONFIDENCE_THRESHOLD", 0.25))
        self._heuristic_complement = HeuristicDetector()
        self.detector: VisionModel = self._initialize_detector()

    def get_confidence_threshold(self) -> float:
        """Returns the current dynamic confidence threshold (Semana 11)."""
        with self._lock:
            return self._confidence_threshold

    def set_confidence_threshold(self, value: float) -> float:
        """
        Dynamically updates the detection confidence threshold without system restart (Semana 11).
        Validates allowed interval [0.15, 0.50]. Thread-safe to avoid race conditions during inference.
        """
        if value is None:
            raise ValueError("El umbral de confianza no puede ser nulo.")
        try:
            val_float = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Valor numérico de umbral inválido: {value}")

        if not (0.15 <= val_float <= 0.50):
            raise ValueError(
                f"Umbral de confianza fuera de rango ({val_float:.3f}). Debe estar comprendido estrictamente entre 0.15 y 0.50."
            )

        with self._lock:
            self._confidence_threshold = round(val_float, 3)
            setattr(settings, "DETECTION_CONFIDENCE_THRESHOLD", self._confidence_threshold)
            logger.info(f"[VisionEngine] Umbral de confianza dinámico actualizado a: {self._confidence_threshold}")
            return self._confidence_threshold

    def _initialize_detector(self) -> VisionModel:
        model_type = getattr(settings, "DETECTION_MODEL_TYPE", "heuristic").lower()
        logger.info(f"Configuring Vision Engine with model type: '{model_type}'")

        if model_type == "diagnostic":
            self.is_fallback = False
            return DiagnosticDetector(reason="Modo diagnóstico explícito configurado")

        if model_type in ("yolo", "hybrid"):
            weights_path = getattr(settings, "YOLO_WEIGHTS_PATH", "storage/weights/best.pt")
            device = getattr(settings, "YOLO_DEVICE", "cpu")
            yolo = YOLODetector(weights_path=weights_path, device=device)
            if yolo.load_model():
                self.is_fallback = False
                if model_type == "hybrid":
                    logger.info(f"Hybrid Vision Model (YOLO + OpenCV Heuristic) initialized from {weights_path}.")
                    return HybridDetector(primary_yolo=yolo, secondary_heuristic=self._heuristic_complement)
                logger.info(f"YOLO Vision Model initialized and active from {weights_path}.")
                return yolo
            
            # YOLO failed or weights are missing
            if getattr(settings, "DETECTION_FALLBACK_TO_HEURISTIC", True):
                self.is_fallback = True
                logger.warning(
                    f"YOLO no disponible ({yolo.load_error}). "
                    "Activando fallback seguro a detector heurístico OpenCV."
                )
                return HeuristicDetector()
            else:
                self.is_fallback = False
                logger.warning(
                    f"YOLO no disponible ({yolo.load_error}) y fallback deshabilitado. "
                    "Activando modo de diagnóstico explícito (sin detecciones simuladas)."
                )
                return DiagnosticDetector(reason=yolo.load_error or "Pesos YOLO no disponibles")

        # Default: Heuristic OpenCV
        self.is_fallback = False
        return HeuristicDetector()

    def set_detector(self, detector: VisionModel):
        """Allows dynamic swapping of vision models (e.g. for testing or reconfiguration)."""
        with self._lock:
            self.detector = detector
            self.is_fallback = False
            self.last_error = None
            info = detector.get_model_info() if hasattr(detector, "get_model_info") else {}
            logger.info(f"Vision model swapped to: {info.get('model_name')}")

    def reload(self):
        """Reloads vision detector according to current settings."""
        with self._lock:
            self.detector = self._initialize_detector()

    def is_busy(self) -> bool:
        """Indicates whether an inference task is currently executing."""
        return self._is_processing

    def process_frame(
        self,
        image: np.ndarray,
        drone_id: str,
        threshold: Optional[float] = None,
        frame_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        skip_if_busy: Optional[bool] = None
    ) -> Tuple[List[DetectionItem], Optional[np.ndarray], float]:
        """
        Processes a single camera frame or external image:
        1. Validates image using OpenCV ImageProcessor.
        2. Applies non-blocking concurrency guard if engine is busy (skippable for uploads).
        3. Executes inference via VisionModel.analyze contract.
           When YOLO is running with generic MS-COCO weights (is_specialized=False) and a Webots
           simulation frame ('drone-webots*') yields 0 COCO detections, complements with OpenCV
           HeuristicDetector so 3D simulation infrastructure (poles, vegetation, obstacles) is detected.
        4. Generates annotated image.
        5. Measures elapsed inference time in milliseconds.
        """
        if threshold is None:
            threshold = self._confidence_threshold

        # 1. Validation
        valid, err = ImageProcessor.validate_image_array(image)
        if not valid:
            logger.warning(f"Frame de dron/imagen '{drone_id}' descartado por validación de imagen: {err}")
            return [], None, 0.0

        # 2. Concurrency guard (skip if already processing to avoid unbounded backlog in video streams)
        should_skip = getattr(settings, "VISION_SKIP_FRAMES_ON_BUSY", True) if skip_if_busy is None else skip_if_busy
        if should_skip and self._is_processing:
            logger.debug(f"Vision Engine ocupado; descartando inferencia para frame de '{drone_id}'.")
            return [], None, 0.0

        with self._lock:
            start_time = time.perf_counter()
            self._is_processing = True

            try:
                # 3. Analyze
                detections = self.detector.analyze(
                    image,
                    confidence_threshold=threshold,
                    frame_id=frame_id,
                    timestamp=timestamp
                )

                # Hybrid complement for Webots 3D simulation frames when generic COCO weights are loaded
                if (
                    not detections
                    and isinstance(self.detector, YOLODetector)
                    and getattr(self.detector, "mode", "") == "pretrained_generic"
                    and getattr(settings, "HYBRID_COMPLEMENT_FOR_WEBOTS", True)
                    and (drone_id or "").startswith("drone-webots")
                ):
                    detections = self._heuristic_complement.analyze(
                        image,
                        confidence_threshold=threshold,
                        frame_id=frame_id,
                        timestamp=timestamp
                    )

                # 4. Annotate
                annotated_image = self.detector.annotate_image(image, detections)
                self.last_error = None

            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Excepción no controlada durante el procesamiento visual: {e}")
                detections = []
                annotated_image = None
            finally:
                self._is_processing = False
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            return detections, annotated_image, elapsed_ms

    def get_status(self) -> Dict[str, Any]:
        """
        Returns detailed status of the active vision engine and loaded detector,
        clearly reporting if Ultralytics is installed, weights exist, active backend,
        and whether a fallback or Webots hybrid complement is enabled.
        """
        info = self.detector.get_model_info() if hasattr(self.detector, "get_model_info") else {}
        is_available = self.detector.is_available() if hasattr(self.detector, "is_available") else True

        ultralytics_available = importlib.util.find_spec("ultralytics") is not None
        configured_weights = getattr(settings, "YOLO_WEIGHTS_PATH", "")
        weights_exist = Path(configured_weights).exists() if configured_weights else False
        is_yolo_active = info.get("backend") in ("yolo", "yolo_hybrid") and is_available

        return {
            "configured_model_type": getattr(settings, "DETECTION_MODEL_TYPE", "heuristic"),
            "ultralytics_available": ultralytics_available,
            "weights_path": configured_weights,
            "weights_exist": weights_exist,
            "is_loaded": info.get("is_loaded", False),
            "is_available": is_available,
            "active_model_name": info.get("model_name", "unknown"),
            "backend": info.get("backend", "opencv"),
            "device": info.get("device", "cpu"),
            "is_fallback": self.is_fallback,
            "is_diagnostic": info.get("is_diagnostic", False),
            "model_mode": info.get("model_mode", "standard"),
            "is_specialized": info.get("is_specialized", False),
            "hybrid_complement_for_webots": getattr(settings, "HYBRID_COMPLEMENT_FOR_WEBOTS", True),
            "load_error": info.get("load_error"),
            "last_inference_error": getattr(self, "last_error", None) or info.get("last_inference_error"),
            "confidence_threshold": self._confidence_threshold,
            "supported_classes": info.get("classes", getattr(settings, "TARGET_CLASSES", [])),
            "total_classes": info.get("total_classes", len(info.get("classes", []))),
            "skip_on_busy": getattr(settings, "VISION_SKIP_FRAMES_ON_BUSY", True),
            "yolo_ready": is_yolo_active,
            "yolo_model_loaded": is_yolo_active
        }

# Singleton instance
detection_service = DetectionService()
