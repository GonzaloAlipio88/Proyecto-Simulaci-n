import math
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status

from backend.app.models.incidente import Incidente
from backend.app.models.imagen import ImageRecord
from backend.app.schemas.incidente import IncidenteCreate, IncidenteUpdate, IncidenteStatsResponse
from backend.app.core.websocket_manager import ws_manager

logger = logging.getLogger("incident_service")


class IncidenteService:
    """
    Servicio de gestión y persistencia de incidentes en base de datos SQLite (Semana 8).
    
    Responsabilidades:
    1. Registro seguro de incidentes y anomalías viales calificadas.
    2. Deduplicación espacio-temporal para evitar saturación de la base de datos.
    3. Consultas flexibles con filtros múltiples (tipo, severidad, estado, drone, confianza, imagen, rango de fechas).
    4. Ciclo de vida completo (crear, consultar, actualizar estado/severidad, eliminar).
    5. Métricas y estadísticas agregadas para dashboard de control.
    6. Gestión tolerante a fallos de base de datos con rollback automático.
    7. Difusión en tiempo real mediante WebSocket conservando contratos existentes.
    """

    async def create_incidente(
        self,
        db: Session,
        inc_data: IncidenteCreate,
        allow_duplicate: bool = False,
        dedup_window_seconds: float = 5.0,
        dedup_distance_meters: float = 2.5
    ) -> Incidente:
        """
        Registra un incidente en SQLite aplicando regla de deduplicación opcional.
        Si ya existe un incidente reciente con el mismo dron y tipo en la misma vecindad espacial,
        se reutiliza y actualiza en lugar de insertar un registro redundante.
        """
        # Determinar timestamp efectivo en UTC
        now_utc = datetime.now(timezone.utc)
        if inc_data.timestamp:
            target_ts = inc_data.timestamp
            if target_ts.tzinfo is None:
                target_ts = target_ts.replace(tzinfo=timezone.utc)
        else:
            target_ts = now_utc

        # 1. Deduplicación espacio-temporal (si allow_duplicate es False)
        if not allow_duplicate:
            cutoff = target_ts - timedelta(seconds=dedup_window_seconds)
            # En SQLite los datetimes suelen persistirse sin tzinfo
            cutoff_naive = cutoff.replace(tzinfo=None)
            target_naive = target_ts.replace(tzinfo=None)

            try:
                candidates = db.query(Incidente).filter(
                    Incidente.drone_id == inc_data.drone_id,
                    Incidente.tipo == inc_data.tipo,
                    Incidente.timestamp >= cutoff_naive
                ).order_by(Incidente.timestamp.desc()).all()

                for cand in candidates:
                    is_dup = False
                    # Comprobación espacial si hay coordenadas en ambos
                    if (
                        inc_data.pos_x is not None and inc_data.pos_y is not None
                        and cand.pos_x is not None and cand.pos_y is not None
                    ):
                        dx = inc_data.pos_x - cand.pos_x
                        dy = inc_data.pos_y - cand.pos_y
                        distance = math.sqrt(dx * dx + dy * dy)
                        if distance <= dedup_distance_meters:
                            is_dup = True
                    elif inc_data.pos_x is None or cand.pos_x is None:
                        # Si no hay coordenadas de ubicación, la coincidencia temporal y tipo basta
                        is_dup = True

                    if is_dup:
                        logger.info(
                            f"Deduplicación activa: incidente #{cand.id} reutilizado "
                            f"(drone='{inc_data.drone_id}', tipo='{inc_data.tipo}', repetición prevenida)"
                        )
                        # Actualizar confianza si la nueva detección tiene mayor certeza
                        if inc_data.confidence > cand.confidence:
                            cand.confidence = inc_data.confidence
                        # Actualizar timestamp al evento más reciente
                        cand.timestamp = target_naive
                        db.commit()
                        db.refresh(cand)
                        return cand

            except SQLAlchemyError as err:
                db.rollback()
                logger.warning(f"Error consultando duplicados en SQLite (continuando con inserción normal): {err}")

        # 2. Inserción normal de nuevo incidente
        target_naive = target_ts.replace(tzinfo=None)
        incidente = Incidente(
            drone_id=inc_data.drone_id,
            tipo=inc_data.tipo,
            severidad=inc_data.severidad,
            descripcion=inc_data.descripcion,
            pos_x=inc_data.pos_x,
            pos_y=inc_data.pos_y,
            pos_z=inc_data.pos_z,
            coordenadas_tipo=inc_data.coordenadas_tipo or "simulacion_webots",
            confidence=inc_data.confidence,
            imagen_id=inc_data.imagen_id,
            estado=inc_data.estado,
            timestamp=target_naive
        )

        try:
            db.add(incidente)
            db.commit()
            db.refresh(incidente)
        except SQLAlchemyError as ex:
            db.rollback()
            logger.error(f"Error de base de datos SQLite al crear incidente: {ex}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en la base de datos SQLite al registrar el incidente: {str(ex)}"
            )

        # 3. Notificación en tiempo real vía WebSocket
        try:
            ts_iso = incidente.timestamp.isoformat() if hasattr(incidente.timestamp, "isoformat") else str(incidente.timestamp)
            await ws_manager.broadcast("incident", {
                "id": incidente.id,
                "drone_id": incidente.drone_id,
                "tipo": incidente.tipo,
                "severidad": incidente.severidad,
                "descripcion": incidente.descripcion,
                "pos_x": incidente.pos_x,
                "pos_y": incidente.pos_y,
                "pos_z": incidente.pos_z,
                "coordenadas_tipo": getattr(incidente, "coordenadas_tipo", "simulacion_webots"),
                "confidence": incidente.confidence,
                "imagen_id": incidente.imagen_id,
                "imagen_url": incidente.imagen_url,
                "estado": incidente.estado,
                "timestamp": ts_iso
            })
        except Exception as ws_ex:
            logger.warning(f"Advertencia WebSocket broadcast incidente #{incidente.id}: {ws_ex}")

        return incidente

    def list_incidentes(
        self,
        db: Session,
        drone_id: Optional[str] = None,
        tipo: Optional[str] = None,
        severidad: Optional[str] = None,
        estado: Optional[str] = None,
        min_confidence: Optional[float] = None,
        has_image: Optional[bool] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        search: Optional[str] = None,
        order_by: str = "desc",
        skip: int = 0,
        limit: int = 100
    ) -> List[Incidente]:
        """
        Recupera incidentes con filtros opcionales de negocio, paginación y ordenación.
        """
        try:
            query = db.query(Incidente)

            if drone_id:
                query = query.filter(Incidente.drone_id == drone_id.strip())
            if tipo:
                query = query.filter(Incidente.tipo == tipo.strip())
            if severidad:
                query = query.filter(Incidente.severidad == severidad.strip())
            if estado:
                query = query.filter(Incidente.estado == estado.strip())
            if min_confidence is not None:
                query = query.filter(Incidente.confidence >= float(min_confidence))
            if has_image is True:
                query = query.filter(Incidente.imagen_id.isnot(None))
            elif has_image is False:
                query = query.filter(Incidente.imagen_id.is_(None))
            if start_date is not None:
                st_naive = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
                query = query.filter(Incidente.timestamp >= st_naive)
            if end_date is not None:
                et_naive = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
                query = query.filter(Incidente.timestamp <= et_naive)
            if search:
                query = query.filter(Incidente.descripcion.ilike(f"%{search.strip()}%"))

            # Ordenación por timestamp
            if order_by.lower() == "asc":
                query = query.order_by(Incidente.timestamp.asc(), Incidente.id.asc())
            else:
                query = query.order_by(Incidente.timestamp.desc(), Incidente.id.desc())

            return query.offset(skip).limit(limit).all()

        except SQLAlchemyError as ex:
            db.rollback()
            logger.error(f"Error consultando incidentes en SQLite: {ex}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error consultando incidentes en la base de datos: {str(ex)}"
            )

    def get_by_id(self, db: Session, incidente_id: int) -> Optional[Incidente]:
        """Recupera un incidente por su identificador primario."""
        try:
            return db.query(Incidente).filter(Incidente.id == incidente_id).first()
        except SQLAlchemyError as ex:
            db.rollback()
            logger.error(f"Error consultando incidente #{incidente_id} en SQLite: {ex}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en la base de datos al buscar el incidente: {str(ex)}"
            )

    async def update_incidente(
        self,
        db: Session,
        incidente_id: int,
        update_data: IncidenteUpdate
    ) -> Optional[Incidente]:
        """Actualiza estado operativo, severidad o descripción de un incidente."""
        inc = self.get_by_id(db, incidente_id)
        if not inc:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(inc, key, value)

        try:
            db.commit()
            db.refresh(inc)
        except SQLAlchemyError as ex:
            db.rollback()
            logger.error(f"Error actualizando incidente #{incidente_id} en SQLite: {ex}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en la base de datos al actualizar el incidente: {str(ex)}"
            )

        # Notificar actualización por WebSocket
        try:
            ts_iso = inc.timestamp.isoformat() if hasattr(inc.timestamp, "isoformat") else str(inc.timestamp)
            await ws_manager.broadcast("incident_updated", {
                "id": inc.id,
                "drone_id": inc.drone_id,
                "tipo": inc.tipo,
                "severidad": inc.severidad,
                "descripcion": inc.descripcion,
                "pos_x": inc.pos_x,
                "pos_y": inc.pos_y,
                "pos_z": inc.pos_z,
                "coordenadas_tipo": getattr(inc, "coordenadas_tipo", "simulacion_webots"),
                "confidence": inc.confidence,
                "imagen_id": inc.imagen_id,
                "imagen_url": inc.imagen_url,
                "estado": inc.estado,
                "timestamp": ts_iso
            })
        except Exception as ws_ex:
            logger.warning(f"Advertencia WebSocket broadcast incidente actualizado #{inc.id}: {ws_ex}")

        return inc

    async def delete_incidente(self, db: Session, incidente_id: int) -> bool:
        """Elimina un incidente por su ID."""
        inc = self.get_by_id(db, incidente_id)
        if not inc:
            return False

        try:
            db.delete(inc)
            db.commit()
        except SQLAlchemyError as ex:
            db.rollback()
            logger.error(f"Error eliminando incidente #{incidente_id} en SQLite: {ex}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error en la base de datos al eliminar el incidente: {str(ex)}"
            )

        # Notificar eliminación por WebSocket
        try:
            await ws_manager.broadcast("incident_deleted", {
                "id": incidente_id,
                "message": f"Incidente #{incidente_id} eliminado"
            })
        except Exception as ws_ex:
            logger.warning(f"Advertencia WebSocket broadcast eliminación #{incidente_id}: {ws_ex}")

        return True

    def get_stats(self, db: Session) -> IncidenteStatsResponse:
        """Calcula métricas agregadas y estadísticas de incidentes almacenados en SQLite."""
        try:
            total = db.query(func.count(Incidente.id)).scalar() or 0

            # Agrupación por tipo
            tipo_rows = db.query(Incidente.tipo, func.count(Incidente.id)).group_by(Incidente.tipo).all()
            por_tipo = {t: count for t, count in tipo_rows}

            # Agrupación por severidad
            sev_rows = db.query(Incidente.severidad, func.count(Incidente.id)).group_by(Incidente.severidad).all()
            por_severidad = {s: count for s, count in sev_rows}

            # Agrupación por estado
            est_rows = db.query(Incidente.estado, func.count(Incidente.id)).group_by(Incidente.estado).all()
            por_estado = {e: count for e, count in est_rows}

            # Métricas de imagen
            con_imagen = db.query(func.count(Incidente.id)).filter(Incidente.imagen_id.isnot(None)).scalar() or 0
            sin_imagen = total - con_imagen

            # Promedio de confianza
            avg_conf = db.query(func.avg(Incidente.confidence)).scalar() or 0.0

            # Último incidente
            ultimo_ts = db.query(func.max(Incidente.timestamp)).scalar()

            return IncidenteStatsResponse(
                total_incidentes=total,
                por_tipo=por_tipo,
                por_severidad=por_severidad,
                por_estado=por_estado,
                con_imagen=con_imagen,
                sin_imagen=sin_imagen,
                confianza_promedio=round(float(avg_conf), 4),
                ultimo_incidente_timestamp=ultimo_ts
            )

        except SQLAlchemyError as ex:
            db.rollback()
            logger.error(f"Error calculando estadísticas en SQLite: {ex}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error consultando estadísticas en SQLite: {str(ex)}"
            )

    def get_image_for_incidente(self, db: Session, incidente_id: int) -> Tuple[Optional[Incidente], Optional[ImageRecord]]:
        """Devuelve el incidente y el registro de imagen ImageRecord asociado, si existe."""
        inc = self.get_by_id(db, incidente_id)
        if not inc:
            return None, None
        if not inc.imagen_id:
            return inc, None

        img_record = db.query(ImageRecord).filter(ImageRecord.id == inc.imagen_id).first()
        return inc, img_record


incidente_service = IncidenteService()
