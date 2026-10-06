from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from datetime import datetime

class DroneBase(BaseModel):
    name: str = "Surveillance-Hexa-01"
    model: str = "DJI Matrice / Webots Quadrotor"
    status: str = "idle"
    battery_level: float = Field(default=100.0, ge=0.0, le=100.0)
    current_x: float = 0.0
    current_y: float = 0.0
    current_z: float = 0.0
    current_speed: float = 0.0
    flight_mode: str = "autonomous"
    current_waypoint: int = 0
    current_mission: str = "Inspeccion_Vias_Demo"

class DroneCreate(DroneBase):
    id: str

class DroneUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    battery_level: Optional[float] = None
    current_x: Optional[float] = None
    current_y: Optional[float] = None
    current_z: Optional[float] = None
    current_speed: Optional[float] = None
    flight_mode: Optional[str] = None
    current_waypoint: Optional[int] = None
    current_mission: Optional[str] = None


class DroneCommand(BaseModel):
    command: Literal["takeoff", "land", "hover", "resume_patrol", "return_to_home", "set_waypoint"]
    params: Optional[dict] = None

class DroneResponse(DroneBase):
    id: str
    last_seen_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

