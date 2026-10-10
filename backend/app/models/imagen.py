from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
from backend.app.core.database import Base

class ImageRecord(Base):
    __tablename__ = "imagenes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    drone_id = Column(String(50), index=True, nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Position when captured
    pos_x = Column(Float, nullable=True)
    pos_y = Column(Float, nullable=True)
    pos_z = Column(Float, nullable=True)
    
    # Detection metadata
    has_detections = Column(Boolean, default=False)
    detection_count = Column(Integer, default=0)
    annotated_filename = Column(String(255), nullable=True)
