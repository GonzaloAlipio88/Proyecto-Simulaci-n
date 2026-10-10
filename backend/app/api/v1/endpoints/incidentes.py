from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from backend.app.core.database import get_db
from backend.app.schemas.incidente import IncidenteCreate, IncidenteUpdate, IncidenteResponse
from backend.app.modules.incidentes.service import incidente_service

router = APIRouter()

@router.post("", response_model=IncidenteResponse)
async def create_incidente(incidente: IncidenteCreate, db: Session = Depends(get_db)):
    """Register a new detected anomaly or incident."""
    return await incidente_service.create_incidente(db, incidente)

@router.get("", response_model=List[IncidenteResponse])
def get_incidentes(
    tipo: Optional[str] = Query(None, description="Filtro por tipo: poste_luz, vegetacion_invasiva, obstruccion_via"),
    severidad: Optional[str] = Query(None, description="Filtro por severidad: baja, media, alta, critica"),
    estado: Optional[str] = Query(None, description="Filtro por estado: reportado, en_revision, atendido, descartado"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Retrieve list of incidents with optional filters."""
    return incidente_service.list_incidentes(db, tipo=tipo, severidad=severidad, estado=estado, limit=limit)

@router.get("/{incidente_id}", response_model=IncidenteResponse)
def get_incidente(incidente_id: int, db: Session = Depends(get_db)):
    """Get incident details by ID."""
    inc = incidente_service.get_by_id(db, incidente_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return inc

@router.patch("/{incidente_id}", response_model=IncidenteResponse)
def update_incidente(incidente_id: int, update_data: IncidenteUpdate, db: Session = Depends(get_db)):
    """Update state, severity or notes of an incident."""
    updated = incidente_service.update_incidente(db, incidente_id, update_data)
    if not updated:
        raise HTTPException(status_code=404, detail="Incidente no encontrado")
    return updated
