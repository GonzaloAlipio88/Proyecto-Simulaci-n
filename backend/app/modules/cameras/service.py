import base64
import logging
from datetime import datetime
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
        self.frame_counts: Dict[str, int] = {}

    async def ingest_frame(self, db: Session, frame_data: CameraFrameIn) -> Dict[str, Any]:
        drone_id = frame_data.drone_id
        b64_image = frame_data.image_base64
        
        # Convert base64 to OpenCV BGR image
        cv_img = image_service.base64_to_cv2(b64_image)
        if cv_img is None:
            return {"success": False, "error": "No se pudo decodificar la imagen"}

        self.latest_frames[drone_id] = b64_image
        self.last_frame_time[drone_id] = datetime.utcnow()
        self.frame_counts[drone_id] = self.frame_counts.get(drone_id, 0) + 1

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

        # Save to database
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
            "timestamp": datetime.utcnow().isoformat(),
            "frame_base64": annotated_b64 or b64_image,
            "detections": [d.model_dump() for d in detections],
            "total_detected": len(detections),
            "inference_time_ms": round(elapsed_ms, 2),
            "image_id": img_record.id
        })

        return {
            "success": True,
            "drone_id": drone_id,
            "image_id": img_record.id,
            "detections_count": len(detections),
            "detections": detections,
            "incidents_created": incidents_created,
            "inference_time_ms": elapsed_ms
        }

    def get_latest_frame(self, drone_id: str, annotated: bool = True) -> Optional[str]:
        if annotated and drone_id in self.latest_annotated_frames:
            return self.latest_annotated_frames[drone_id]
        return self.latest_frames.get(drone_id)

    def get_status(self) -> CameraStatusResponse:
        active_drones = list(self.latest_frames.keys())
        last_time = max(self.last_frame_time.values()) if self.last_frame_time else None
        return CameraStatusResponse(
            is_active=len(active_drones) > 0,
            last_frame_timestamp=last_time,
            resolution="640x480",
            fps=10.0 if len(active_drones) > 0 else 0.0,
            connected_drones=active_drones
        )

camera_service = CameraService()
