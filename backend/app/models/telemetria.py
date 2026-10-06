from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from backend.app.core.database import Base

class TelemetryRecord(Base):
    __tablename__ = "telemetria"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    drone_id = Column(String(50), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    # 3D Position
    pos_x = Column(Float, nullable=False)
    pos_y = Column(Float, nullable=False)
    pos_z = Column(Float, nullable=False) # Altitude
    
    # Orientation (degrees or radians)
    roll = Column(Float, default=0.0)
    pitch = Column(Float, default=0.0)
    yaw = Column(Float, default=0.0)
    
    # Dynamics & System
    speed = Column(Float, default=0.0)
    battery = Column(Float, default=100.0)
    flight_mode = Column(String(30), default="autonomous")
    
    # Mission tracking
    current_waypoint = Column(Integer, default=0)
    current_mission = Column(String(100), default="Inspeccion_Vias_Demo")
    state_description = Column(String(200), nullable=True)

