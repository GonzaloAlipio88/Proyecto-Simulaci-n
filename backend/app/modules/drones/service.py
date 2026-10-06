from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import logging
from backend.app.models.dron import Drone
from backend.app.schemas.dron import DroneCreate, DroneUpdate, DroneCommand
from backend.app.core.websocket_manager import ws_manager

logger = logging.getLogger("drone_service")

class DroneService:
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

    async def send_command(self, db: Session, drone_id: str, cmd: DroneCommand) -> dict:
        drone = self.get_drone(db, drone_id)
        if not drone:
            return {"success": False, "message": f"Drone {drone_id} no encontrado"}

        # Update local drone state based on command
        if cmd.command == "takeoff":
            drone.status = "flying"
        elif cmd.command == "land":
            drone.status = "landed"
        elif cmd.command == "hover":
            drone.status = "hovering"
        elif cmd.command == "return_to_home":
            drone.status = "returning"
            
        db.commit()
        db.refresh(drone)

        # Broadcast command to Webots and frontend clients
        await ws_manager.broadcast("drone_command", {
            "drone_id": drone_id,
            "command": cmd.command,
            "params": cmd.params or {},
            "timestamp": datetime.utcnow().isoformat()
        })

        return {
            "success": True,
            "drone_id": drone_id,
            "command": cmd.command,
            "new_status": drone.status,
            "message": f"Comando '{cmd.command}' transmitido con éxito"
        }

drone_service = DroneService()
