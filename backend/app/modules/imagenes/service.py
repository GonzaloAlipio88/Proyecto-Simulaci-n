import os
import uuid
import base64
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.models.imagen import ImageRecord
from backend.app.schemas.imagen import ImageResponse

class ImageService:
    def __init__(self, max_stored_images: int = 60):
        self.images_dir = settings.IMAGES_DIR
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.max_stored_images = max_stored_images

    def base64_to_cv2(self, b64_str: str) -> Optional[np.ndarray]:
        """Safely decode base64 string to OpenCV BGR numpy array."""
        if not b64_str or not isinstance(b64_str, str):
            return None
        try:
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_str)
            if not img_bytes:
                return None
            nparr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None or img.size == 0 or img.shape[0] == 0 or img.shape[1] == 0:
                return None
            return img
        except Exception:
            return None

    def cv2_to_base64(self, image: np.ndarray, quality: int = 85) -> str:
        """Encode OpenCV BGR image to base64 JPEG string."""
        _, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        return base64.b64encode(buffer).decode('utf-8')

    def _prune_storage_if_needed(self):
        """Bounded storage retention: removes oldest image files when limit is reached."""
        try:
            files = sorted(
                [f for f in self.images_dir.glob("*.jpg") if f.is_file()],
                key=lambda p: p.stat().st_mtime
            )
            if len(files) > self.max_stored_images:
                excess = len(files) - self.max_stored_images
                for old_file in files[:excess]:
                    try:
                        old_file.unlink(missing_ok=True)
                    except OSError:
                        pass
        except Exception:
            pass

    def save_image(
        self,
        db: Session,
        image: np.ndarray,
        drone_id: str,
        pos_x: Optional[float] = None,
        pos_y: Optional[float] = None,
        pos_z: Optional[float] = None,
        has_detections: bool = False,
        detection_count: int = 0,
        annotated_image: Optional[np.ndarray] = None
    ) -> ImageRecord:
        now = datetime.now()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{drone_id}_{timestamp_str}_{unique_id}.jpg"
        file_path = self.images_dir / filename

        # Safe atomic write for raw frame
        temp_path = self.images_dir / f".tmp_{filename}"
        cv2.imwrite(str(temp_path), image)
        temp_path.replace(file_path)

        annotated_filename = None
        if annotated_image is not None and has_detections:
            annotated_filename = f"annotated_{filename}"
            annotated_path = self.images_dir / annotated_filename
            temp_annotated = self.images_dir / f".tmp_{annotated_filename}"
            cv2.imwrite(str(temp_annotated), annotated_image)
            temp_annotated.replace(annotated_path)

        record = ImageRecord(
            drone_id=drone_id,
            filename=filename,
            file_path=str(file_path),
            captured_at=now,
            pos_x=pos_x,
            pos_y=pos_y,
            pos_z=pos_z,
            has_detections=has_detections,
            detection_count=detection_count,
            annotated_filename=annotated_filename
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        # Enforce storage limits
        self._prune_storage_if_needed()

        return record

    def get_image_path(self, filename: str) -> Optional[Path]:
        path = self.images_dir / filename
        if path.exists():
            return path
        return None

image_service = ImageService()

