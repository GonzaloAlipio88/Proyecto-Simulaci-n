from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import logging

from backend.app.core.database import get_db
from backend.app.schemas.incidente import (
    IncidenteCreate,
    IncidenteUpdate,
    IncidenteResponse,
    IncidenteStatsResponse,
    IncidenteDeleteResponse
)
from backend.app.modules.incidentes.service import incidente_service
from backend.app.modules.imagenes.service import image_service

logger = logging.getLogger("incidentes_endpoint")
router = APIRouter()

@router.post("", response_model=IncidenteResponse, status_code=status.HTTP_200_OK)
async def create_incidente(
    incidente: IncidenteCreate,
    allow_duplicate: bool = Query(
        default=False,
        description="Permite omitir la regla de deduplicación espacio-temporal (crear siempre un nuevo registro)"
    ),
    db: Session = Depends(get_db)
):
    """
    Registra un nuevo incidente o anomalía en vía en la base de datos SQLite.
    
    Aplica regla de deduplicación automática (5 segundos / 2.5 metros) para prevenir
    múltiples registros idénticos por fotograma. Para forzar la creación independiente,
    use el parámetro allow_duplicate=true.
    """
    try:
        return await incidente_service.create_incidente(db, incidente, allow_duplicate=allow_duplicate)
    except HTTPException:
        raise
    except SQLAlchemyError as ex:
        db.rollback()
        logger.error(f"Error de base de datos creando incidente: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la base de datos al registrar el incidente: {ex}"
        )
    except Exception as ex:
        db.rollback()
        logger.error(f"Error no controlado creando incidente: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno del servidor al procesar el incidente: {ex}"
        )


@router.get("", response_model=List[IncidenteResponse])
def get_incidentes(
    tipo: Optional[str] = Query(None, description="Filtro por tipo: poste_luz, vegetacion_invasiva, obstruccion_via, otro"),
    severidad: Optional[str] = Query(None, description="Filtro por severidad: baja, media, alta, critica"),
    estado: Optional[str] = Query(None, description="Filtro por estado: reportado, en_revision, atendido, descartado"),
    drone_id: Optional[str] = Query(None, description="Filtro por identificador de dron emisor"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Filtro por confianza mínima de detección"),
    has_image: Optional[bool] = Query(None, description="Filtrar por presencia de imagen adjunta (true o false)"),
    start_date: Optional[datetime] = Query(None, description="Fecha y hora mínima en formato ISO 8601"),
    end_date: Optional[datetime] = Query(None, description="Fecha y hora máxima en formato ISO 8601"),
    search: Optional[str] = Query(None, description="Búsqueda de texto en la descripción del incidente"),
    order_by: str = Query(default="desc", pattern="^(asc|desc)$", description="Orden temporal de los resultados ('desc' o 'asc')"),
    skip: int = Query(default=0, ge=0, description="Paginación: cantidad de registros a omitir"),
    limit: int = Query(default=100, ge=1, le=500, description="Paginación: cantidad máxima de registros a devolver"),
    db: Session = Depends(get_db)
):
    """
    Recupera el listado de incidentes registrados en SQLite con filtros combinados,
    búsqueda por texto, paginación y ordenación.
    """
    try:
        return incidente_service.list_incidentes(
            db,
            drone_id=drone_id,
            tipo=tipo,
            severidad=severidad,
            estado=estado,
            min_confidence=min_confidence,
            has_image=has_image,
            start_date=start_date,
            end_date=end_date,
            search=search,
            order_by=order_by,
            skip=skip,
            limit=limit
        )
    except HTTPException:
        raise
    except SQLAlchemyError as ex:
        db.rollback()
        logger.error(f"Error de base de datos listando incidentes: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error consultando incidentes en la base de datos: {ex}"
        )


@router.get("/stats", response_model=IncidenteStatsResponse)
def get_incidente_stats(db: Session = Depends(get_db)):
    """
    Entrega métricas agregadas y estadísticas completas de los incidentes en SQLite:
    totales, distribución por tipo, severidad, estado operativo, cobertura de imágenes y confianza promedio.
    """
    try:
        return incidente_service.get_stats(db)
    except HTTPException:
        raise
    except SQLAlchemyError as ex:
        db.rollback()
        logger.error(f"Error de base de datos calculando estadísticas: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la base de datos calculando estadísticas: {ex}"
        )


@router.get("/{incidente_id}", response_model=IncidenteResponse)
def get_incidente(incidente_id: int, db: Session = Depends(get_db)):
    """
    Recupera los detalles completos de un incidente por su identificador primario.
    """
    try:
        inc = incidente_service.get_by_id(db, incidente_id)
        if not inc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incidente #{incidente_id} no encontrado"
            )
        return inc
    except HTTPException:
        raise
    except SQLAlchemyError as ex:
        db.rollback()
        logger.error(f"Error de base de datos obteniendo incidente #{incidente_id}: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la base de datos al buscar el incidente: {ex}"
        )


