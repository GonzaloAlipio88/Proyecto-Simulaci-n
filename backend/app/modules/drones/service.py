import logging
import threading
import uuid
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from backend.app.models.dron import Drone
from backend.app.schemas.dron import DroneCreate, DroneUpdate, DroneCommand
from backend.app.core.websocket_manager import ws_manager

logger = logging.getLogger("drone_service")

# Comandos soportados entre Dashboard, FastAPI y el controlador Webots
VALID_DRONE_COMMANDS = {
    "takeoff": ("flying", "TAKEOFF"),
    "hover": ("hovering", "HOVER"),
    "resume_patrol": ("flying", "NAVIGATING"),
    "return_to_home": ("returning", "RETURNING"),
    "rtl": ("returning", "RETURNING"),
    "rth": ("returning", "RETURNING"),
    "land": ("landed", "LANDING"),
    "set_waypoint": ("flying", "NAVIGATING"),
}

CANONICAL_CONTROLLER_COMMANDS = {
    "takeoff": "TAKEOFF",
    "hover": "HOVER",
    "resume_patrol": "RESUME_PATROL",
    "return_to_home": "RETURN_TO_HOME",
    "rtl": "RETURN_TO_HOME",
    "rth": "RETURN_TO_HOME",
    "land": "LAND",
    "set_waypoint": "SET_WAYPOINT",
}

# Los 5 waypoints oficiales del corredor vial de simulación Webots (inspection_zone.wbt)
SIMULATION_WAYPOINTS = [
    {"index": 1, "x": 0.0, "y": -30.0, "z": 6.0, "hover_time": 3.0, "name": "WP 1: Sector Sur", "description": "Waypoint 1: Sector Sur - Poste de Alumbrado Inicial"},
    {"index": 2, "x": 0.0, "y": -15.0, "z": 6.0, "hover_time": 3.0, "name": "WP 2: Tramo Sur-Centro", "description": "Waypoint 2: Tramo Sur-Centro - Pinos y Borde Vial"},
    {"index": 3, "x": 0.0, "y": 0.0, "z": 6.0, "hover_time": 3.0, "name": "WP 3: Sector Central", "description": "Waypoint 3: Sector Central - Cajas en Vía y Poste Central"},
    {"index": 4, "x": 0.0, "y": 15.0, "z": 6.0, "hover_time": 3.0, "name": "WP 4: Tramo Centro-Norte", "description": "Waypoint 4: Tramo Centro-Norte - Parche de Vegetación Invasiva"},
    {"index": 5, "x": 0.0, "y": 30.0, "z": 6.0, "hover_time": 3.0, "name": "WP 5: Sector Norte", "description": "Waypoint 5: Sector Norte - Roca en Vía y Poste Norte"},
]


class DroneService:
    def __init__(self):
        self._lock = threading.Lock()
        self._pending_commands: Dict[str, List[Dict[str, Any]]] = {}

    def get_or_create(self, db: Session, drone_data: DroneCreate) -> Drone:
        drone = db.query(Drone).filter(Drone.id == drone_data.id).first()
        if not drone:
            drone = Drone(
                id=drone_data.id,
                name=drone_data.name,
                model=drone_data.model,
                status=drone_data.status,
                battery_level=drone_data.battery_level,
                current_x=drone_data.current_x,
                current_y=drone_data.current_y,
                current_z=drone_data.current_z,
                current_speed=drone_data.current_speed,
                flight_mode=drone_data.flight_mode,
                last_seen_at=datetime.utcnow()
            )
            db.add(drone)
            db.commit()
            db.refresh(drone)
        return drone

    def list_drones(self, db: Session) -> List[Drone]:
        return db.query(Drone).all()

    def get_drone(self, db: Session, drone_id: str) -> Optional[Drone]:
        return db.query(Drone).filter(Drone.id == drone_id).first()

    def update_drone(self, db: Session, drone_id: str, update_data: DroneUpdate) -> Optional[Drone]:
        drone = self.get_drone(db, drone_id)
        if not drone:
            return None

        data = update_data.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(drone, key, value)
        drone.last_seen_at = datetime.utcnow()
        db.commit()
        db.refresh(drone)
        return drone

    def get_simulation_waypoints(self) -> List[Dict[str, Any]]:
        return [dict(wp) for wp in SIMULATION_WAYPOINTS]

    def peek_pending_commands(self, drone_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._pending_commands.get(drone_id, []))

    def pop_pending_commands(self, drone_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            cmds = self._pending_commands.pop(drone_id, [])
            return list(cmds)

    async def send_command(self, db: Session, drone_id: str, cmd: DroneCommand) -> dict:
        drone = self.get_drone(db, drone_id)
        if not drone:
            return {"success": False, "message": f"Drone {drone_id} no encontrado"}

        raw_cmd = (cmd.command or "").strip().lower()
        if raw_cmd not in VALID_DRONE_COMMANDS:
            return {
                "success": False,
                "message": f"Comando '{cmd.command}' no soportado. Use: takeoff, hover, resume_patrol, return_to_home, land."
            }

        new_status, new_flight_mode = VALID_DRONE_COMMANDS[raw_cmd]
        canonical_cmd = CANONICAL_CONTROLLER_COMMANDS[raw_cmd]

        drone.status = new_status
        drone.flight_mode = new_flight_mode
        drone.last_seen_at = datetime.utcnow()

        db.commit()
        db.refresh(drone)

        cmd_entry = {
            "command_id": str(uuid.uuid4()),
            "drone_id": drone_id,
            "command": canonical_cmd,
            "raw_command": raw_cmd,
            "new_status": drone.status,
            "new_flight_mode": drone.flight_mode,
            "params": cmd.params or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        with self._lock:
            self._pending_commands.setdefault(drone_id, []).append(cmd_entry)

        # Broadcast command to Webots and frontend clients
        await ws_manager.broadcast("drone_command", cmd_entry)

        return {
            "success": True,
            "command_id": cmd_entry["command_id"],
            "drone_id": drone_id,
            "command": cmd.command,
            "canonical_command": canonical_cmd,
            "new_status": drone.status,
            "new_flight_mode": drone.flight_mode,
            "message": f"Comando '{canonical_cmd}' encolado y transmitido con éxito"
        }


drone_service = DroneService()
