from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
import logging
from backend.app.models.incidente import Incidente
from backend.app.schemas.incidente import IncidenteCreate, IncidenteUpdate
from backend.app.core.websocket_manager import ws_manager

logger = logging.getLogger("incident_service")

class IncidenteService:
    async def create_incidente(self, db: Session, inc_data: IncidenteCreate) -> Incidente:
        incidente = Incidente(
            drone_id=inc_data.drone_id,
            tipo=inc_data.tipo,
            severidad=inc_data.severidad,
            descripcion=inc_data.descripcion,
            pos_x=inc_data.pos_x,
            pos_y=inc_data.pos_y,
            pos_z=inc_data.pos_z,
            confidence=inc_data.confidence,
            imagen_id=inc_data.imagen_id,
            estado=inc_data.estado,
            timestamp=datetime.utcnow()
        )
        db.add(incidente)
        db.commit()
        db.refresh(incidente)

        # Broadcast critical incident alert via WebSocket
        await ws_manager.broadcast("incident", {
            "id": incidente.id,
            "drone_id": incidente.drone_id,
            "tipo": incidente.tipo,
            "severidad": incidente.severidad,
            "descripcion": incidente.descripcion,
            "pos_x": incidente.pos_x,
            "pos_y": incidente.pos_y,
            "pos_z": incidente.pos_z,
            "confidence": incidente.confidence,
            "imagen_id": incidente.imagen_id,
            "estado": incidente.estado,
            "timestamp": incidente.timestamp.isoformat()
        })

        return incidente

    def list_incidentes(
        self,
        db: Session,
        tipo: Optional[str] = None,
        severidad: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 100
    ) -> List[Incidente]:
        query = db.query(Incidente)
        if tipo:
            query = query.filter(Incidente.tipo == tipo)
        if severidad:
            query = query.filter(Incidente.severidad == severidad)
        if estado:
            query = query.filter(Incidente.estado == estado)
        return query.order_by(Incidente.timestamp.desc()).limit(limit).all()

    def get_by_id(self, db: Session, incidente_id: int) -> Optional[Incidente]:
        return db.query(Incidente).filter(Incidente.id == incidente_id).first()

    def update_incidente(self, db: Session, incidente_id: int, update_data: IncidenteUpdate) -> Optional[Incidente]:
        inc = self.get_by_id(db, incidente_id)
        if not inc:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(inc, key, value)

        db.commit()
        db.refresh(inc)
        return inc

incidente_service = IncidenteService()