@router.get("/{incidente_id}/imagen")
def get_incidente_image(
    incidente_id: int,
    download: bool = Query(default=False, description="Descargar directamente el archivo binario JPG de la imagen"),
    db: Session = Depends(get_db)
):
    """
    Consulta o descarga la fotografía vinculada a un incidente registrado.
    """
    try:
        inc, img_record = incidente_service.get_image_for_incidente(db, incidente_id)
        if not inc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incidente #{incidente_id} no encontrado"
            )
        if not img_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"El incidente #{incidente_id} no tiene una imagen asociada en el registro"
            )

        if download:
            target_filename = img_record.annotated_filename or img_record.filename
            path = image_service.get_image_path(target_filename)
            if not path or not path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"El archivo físico de la imagen '{target_filename}' no está disponible en almacenamiento"
                )
            media_type = "image/png" if target_filename.lower().endswith(".png") else "image/jpeg"
            return FileResponse(path, media_type=media_type, filename=target_filename)

        # Retorna metadata de la imagen asociada
        return {
            "incidente_id": inc.id,
            "image_id": img_record.id,
            "drone_id": img_record.drone_id,
            "filename": img_record.filename,
            "annotated_filename": img_record.annotated_filename,
            "url": f"/api/v1/imagenes/file/{img_record.filename}",
            "annotated_url": f"/api/v1/imagenes/file/{img_record.annotated_filename}" if img_record.annotated_filename else None,
            "captured_at": img_record.captured_at,
            "has_detections": img_record.has_detections,
            "detection_count": img_record.detection_count
        }
    except HTTPException:
        raise
    except SQLAlchemyError as ex:
        db.rollback()
        logger.error(f"Error de base de datos obteniendo imagen de incidente #{incidente_id}: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la base de datos al buscar la imagen del incidente: {ex}"
        )


@router.patch("/{incidente_id}", response_model=IncidenteResponse)
async def update_incidente(
    incidente_id: int,
    update_data: IncidenteUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza el estado operativo ('reportado', 'en_revision', 'atendido', 'descartado'),
    la severidad o las notas de un incidente existente.
    """
    try:
        updated = await incidente_service.update_incidente(db, incidente_id, update_data)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incidente #{incidente_id} no encontrado"
            )
        return updated
    except HTTPException:
        raise
    except SQLAlchemyError as ex:
        db.rollback()
        logger.error(f"Error de base de datos actualizando incidente #{incidente_id}: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la base de datos al actualizar el incidente: {ex}"
        )


@router.delete("/{incidente_id}", response_model=IncidenteDeleteResponse)
async def delete_incidente(incidente_id: int, db: Session = Depends(get_db)):
    """
    Elimina permanentemente un incidente de la base de datos SQLite por su ID.
    """
    try:
        deleted = await incidente_service.delete_incidente(db, incidente_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Incidente #{incidente_id} no encontrado"
            )
        return IncidenteDeleteResponse(
            success=True,
            message=f"Incidente #{incidente_id} eliminado exitosamente",
            id=incidente_id
        )
    except HTTPException:
        raise
    except SQLAlchemyError as ex:
        db.rollback()
        logger.error(f"Error de base de datos eliminando incidente #{incidente_id}: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la base de datos al eliminar el incidente: {ex}"
        )
