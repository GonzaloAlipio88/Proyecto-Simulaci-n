from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from backend.app.core.database import Base

class Drone(Base):
    __tablename__ = "drones"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False, default="Surveillance-Hexa-01")
    model = Column(String(50), default="DJI Matrice / Webots Quadrotor")
    status = Column(String(30), default="idle")  # idle, arming, flying, hovering, returning, landed, emergency
    battery_level = Column(Float, default=100.0) # 0 - 100%
    current_x = Column(Float, default=0.0)
    current_y = Column(Float, default=0.0)
    current_z = Column(Float, default=0.0)       # altitude
    current_speed = Column(Float, default=0.0)   # m/s
    flight_mode = Column(String(30), default="autonomous") # manual, autonomous, loiter, rtl
    current_waypoint = Column(Integer, default=0)
    current_mission = Column(String(100), default="Inspeccion_Vias_Demo")
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

