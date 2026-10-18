import os
import base64
import json
import logging
import time
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger("drone_comm")

class DroneCommunicationClient:
    """Handles communication between Webots drone simulation and FastAPI backend."""

    def __init__(self, backend_url: str = "http://127.0.0.1:8000", drone_id: str = "drone-webots-01"):
        env_backend = os.environ.get("BACKEND_URL")
        self.backend_url = (env_backend or backend_url).rstrip("/")
        self.drone_id = drone_id
        self.api_prefix = f"{self.backend_url}/api/v1"
        self.session = requests.Session()
        self.is_registered = False

    def register(self, name: str = "Webots Mavic 2 Pro", model: str = "DJI Mavic 2 Pro") -> bool:
        payload = {
            "id": self.drone_id,
            "name": name,
            "model": model,
            "status": "idle",
            "battery_level": 100.0,
            "current_x": 0.0,
            "current_y": -45.0,
            "current_z": 0.2,
            "current_speed": 0.0,
            "flight_mode": "autonomous"
        }
        try:
            res = self.session.post(f"{self.api_prefix}/drones", json=payload, timeout=1.5)
            if res.status_code in (200, 201):
                self.is_registered = True
                logger.info(f"Drone {self.drone_id} registered with backend at {self.backend_url}.")
                return True
        except Exception as e:
            logger.warning(f"Could not connect to backend to register drone: {e}")
        return False

    def send_telemetry(
        self,
        pos_x: float,
        pos_y: float,
        pos_z: float,
        roll: float = 0.0,
        pitch: float = 0.0,
        yaw: float = 0.0,
        speed: float = 0.0,
        battery: float = 100.0,
        flight_mode: str = "autonomous",
        current_waypoint: int = 0,
        current_mission: str = "Mision_Inspeccion_Vigilancia_Vias",
        state_description: Optional[str] = None
    ) -> bool:
        payload = {
            "drone_id": self.drone_id,
            "pos_x": round(pos_x, 3),
            "pos_y": round(pos_y, 3),
            "pos_z": round(pos_z, 3),
            "roll": round(roll, 3),
            "pitch": round(pitch, 3),
            "yaw": round(yaw, 3),
            "speed": round(speed, 2),
            "battery": round(battery, 1),
            "flight_mode": flight_mode,
            "current_waypoint": current_waypoint,
            "current_mission": current_mission,
            "state_description": state_description
        }
        try:
            res = self.session.post(f"{self.api_prefix}/telemetria", json=payload, timeout=0.4)
            return res.status_code == 200
        except Exception as e:
            logger.debug(f"Telemetry send failed: {e}")
            return False

    def send_camera_frame(
        self,
        image_base64: str,
        pos_x: float,
        pos_y: float,
        pos_z: float,
        run_detection: bool = True,
        timestamp: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        payload = {
            "drone_id": self.drone_id,
            "image_base64": image_base64,
            "pos_x": round(pos_x, 3),
            "pos_y": round(pos_y, 3),
            "pos_z": round(pos_z, 3),
            "run_detection": run_detection,
            "timestamp": timestamp
        }
        try:
            res = self.session.post(f"{self.api_prefix}/cameras/frame", json=payload, timeout=0.8)
            if res.status_code == 200:
                return res.json()
        except Exception as e:
            logger.debug(f"Frame send failed: {e}")
        return None

