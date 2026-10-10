from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.schemas.telemetria import TelemetryIn, TelemetryResponse
from backend.app.modules.telemetria.service import telemetry_service

router = APIRouter()

@router.post("", response_model=TelemetryResponse)
async def post_telemetry(telemetry: TelemetryIn, db: Session = Depends(get_db)):
    """Ingest real-time flight telemetry from Webots or physical drone."""
    return await telemetry_service.record_telemetry(db, telemetry)

@router.get("/{drone_id}/latest", response_model=TelemetryResponse)
def get_latest_telemetry(drone_id: str, db: Session = Depends(get_db)):
    """Get the most recent telemetry sample for a given drone."""
    latest = telemetry_service.get_latest_telemetry(db, drone_id)
    if not latest:
        raise HTTPException(status_code=404, detail="No hay telemetría registrada para este dron")
    return latest

@router.get("/{drone_id}/history", response_model=List[TelemetryResponse])
def get_telemetry_history(
    drone_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get historical telemetry trail for flight trajectory visualization."""
    return telemetry_service.get_history(db, drone_id, limit=limit)
