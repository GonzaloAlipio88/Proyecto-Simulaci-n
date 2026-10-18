import base64
import logging
from typing import Optional, Tuple, List
import cv2
import numpy as np
from backend.app.schemas.deteccion import DetectionItem

logger = logging.getLogger("image_processor")

class ImageProcessingError(Exception):
    """Custom exception raised when an image fails OpenCV decoding or validation."""
    pass

class ImageProcessor:
    """
    Centralized OpenCV image validation, conversion, and annotation engine.
    Ensures safe handling of buffers, avoids unnecessary color-space conversions,
    and enforces strict dimension and dtype checks.
    """

    MIN_WIDTH: int = 16
    MIN_HEIGHT: int = 16
    MAX_WIDTH: int = 4096
    MAX_HEIGHT: int = 4096

    CLASS_COLORS = {
        "poste_luz": (255, 180, 0),          # Cyan / Yellow-Blue in BGR
        "vegetacion_invasiva": (60, 220, 60), # Vivid Green in BGR
        "obstruccion_via": (40, 40, 230),     # Vivid Red in BGR
    }
    DEFAULT_COLOR = (0, 255, 255)            # Yellow in BGR

    @classmethod
    def validate_image_array(cls, image: Optional[np.ndarray]) -> Tuple[bool, Optional[str]]:
        """
        Validates that a numpy array is a valid OpenCV image:
        - Non-null and non-empty
        - uint8 data type
        - 2D (grayscale) or 3D (color with 3 channels)
        - Dimensions within acceptable bounds
        """
        if image is None:
            return False, "Imagen nula (None)"
        if not isinstance(image, np.ndarray):
            return False, f"Tipo de objeto inválido: esperado np.ndarray, recibido {type(image)}"
        if image.size == 0:
            return False, "Matriz de imagen vacía (size == 0)"
        if image.dtype != np.uint8:
            return False, f"Tipo de datos de píxel inválido: {image.dtype}, se requiere uint8"
        
        ndim = image.ndim
        if ndim == 2:
            h, w = image.shape
            c = 1
        elif ndim == 3:
            h, w, c = image.shape
            if c not in (1, 3, 4):
                return False, f"Número de canales no soportado: {c} (se espera 1, 3 o 4)"
        else:
            return False, f"Dimensiones de matriz no válidas (ndim={ndim})"

        if w < cls.MIN_WIDTH or h < cls.MIN_HEIGHT:
            return False, f"Dimensiones inferiores al mínimo requerido: {w}x{h} (mínimo {cls.MIN_WIDTH}x{cls.MIN_HEIGHT})"
        if w > cls.MAX_WIDTH or h > cls.MAX_HEIGHT:
            return False, f"Dimensiones superiores al máximo permitido: {w}x{h} (máximo {cls.MAX_WIDTH}x{cls.MAX_HEIGHT})"

        return True, None

    @classmethod
    def base64_to_bgr(cls, b64_str: str) -> Optional[np.ndarray]:
        """
        Decodes a base64 encoded image string safely into an OpenCV BGR numpy array.
        Handles data URIs (e.g., 'data:image/jpeg;base64,...').
        Returns None if string is invalid or corrupt.
        """
        if not b64_str or not isinstance(b64_str, str):
            logger.warning("Base64 string is empty or not a string")
            return None
        
        stripped = b64_str.strip()
        if len(stripped) < 16:
            logger.warning("Base64 string length is too short to be a valid image")
            return None

        try:
            if "," in stripped:
                stripped = stripped.split(",", 1)[1]
            img_bytes = base64.b64decode(stripped, validate=True)
            if not img_bytes:
                return None
            return cls.bytes_to_bgr(img_bytes)
        except Exception as e:
            logger.warning(f"Error decodificando base64 a imagen OpenCV: {e}")
            return None

    @classmethod
    def bytes_to_bgr(cls, data: bytes) -> Optional[np.ndarray]:
        """
        Decodes raw image bytes into an OpenCV BGR numpy array and verifies integrity.
        """
        if not data or len(data) == 0:
            return None
        try:
            nparr = np.frombuffer(data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            valid, err = cls.validate_image_array(img)
            if not valid:
                logger.warning(f"Decoded image failed validation: {err}")
                return None
            return img
        except Exception as e:
            logger.error(f"Error decodificando bytes con cv2.imdecode: {e}")
            return None

    @classmethod
    def bgr_to_rgb(cls, bgr_image: np.ndarray) -> np.ndarray:
        """
        Converts BGR to RGB if needed by deep learning frameworks (e.g. PyTorch/YOLO).
        Only converts if input is a valid 3-channel image.
        """
        if bgr_image is None or bgr_image.ndim != 3 or bgr_image.shape[2] != 3:
            return bgr_image
        return cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)

    @classmethod
    def rgb_to_bgr(cls, rgb_image: np.ndarray) -> np.ndarray:
        """Converts RGB to BGR."""
        if rgb_image is None or rgb_image.ndim != 3 or rgb_image.shape[2] != 3:
            return rgb_image
        return cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)

    @classmethod
    def bgr_to_base64(cls, image: np.ndarray, quality: int = 85) -> Optional[str]:
        """Encodes an OpenCV BGR image into a base64 JPEG string."""
        if image is None:
            return None
        try:
            ok, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            if not ok:
                return None
            return base64.b64encode(buffer).decode('utf-8')
        except Exception as e:
            logger.error(f"Error codificando imagen a Base64: {e}")
            return None

    @classmethod
    def annotate_detections(
        cls,
        image: np.ndarray,
        detections: List[DetectionItem],
        draw_labels: bool = True
    ) -> np.ndarray:
        """
        Draws bounding boxes and labels onto a copy of the input image.
        Returns a new contiguous BGR image array.
        """
        if image is None:
            return None
        annotated = image.copy()
        h, w = annotated.shape[:2]

        for det in detections:
            color = cls.CLASS_COLORS.get(det.label, cls.DEFAULT_COLOR)
            x1 = int(max(0, min(w - 1, det.bbox.x_min)))
            y1 = int(max(0, min(h - 1, det.bbox.y_min)))
            x2 = int(max(0, min(w - 1, det.bbox.x_max)))
            y2 = int(max(0, min(h - 1, det.bbox.y_max)))

            # Draw bounding box rectangle
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

            if draw_labels:
                display_label = det.class_name or det.label
                text = f"{display_label}: {int(det.confidence * 100)}%"
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                
                # Top label banner
                bg_y1 = max(0, y1 - th - 6)
                bg_y2 = y1
                cv2.rectangle(annotated, (x1, bg_y1), (min(w - 1, x1 + tw + 6), bg_y2), color, -1)
                cv2.putText(
                    annotated,
                    text,
                    (x1 + 3, max(12, y1 - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 0, 0),
                    1,
                    cv2.LINE_AA
                )

        return annotated
