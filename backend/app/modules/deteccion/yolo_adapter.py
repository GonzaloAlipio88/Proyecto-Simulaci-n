import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
import numpy as np

from backend.app.modules.deteccion.base import VisionModel
from backend.app.modules.deteccion.image_processor import ImageProcessor
from backend.app.schemas.deteccion import DetectionItem, BoundingBox

logger = logging.getLogger("yolo_adapter")

class YOLODetector(VisionModel):
    """
    Decoupled Adapter for Ultralytics YOLO (v8 / v11) model.
    Key design guarantees:
    1. Loads model into memory only once (singleton / cached).
    2. Does NOT download large weights automatically on startup.
    3. Verifies weights file existence before attempting load.
    4. Supports configurable device selection ('cpu', 'cuda', 'auto') without requiring an NVIDIA GPU.
    5. Reads actual class names from model metadata (model.names).
    6. Distinguishes 'pretrained_generic' (COCO classes) from 'specialized_infrastructure'.
    7. Returns structured detections conforming to VisionModel.analyze contract.
    8. Clearly reports availability state (does not claim real YOLO when weights/library are absent).
    """

    DEFAULT_FALLBACK_CLASSES = {
        0: "poste_luz",
        1: "vegetacion_invasiva",
        2: "obstruccion_via"
    }

    def __init__(
        self,
        weights_path: str = "storage/weights/best.pt",
        device: str = "cpu",
        class_mapping: Optional[Dict[int, str]] = None
    ):
        self.weights_path = weights_path
        self.requested_device = device
        self.resolved_device = "cpu"
        self.class_mapping = class_mapping or self.DEFAULT_FALLBACK_CLASSES
        self.raw_class_names: Dict[int, str] = {}
        self.mode = "uninitialized"
        self.model = None
        self.is_loaded = False
        self.load_error: Optional[str] = None
        self.last_inference_error: Optional[str] = None
        self._load_attempted = False

    def _resolve_device(self) -> str:
        """Determines computation device with safe CPU fallback."""
        if self.requested_device == "cpu":
            return "cpu"
        
        try:
            import torch
            if self.requested_device in ("cuda", "auto"):
                if torch.cuda.is_available():
                    return "cuda:0"
                else:
                    logger.info("CUDA not available; falling back to CPU for YOLO inference.")
                    return "cpu"
        except ImportError:
            pass

        return "cpu"

    def load_model(self) -> bool:
        """
        Loads YOLO model weights once.
        Safely aborts if file does not exist or if ultralytics is not installed.
        """
        if self.is_loaded and self.model is not None:
            return True

        self._load_attempted = True
        weights_file = Path(self.weights_path)

        # 1. Strictly avoid downloading large weights automatically if file does not exist
        if not weights_file.exists() or not weights_file.is_file():
            self.load_error = f"Archivo de pesos no encontrado en: {weights_file.resolve()}"
            logger.warning(
                f"[YOLO Adapter] {self.load_error}. "
                "No se descargarán modelos automáticamente durante el arranque."
            )
            self.is_loaded = False
            self.mode = "missing_weights"
            return False

        # 2. Check file size (prevent loading 0-byte or corrupt placeholders)
        if weights_file.stat().st_size < 1024:
            self.load_error = f"El archivo de pesos '{weights_file}' está corrupto o vacío (<1KB)."
            logger.warning(f"[YOLO Adapter] {self.load_error}")
            self.is_loaded = False
            self.mode = "corrupt_weights"
            return False

        # 3. Import ultralytics library
        try:
            from ultralytics import YOLO
        except ImportError as e:
            self.load_error = "Biblioteca 'ultralytics' no instalada en el entorno Python."
            logger.warning(
                f"[YOLO Adapter] {self.load_error} "
                "Instale con: pip install ultralytics"
            )
            self.is_loaded = False
            self.mode = "library_missing"
            return False

        # 4. Instantiate model and set device
        try:
            self.resolved_device = self._resolve_device()
            logger.info(f"[YOLO Adapter] Cargando modelo YOLO desde {weights_file} en dispositivo '{self.resolved_device}'...")
            self.model = YOLO(str(weights_file))
            self.is_loaded = True
            self.load_error = None

            # 5. Extract authentic class names from model metadata
            if hasattr(self.model, "names") and self.model.names:
                self.raw_class_names = {int(k): str(v) for k, v in self.model.names.items()}
                # Check whether the loaded model has custom highway classes
                has_highway = any(
                    c in self.raw_class_names.values()
                    for c in ["poste_luz", "vegetacion_invasiva", "obstruccion_via"]
                )
                if has_highway:
                    self.mode = "specialized_infrastructure"
                else:
                    self.mode = "pretrained_generic"
                self.class_mapping = self.raw_class_names
            else:
                self.mode = "pretrained_generic"

            logger.info(
                f"[YOLO Adapter] Modelo YOLO cargado con éxito en {self.resolved_device}. "
                f"Modo: {self.mode} ({len(self.class_mapping)} clases detectadas)."
            )
            return True
        except Exception as e:
            self.load_error = f"Fallo al inicializar pesos YOLO: {e}"
            logger.error(f"[YOLO Adapter] {self.load_error}")
            self.model = None
            self.is_loaded = False
            self.mode = "init_failed"
            return False

    def is_available(self) -> bool:
        """Returns True if model is initialized and ready for real inference."""
        return self.is_loaded and self.model is not None

    def analyze(
        self,
        image: np.ndarray,
        confidence_threshold: float = 0.5,
        frame_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> List[DetectionItem]:
        """
        Performs real YOLO inference on a validated image array.
        """
        valid, err = ImageProcessor.validate_image_array(image)
        if not valid:
            logger.warning(f"[YOLO Adapter] Imagen rechazada por validación: {err}")
            return []

        if not self.is_available():
            logger.debug("[YOLO Adapter] Modelo no disponible; devolviendo lista vacía.")
            return []

        detections: List[DetectionItem] = []
        try:
            # OpenCV provides BGR images. Ultralytics accepts BGR numpy arrays natively.
            results = self.model.predict(
                source=image,
                conf=confidence_threshold,
                device=self.resolved_device,
                verbose=False
            )

            for r in results:
                if not hasattr(r, "boxes") or r.boxes is None:
                    continue
                for box in r.boxes:
                    cls_id = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    xyxy = box.xyxy[0].tolist()

                    label = self.class_mapping.get(cls_id, f"clase_{cls_id}")
                    # Severity heuristic based on detected category
                    if label in ["obstruccion_via", "vegetacion_invasiva", "stop sign", "traffic light", "car", "truck", "bus"]:
                        severity = "alta"
                    elif label in ["person", "bicycle", "motorcycle"]:
                        severity = "critica"
                    else:
                        severity = "media"

                    detections.append(DetectionItem(
                        label=label,
                        class_name=label,
                        confidence=round(conf, 4),
                        bbox=BoundingBox(
                            x_min=float(xyxy[0]),
                            y_min=float(xyxy[1]),
                            x_max=float(xyxy[2]),
                            y_max=float(xyxy[3])
                        ),
                        severity=severity,
                        description=f"Detección YOLO [{self.mode}] de {label} (conf: {conf*100:.1f}%)",
                        frame_id=frame_id,
                        timestamp=timestamp
                    ))
            self.last_inference_error = None
        except Exception as e:
            self.last_inference_error = str(e)
            logger.error(f"[YOLO Adapter] Error durante inferencia YOLO: {e}")
            raise

        return detections

    def annotate_image(self, image: np.ndarray, detections: List[DetectionItem]) -> np.ndarray:
        """Draws bounding boxes and labels onto the image."""
        return ImageProcessor.annotate_detections(image, detections)

    def get_model_info(self) -> Dict[str, Any]:
        """Returns comprehensive diagnostic and execution metadata."""
        return {
            "model_name": "ultralytics_yolo",
            "backend": "yolo",
            "device": self.resolved_device,
            "weights_path": self.weights_path,
            "model_mode": self.mode,
            "is_specialized": self.mode == "specialized_infrastructure",
            "is_loaded": self.is_loaded,
            "is_available": self.is_available(),
            "load_error": self.load_error,
            "last_inference_error": self.last_inference_error,
            "classes": list(self.class_mapping.values()),
            "total_classes": len(self.class_mapping)
        }
