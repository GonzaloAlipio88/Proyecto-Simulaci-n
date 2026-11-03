import sys
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from datetime import datetime
from backend.app.core.database import Base

sys.modules["backend.app.models.incidente"] = sys.modules[__name__]
sys.modules["app.models.incidente"] = sys.modules[__name__]

class Incidente(Base):
    __tablename__ = "incidentes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    drone_id = Column(String(50), index=True, nullable=False)
    
    # Classification: 'poste_luz', 'vegetacion_invasiva', 'obstruccion_via'
    tipo = Column(String(50), nullable=False, index=True)
    severidad = Column(String(20), default="media") # baja, media, alta, critica
    descripcion = Column(String(500), nullable=False)
    
    # 3D Coordinates where the incident was detected (simulation Webots cartesian meters, or null if unknown)
    pos_x = Column(Float, nullable=True)
    pos_y = Column(Float, nullable=True)
    pos_z = Column(Float, nullable=True)
    coordenadas_tipo = Column(String(50), default="simulacion_webots", nullable=True)
    
    # Detection metrics
    confidence = Column(Float, default=0.0)
    
    # Linked image record
    imagen_id = Column(Integer, nullable=True)
    
    # Status lifecycle
    estado = Column(String(30), default="reportado") # reportado, en_revision, atendido, descartado
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    @property
    def imagen_url(self) -> str | None:
        """Returns direct API route to fetch linked image, if available."""
        if self.imagen_id is not None:
            return f"/api/v1/imagenes/{self.imagen_id}"
        return None

    def __repr__(self) -> str:
        return f"<Incidente id={self.id} drone={self.drone_id} tipo={self.tipo} severidad={self.severidad} estado={self.estado}>"
