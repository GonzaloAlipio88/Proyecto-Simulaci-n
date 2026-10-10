from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from datetime import datetime
from backend.app.core.database import Base

class Incidente(Base):
    __tablename__ = "incidentes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    drone_id = Column(String(50), index=True, nullable=False)
    
    # Classification: 'poste_luz', 'vegetacion_invasiva', 'obstruccion_via'
    tipo = Column(String(50), nullable=False, index=True)
    severidad = Column(String(20), default="media") # baja, media, alta, critica
    descripcion = Column(String(500), nullable=False)
    
    # 3D Coordinates where the incident was detected
    pos_x = Column(Float, nullable=False)
    pos_y = Column(Float, nullable=False)
    pos_z = Column(Float, nullable=False)
    
    # Detection metrics
    confidence = Column(Float, default=0.0)
    
    # Linked image record
    imagen_id = Column(Integer, nullable=True)
    
    # Status lifecycle
    estado = Column(String(30), default="reportado") # reportado, en_revision, atendido, descartado
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
