from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.app.core.database import get_db
from backend.app.schemas.dron import DroneCreate, DroneUpdate, DroneResponse, DroneCommand
from backend.app.modules.drones.service import drone_service

router = APIRouter()

@router.post("", response_model=DroneResponse)
def register_drone(drone: DroneCreate, db: Session = Depends(get_db)):
    """Register or initialize a drone in the system."""
    return drone_service.get_or_create(db, drone)

@router.get("", response_model=List[DroneResponse])
def get_all_drones(db: Session = Depends(get_db)):
    """Retrieve list of all active or registered drones."""
    return drone_service.list_drones(db)

@router.get("/{drone_id}", response_model=DroneResponse)
def get_drone(drone_id: str, db: Session = Depends(get_db)):
    """Get status and details of a specific drone."""
    drone = drone_service.get_drone(db, drone_id)
    if not drone:
        raise HTTPException(status_code=404, detail="Drone no encontrado")
    return drone

@router.post("/{drone_id}/command")
async def send_drone_command(drone_id: str, cmd: DroneCommand, db: Session = Depends(get_db)):
    """Send navigation or operational command to the drone (takeoff, land, hover, etc.)."""
    result = await drone_service.send_command(db, drone_id, cmd)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message"))
    return result
