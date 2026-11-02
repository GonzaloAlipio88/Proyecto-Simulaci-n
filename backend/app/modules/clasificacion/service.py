import time
import uuid
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from backend.app.schemas.deteccion import DetectionItem, RoadDetectionItem, RoadClassificationBatchResult
from backend.app.modules.clasificacion.rules import (
    ClassificationRules,
    BoundingBoxValidator,
    DeduplicationTracker,
    DEFAULT_CATEGORY_THRESHOLDS,
    TARGET_ROAD_CATEGORIES,
    CATEGORY_POLE,
    CATEGORY_VEGETATION,
    CATEGORY_OBSTACLE,
    CATEGORY_OTHER
)

logger = logging.getLogger("road_classification_service")

class RoadClassificationService:
    """
    Servicio desacoplado de clasificación e interpretación de detecciones de visión artificial (Semana 6).
    
    Responsabilidades:
    1. Recibir resultados en bruto de VisionModel (YOLOv8 / Heurístico / Diagnóstico).
    2. Normalizar categorías a las tres clases objetivo de carretera ('poste_luz', 'vegetacion_invasiva', 'obstruccion_via') u 'otro'.
    3. Aplicar validación geométrica de cajas delimitadoras (BoundingBoxValidator).
    4. Aplicar umbrales de confianza configurables por categoría.
    5. Diferenciar detección visual de incidente vial confirmado (criterio prudencial).
    6. Vincular cada resultado con frame, drone_id y coordenadas métricas de simulación Webots.
    7. Garantizar que la ausencia de ubicación se reporte como None honesto sin inventar coordenadas GPS ni (0,0,0).
    8. Aplicar deduplicación espacio-temporal para evitar alertas repetidas en ráfaga.
    """

    def __init__(self, dedup_window_seconds: float = 5.0, spatial_grid_meters: float = 2.5):
        self.deduplicator = DeduplicationTracker(
            time_window_seconds=dedup_window_seconds,
            spatial_grid_meters=spatial_grid_meters
        )
        self.category_thresholds = dict(DEFAULT_CATEGORY_THRESHOLDS)

    def set_thresholds(self, thresholds: Dict[str, float]):
        """Permite actualizar dinámicamente los umbrales de confianza por categoría."""
        self.category_thresholds.update(thresholds)

    def get_thresholds(self) -> Dict[str, float]:
        """Retorna los umbrales de confianza activos por categoría."""
        return dict(self.category_thresholds)

    def interpret_detection(
        self,
        raw_det: DetectionItem,
        drone_id: str,
        frame_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        pos_x: Optional[float] = None,
        pos_y: Optional[float] = None,
        pos_z: Optional[float] = None,
        image_id: Optional[int] = None,
        image_dims: Optional[Tuple[int, int]] = (640, 480),
        custom_thresholds: Optional[Dict[str, float]] = None
    ) -> RoadDetectionItem:
        """
        Interpreta, valida y califica una detección individual.
        """
        now_utc = timestamp or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        # 1. Normalización de etiqueta y categoría
        raw_label = raw_det.label or raw_det.class_name or "desconocido"
        norm_cat, clean_label = ClassificationRules.normalize_label(raw_label)

        # 2. Representación de ubicación de simulación vs GPS
        simulation_coords = None
        if pos_x is not None and pos_y is not None and pos_z is not None:
            simulation_coords = {
                "pos_x": round(float(pos_x), 3),
                "pos_y": round(float(pos_y), 3),
                "pos_z": round(float(pos_z), 3)
            }

        # 3. Validación de caja delimitadora
        img_w, img_h = image_dims if image_dims else (640, 480)
        bbox_valid, bbox_err = BoundingBoxValidator.validate(raw_det.bbox, img_w, img_h)

        # 4. Umbral de confianza por categoría
        threshold = ClassificationRules.get_threshold(norm_cat, custom_thresholds or self.category_thresholds)
        conf_valid = (raw_det.confidence >= threshold)

        validation_passed = bbox_valid and conf_valid
        rejection_reason = None
        if not bbox_valid:
            rejection_reason = f"Caja delimitadora inválida: {bbox_err}"
        elif not conf_valid:
            rejection_reason = f"Confianza ({raw_det.confidence:.2f}) inferior al umbral de categoría '{norm_cat}' ({threshold:.2f})"

        # 5. Calificación de severidad, estado de revisión e incidente candidato
        qualification = ClassificationRules.qualify_detection(
            normalized_category=norm_cat,
            raw_label=clean_label,
            confidence=raw_det.confidence,
            bbox=raw_det.bbox,
            image_dims=(img_w, img_h),
            simulation_coords=simulation_coords
        )

        is_incident_candidate = qualification["is_incident_candidate"] and validation_passed
        severity = raw_det.severity if raw_det.severity in ["alta", "critica"] and qualification["severity"] != "critica" else qualification["severity"]
        review_status = qualification["review_status"]
        justification = qualification["justification"]

        # 6. Deduplicación espacio-temporal
        is_duplicate = False
        repetition_count = 1
        if validation_passed and is_incident_candidate:
            is_dup, dedup_key, rep_count = self.deduplicator.check_and_record(
                drone_id=drone_id,
                category=norm_cat,
                bbox=raw_det.bbox,
                simulation_coords=simulation_coords,
                now=now_utc
            )
            is_duplicate = is_dup
            repetition_count = rep_count
            if is_duplicate:
                review_status = "pendiente_revision"

        # 7. Construcción de RoadDetectionItem enriquecido
        det_id = str(uuid.uuid4())
        return RoadDetectionItem(
            id=det_id,
            label=norm_cat,
            class_name=norm_cat,
            normalized_category=norm_cat,
            raw_label=clean_label,
            confidence=raw_det.confidence,
            bbox=raw_det.bbox,
            severity=severity,
            review_status=review_status,
            description=raw_det.description or justification,
            frame_id=frame_id or raw_det.frame_id,
            timestamp=now_utc,
            drone_id=drone_id,
            simulation_coords=simulation_coords,
            coordinate_system="simulation_webots_cartesian_meters",
            gps_coords=None, # Documentado explícitamente: GPS ausente en simulación Webots
            image_id=image_id,
            is_incident_candidate=is_incident_candidate,
            incident_id=None,
            validation_passed=validation_passed,
            rejection_reason=rejection_reason,
            is_duplicate=is_duplicate,
            repetition_count=repetition_count,
            justification=justification
        )

    def classify_detections(
        self,
        raw_detections: List[DetectionItem],
        drone_id: str,
        frame_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        pos_x: Optional[float] = None,
        pos_y: Optional[float] = None,
        pos_z: Optional[float] = None,
        image_id: Optional[int] = None,
        image_dims: Optional[Tuple[int, int]] = (640, 480),
        custom_thresholds: Optional[Dict[str, float]] = None
    ) -> RoadClassificationBatchResult:
        """
        Procesa por lote una lista de detecciones de un frame y genera el resultado clasificado.
        """
        start_t = time.perf_counter()
        now_utc = timestamp or datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            now_utc = now_utc.replace(tzinfo=timezone.utc)

        classified: List[RoadDetectionItem] = []
        valid_count = 0
        rejected_count = 0
        incident_candidates_count = 0

        for raw_det in raw_detections:
            item = self.interpret_detection(
                raw_det=raw_det,
                drone_id=drone_id,
                frame_id=frame_id,
                timestamp=now_utc,
                pos_x=pos_x,
                pos_y=pos_y,
                pos_z=pos_z,
                image_id=image_id,
                image_dims=image_dims,
                custom_thresholds=custom_thresholds
            )
            classified.append(item)
            if item.validation_passed:
                valid_count += 1
                if item.is_incident_candidate and not item.is_duplicate:
                    incident_candidates_count += 1
            else:
                rejected_count += 1

        elapsed_ms = (time.perf_counter() - start_t) * 1000.0

        return RoadClassificationBatchResult(
            drone_id=drone_id,
            timestamp=now_utc,
            frame_id=frame_id,
            total_input=len(raw_detections),
            total_valid=valid_count,
            total_rejected=rejected_count,
            total_incidents_qualified=incident_candidates_count,
            detections=classified,
            active_thresholds=dict(custom_thresholds or self.category_thresholds),
            processing_time_ms=round(elapsed_ms, 2)
        )

# Instancia singleton del servicio de clasificación
classification_service = RoadClassificationService()
