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
    def __init__(self):
        self.images_dir = settings.IMAGES_DIR
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def base64_to_cv2(self, b64_str: str) -> np.ndarray:
        if "," in b64_str:
            b64_str = b64_str.split(",")[1]
        img_bytes = base64.b64decode(b64_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    def cv2_to_base64(self, image: np.ndarray) -> str:
        _, buffer = cv2.imencode('.jpg', image, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        return base64.b64encode(buffer).decode('utf-8')

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
        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{drone_id}_{timestamp_str}_{unique_id}.jpg"
        file_path = self.images_dir / filename
        cv2.imwrite(str(file_path), image)

        annotated_filename = None
        if annotated_image is not None and has_detections:
            annotated_filename = f"annotated_{filename}"
            annotated_path = self.images_dir / annotated_filename
            cv2.imwrite(str(annotated_path), annotated_image)

        record = ImageRecord(
            drone_id=drone_id,
            filename=filename,
            file_path=str(file_path),
            captured_at=datetime.utcnow(),
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
        return record

    def get_image_path(self, filename: str) -> Optional[Path]:
        path = self.images_dir / filename
        if path.exists():
            return path
        return None

image_service = ImageService()
