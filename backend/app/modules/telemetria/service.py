from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import logging
from backend.app.models.telemetria import TelemetryRecord
from backend.app.models.dron import Drone
from backend.app.schemas.telemetria import TelemetryIn, TelemetryResponse
from backend.app.core.websocket_manager import ws_manager

logger = logging.getLogger("telemetry_service")

class TelemetryService:
    async def record_telemetry(self, db: Session, telemetry_data: TelemetryIn) -> TelemetryRecord:
        # Create record in DB
        record = TelemetryRecord(
            drone_id=telemetry_data.drone_id,
            timestamp=datetime.utcnow(),
            pos_x=telemetry_data.pos_x,
            pos_y=telemetry_data.pos_y,
            pos_z=telemetry_data.pos_z,
            roll=telemetry_data.roll,
            pitch=telemetry_data.pitch,
            yaw=telemetry_data.yaw,
            speed=telemetry_data.speed,
            battery=telemetry_data.battery,
            flight_mode=telemetry_data.flight_mode,
            current_waypoint=telemetry_data.current_waypoint,
            current_mission=telemetry_data.current_mission,
            state_description=telemetry_data.state_description
        )
        db.add(record)

        # Update drone state
        drone = db.query(Drone).filter(Drone.id == telemetry_data.drone_id).first()
        if drone:
            drone.current_x = telemetry_data.pos_x
            drone.current_y = telemetry_data.pos_y
            drone.current_z = telemetry_data.pos_z
            drone.current_speed = telemetry_data.speed
            drone.battery_level = telemetry_data.battery
            drone.flight_mode = telemetry_data.flight_mode
            drone.current_waypoint = telemetry_data.current_waypoint
            drone.current_mission = telemetry_data.current_mission
            drone.last_seen_at = datetime.utcnow()
            if drone.status == "idle" and telemetry_data.pos_z > 0.5:
                drone.status = "flying"
        else:
            # Auto-register drone if not yet registered
            new_drone = Drone(
                id=telemetry_data.drone_id,
                name=f"Webots Drone {telemetry_data.drone_id}",
                status="flying" if telemetry_data.pos_z > 0.5 else "idle",
                battery_level=telemetry_data.battery,
                current_x=telemetry_data.pos_x,
                current_y=telemetry_data.pos_y,
                current_z=telemetry_data.pos_z,
                current_speed=telemetry_data.speed,
                flight_mode=telemetry_data.flight_mode,
                current_waypoint=telemetry_data.current_waypoint,
                current_mission=telemetry_data.current_mission,
                last_seen_at=datetime.utcnow()
            )
            db.add(new_drone)

        db.commit()
        db.refresh(record)

        # Real-time WebSocket broadcast
        await ws_manager.broadcast("telemetry", {
            "id": record.id,
            "drone_id": record.drone_id,
            "timestamp": record.timestamp.isoformat(),
            "pos_x": record.pos_x,
            "pos_y": record.pos_y,
            "pos_z": record.pos_z,
            "roll": record.roll,
            "pitch": record.pitch,
            "yaw": record.yaw,
            "speed": record.speed,
            "battery": record.battery,
            "flight_mode": record.flight_mode,
            "current_waypoint": record.current_waypoint,
            "current_mission": record.current_mission,
            "state_description": record.state_description
        })


        return record

    def get_latest_telemetry(self, db: Session, drone_id: str) -> Optional[TelemetryRecord]:
        return db.query(TelemetryRecord)\
            .filter(TelemetryRecord.drone_id == drone_id)\
            .order_by(TelemetryRecord.timestamp.desc())\
            .first()

    def get_history(self, db: Session, drone_id: str, limit: int = 100) -> List[TelemetryRecord]:
        return db.query(TelemetryRecord)\
            .filter(TelemetryRecord.drone_id == drone_id)\
            .order_by(TelemetryRecord.timestamp.desc())\
            .limit(limit)\
            .all()

telemetry_service = TelemetryService()
