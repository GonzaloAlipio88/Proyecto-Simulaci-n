from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

class TelemetryIn(BaseModel):
    drone_id: str
    pos_x: float
    pos_y: float
    pos_z: float # Altitude
    roll: float = 0.0
    pitch: float = 0.0
    yaw: float = 0.0
    speed: float = 0.0
    battery: float = Field(default=100.0, ge=0.0, le=100.0)
    flight_mode: str = "autonomous"
    current_waypoint: int = 0
    current_mission: str = "Inspeccion_Vias_Demo"
    state_description: Optional[str] = None


class TelemetryResponse(TelemetryIn):
    id: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

