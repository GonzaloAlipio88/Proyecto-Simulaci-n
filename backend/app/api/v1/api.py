from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    drones,
    telemetria,
    cameras,
    deteccion,
    imagenes,
    incidentes
)

api_router = APIRouter()

api_router.include_router(drones.router, prefix="/drones", tags=["Drones"])
api_router.include_router(telemetria.router, prefix="/telemetria", tags=["Telemetría"])
api_router.include_router(cameras.router, prefix="/cameras", tags=["Cámaras"])
api_router.include_router(deteccion.router, prefix="/deteccion", tags=["Detección Visión Artificial"])
api_router.include_router(imagenes.router, prefix="/imagenes", tags=["Imágenes"])
api_router.include_router(incidentes.router, prefix="/incidentes", tags=["Incidentes"])
