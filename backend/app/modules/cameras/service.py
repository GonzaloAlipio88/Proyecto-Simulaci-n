import base64
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import cv2
import numpy as np
from sqlalchemy.orm import Session
from backend.app.schemas.camera import CameraFrameIn, CameraStatusResponse
from backend.app.modules.imagenes.service import image_service
from backend.app.modules.deteccion.service import detection_service
from backend.app.modules.incidentes.service import incidente_service
from backend.app.schemas.incidente import IncidenteCreate
from backend.app.core.websocket_manager import ws_manager

logger = logging.getLogger("camera_service")

class CameraService:
    def __init__(self):
        # Cache for latest frame per drone
        self.latest_frames: Dict[str, str] = {}
        self.latest_annotated_frames: Dict[str, str] = {}
        self.last_frame_time: Dict[str, datetime] = {}
        self.latest_metadata: Dict[str, Dict[str, Any]] = {}
        self.frame_counts: Dict[str, int] = {}

    async def ingest_frame(self, db: Session, frame_data: CameraFrameIn) -> Dict[str, Any]:
        drone_id = frame_data.drone_id
        b64_image = frame_data.image_base64
        
        # 1. Validation: Reject empty or non-string base64
        if not b64_image or not isinstance(b64_image, str) or len(b64_image.strip()) < 10:
            return {"success": False, "error": "Fotograma vacío o inválido"}

        # 2. Decode to OpenCV BGR image and validate dimensions
        cv_img = image_service.base64_to_cv2(b64_image)
        if cv_img is None:
            return {"success": False, "error": "Datos de imagen corruptos o formato no soportado"}

        h, w = cv_img.shape[:2]
        now = datetime.now(timezone.utc)
        if frame_data.timestamp:
            if frame_data.timestamp.tzinfo is None:
                captured_time = frame_data.timestamp.replace(tzinfo=timezone.utc)
            else:
                captured_time = frame_data.timestamp.astimezone(timezone.utc)
        else:
            captured_time = now

        self.latest_frames[drone_id] = b64_image
        self.last_frame_time[drone_id] = captured_time
        self.frame_counts[drone_id] = self.frame_counts.get(drone_id, 0) + 1
        self.latest_metadata[drone_id] = {
            "width": w,
            "height": h,
            "format": "image/jpeg",
            "captured_at": captured_time
        }

        detections = []
        annotated_b64 = None
        annotated_cv = None
        elapsed_ms = 0.0

        if frame_data.run_detection:
            detections, annotated_cv, elapsed_ms = detection_service.process_frame(
                cv_img,
                drone_id=drone_id
            )
            if annotated_cv is not None and len(detections) > 0:
                annotated_b64 = image_service.cv2_to_base64(annotated_cv)
                self.latest_annotated_frames[drone_id] = annotated_b64

        # Save to database (with storage bounded pruning)
        has_detections = len(detections) > 0
        img_record = image_service.save_image(
            db=db,
            image=cv_img,
            drone_id=drone_id,
            pos_x=frame_data.pos_x,
            pos_y=frame_data.pos_y,
            pos_z=frame_data.pos_z,
            has_detections=has_detections,
            detection_count=len(detections),
            annotated_image=annotated_cv if has_detections else None
        )

        # Automatic Incident creation for significant detections
        incidents_created = []
        for det in detections:
            if det.confidence >= 0.70 or det.severity in ["alta", "critica"]:
                inc_create = IncidenteCreate(
                    drone_id=drone_id,
                    tipo=det.label,
                    severidad=det.severity,
                    descripcion=det.description or f"Detección de {det.label} con confianza {det.confidence*100:.0f}%",
                    pos_x=frame_data.pos_x or 0.0,
                    pos_y=frame_data.pos_y or 0.0,
                    pos_z=frame_data.pos_z or 0.0,
                    confidence=det.confidence,
                    imagen_id=img_record.id,
                    estado="reportado"
                )
                inc_record = await incidente_service.create_incidente(db, inc_create)
                incidents_created.append(inc_record.id)

        # Broadcast live camera update & detection alert to WebSocket clients
        await ws_manager.broadcast("camera_stream", {
            "drone_id": drone_id,
            "timestamp": captured_time.isoformat(),
            "frame_base64": annotated_b64 or b64_image,
            "detections": [d.model_dump() for d in detections],
            "total_detected": len(detections),
            "inference_time_ms": round(elapsed_ms, 2),
            "image_id": img_record.id,
            "width": w,
            "height": h,
            "is_fresh": True
        })

        return {
            "success": True,
            "drone_id": drone_id,
            "image_id": img_record.id,
            "detections_count": len(detections),
            "detections": detections,
            "incidents_created": incidents_created,
            "inference_time_ms": elapsed_ms,
            "width": w,
            "height": h,
            "captured_at": captured_time.isoformat()
        }

    def get_latest_frame(self, drone_id: str, annotated: bool = True) -> Optional[str]:
        if annotated and drone_id in self.latest_annotated_frames:
            return self.latest_annotated_frames[drone_id]
        return self.latest_frames.get(drone_id)

    def get_latest_frame_info(self, drone_id: str, annotated: bool = True) -> Dict[str, Any]:
        b64 = self.get_latest_frame(drone_id, annotated=annotated)
        last_time = self.last_frame_time.get(drone_id)
        age = None
        is_fresh = False
        if last_time:
            now_utc = datetime.now(timezone.utc)
            if last_time.tzinfo is None:
                last_time_aware = last_time.replace(tzinfo=timezone.utc)
            else:
                last_time_aware = last_time
            age = max(0.0, (now_utc - last_time_aware).total_seconds())
            is_fresh = age <= 4.0

        meta = self.latest_metadata.get(drone_id, {})
        return {
            "available": b64 is not None,
            "drone_id": drone_id,
            "annotated": annotated,
            "frame_base64": b64,
            "captured_at": last_time,
            "age_seconds": round(age, 2) if age is not None else None,
            "is_fresh": is_fresh,
            "width": meta.get("width"),
            "height": meta.get("height"),
            "format": meta.get("format", "image/jpeg")
        }

    def get_status(self) -> CameraStatusResponse:
        active_drones = list(self.latest_frames.keys())
        last_time = max(self.last_frame_time.values()) if self.last_frame_time else None
        return CameraStatusResponse(
            is_active=len(active_drones) > 0,
            last_frame_timestamp=last_time,
            resolution="640x480",
            fps=2.5 if len(active_drones) > 0 else 0.0,
            connected_drones=active_drones
        )

camera_service = CameraService()

