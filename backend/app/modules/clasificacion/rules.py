import math
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime, timezone
from backend.app.schemas.deteccion import BoundingBox

logger = logging.getLogger("classification_rules")

# ==============================================================================
# 1. CATEGORÍAS OBJETIVO Y UMBRALES CONFIGURABLES
# ==============================================================================

CATEGORY_POLE = "poste_luz"
CATEGORY_VEGETATION = "vegetacion_invasiva"
CATEGORY_OBSTACLE = "obstruccion_via"
CATEGORY_OTHER = "otro"

TARGET_ROAD_CATEGORIES = [
    CATEGORY_POLE,
    CATEGORY_VEGETATION,
    CATEGORY_OBSTACLE,
    CATEGORY_OTHER
]

DEFAULT_CATEGORY_THRESHOLDS: Dict[str, float] = {
    CATEGORY_POLE: 0.45,         # Infraestructura fija
    CATEGORY_VEGETATION: 0.55,   # Requiere evidencia suficiente antes de alertar invasión
    CATEGORY_OBSTACLE: 0.50,     # Seguridad vial prioritaria
    CATEGORY_OTHER: 0.60         # Clases genéricas desconocidas
}

# Mapeo exhaustivo de sinónimos y etiquetas comunes a categorías normalizadas
RAW_LABEL_MAPPING: Dict[str, str] = {
    # Postes de luz / infraestructura
    "poste_luz": CATEGORY_POLE,
    "poste": CATEGORY_POLE,
    "post": CATEGORY_POLE,
    "pole": CATEGORY_POLE,
    "light pole": CATEGORY_POLE,
    "light_pole": CATEGORY_POLE,
    "street light": CATEGORY_POLE,
    "street_light": CATEGORY_POLE,
    "columna": CATEGORY_POLE,
    "columna_electrica": CATEGORY_POLE,
    "catenary_pole": CATEGORY_POLE,
    "traffic light": CATEGORY_POLE,

    # Vegetación
    "vegetacion_invasiva": CATEGORY_VEGETATION,
    "vegetacion": CATEGORY_VEGETATION,
    "maleza": CATEGORY_VEGETATION,
    "maleza_invasiva": CATEGORY_VEGETATION,
    "tree": CATEGORY_VEGETATION,
    "bush": CATEGORY_VEGETATION,
    "plant": CATEGORY_VEGETATION,
    "potted plant": CATEGORY_VEGETATION,
    "arbol": CATEGORY_VEGETATION,
    "ramas": CATEGORY_VEGETATION,
    "arbusto": CATEGORY_VEGETATION,

    # Obstáculos / obstrucción de vía
    "obstruccion_via": CATEGORY_OBSTACLE,
    "obstaculo": CATEGORY_OBSTACLE,
    "obstruction": CATEGORY_OBSTACLE,
    "road_obstruction": CATEGORY_OBSTACLE,
    "debris": CATEGORY_OBSTACLE,
    "escombro": CATEGORY_OBSTACLE,
    "escombros": CATEGORY_OBSTACLE,
    "roca": CATEGORY_OBSTACLE,
    "rock": CATEGORY_OBSTACLE,
    "boulder": CATEGORY_OBSTACLE,
    "caja": CATEGORY_OBSTACLE,
    "box": CATEGORY_OBSTACLE,
    "bloqueo": CATEGORY_OBSTACLE,
    "bloqueo_via": CATEGORY_OBSTACLE,
    
    # Objetos COCO que pueden constituir obstrucción o peligro en vía
    "car": CATEGORY_OBSTACLE,
    "truck": CATEGORY_OBSTACLE,
    "bus": CATEGORY_OBSTACLE,
    "train": CATEGORY_OBSTACLE,
    "motorcycle": CATEGORY_OBSTACLE,
    "bicycle": CATEGORY_OBSTACLE,
    "person": CATEGORY_OBSTACLE,
    "bench": CATEGORY_OBSTACLE,
    "suitcase": CATEGORY_OBSTACLE,
    "stop sign": CATEGORY_OBSTACLE
}


# ==============================================================================
# 2. VALIDACIÓN GEOMÉTRICA DE CAJAS DELIMITADORAS (BOUNDING BOXES)
# ==============================================================================

class BoundingBoxValidator:
    """
    Validador estricto de geometría de cajas delimitadoras.
    Rechaza cajas invertidas, de área cero, coordenadas negativas graves o valores NaN.
    """

    MIN_BOX_DIMENSION = 2.0  # Mínimo ancho/alto en píxeles
    MIN_BOX_AREA = 4.0       # Mínima área en px²

    @classmethod
    def validate(
        cls,
        bbox: Optional[BoundingBox],
        image_width: Optional[int] = None,
        image_height: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        if bbox is None:
            return False, "Caja delimitadora ausente o nula"

        # 1. Comprobar valores NaN o infinitos
        for val, name in [
            (bbox.x_min, "x_min"), (bbox.y_min, "y_min"),
            (bbox.x_max, "x_max"), (bbox.y_max, "y_max")
        ]:
            if val is None or math.isnan(val) or math.isinf(val):
                return False, f"Coordenada {name} inválida (NaN o Inf)"

        # 2. Comprobar que no sean significativamente negativas
        if bbox.x_min < -1.0 or bbox.y_min < -1.0:
            return False, f"Coordenadas negativas fuera de rango ([{bbox.x_min}, {bbox.y_min}])"

        # 3. Comprobar orientación geométrica (min < max)
        if bbox.x_min >= bbox.x_max:
            return False, f"Inversión horizontal: x_min ({bbox.x_min}) >= x_max ({bbox.x_max})"
        if bbox.y_min >= bbox.y_max:
            return False, f"Inversión vertical: y_min ({bbox.y_min}) >= y_max ({bbox.y_max})"

        width = bbox.x_max - bbox.x_min
        height = bbox.y_max - bbox.y_min
        area = width * height

        # 4. Dimensiones mínimas
        if width < cls.MIN_BOX_DIMENSION or height < cls.MIN_BOX_DIMENSION:
            return False, f"Caja degenerada o de tamaño insuficiente ({width:.1f}x{height:.1f} px)"

        if area < cls.MIN_BOX_AREA:
            return False, f"Área de caja insignificante ({area:.1f} px²)"

        # 5. Comprobar límites de imagen si están disponibles
        if image_width is not None and image_width > 0:
            if bbox.x_min >= image_width or bbox.x_max < 0:
                return False, f"Caja completamente fuera de los límites horizontales (imagen={image_width}px)"
        if image_height is not None and image_height > 0:
            if bbox.y_min >= image_height or bbox.y_max < 0:
                return False, f"Caja completamente fuera de los límites verticales (imagen={image_height}px)"

        return True, None


# ==============================================================================
# 3. NORMALIZACIÓN Y REGLAS DE CALIFICACIÓN DE INCIDENTES
# ==============================================================================

class ClassificationRules:
    """
    Reglas de negocio e interpretación de detecciones de visión artificial:
    - Normalización de etiquetas del modelo a las tres categorías o 'otro'.
    - Umbrales por categoría.
    - Criterios prudentes: no toda vegetación es invasiva ni todo objeto es obstáculo.
    - Determinación de severidad justificada.
    - Calificación de incidente vs detección visual pura.
    """

    @classmethod
    def normalize_label(cls, raw_label: Optional[str]) -> Tuple[str, str]:
        """
        Devuelve (categoría_normalizada, etiqueta_limpia).
        No provoca excepciones ante etiquetas desconocidas.
        """
        if not raw_label or not isinstance(raw_label, str):
            return CATEGORY_OTHER, "desconocido"

        clean = raw_label.strip().lower()
        # Normalizar espacios/guiones
        norm_key = clean.replace("-", "_").replace("  ", " ")

        if norm_key in RAW_LABEL_MAPPING:
            return RAW_LABEL_MAPPING[norm_key], clean

        # Buscar por palabras clave parciales
        if any(w in norm_key for w in ["pole", "poste", "columna"]):
            return CATEGORY_POLE, clean
        if any(w in norm_key for w in ["veg", "tree", "arbol", "maleza", "bush", "rama"]):
            return CATEGORY_VEGETATION, clean
        if any(w in norm_key for w in ["obs", "obst", "block", "roca", "escombro", "car", "vehic"]):
            return CATEGORY_OBSTACLE, clean

        return CATEGORY_OTHER, clean

    @classmethod
    def get_threshold(cls, category: str, custom_thresholds: Optional[Dict[str, float]] = None) -> float:
        thresholds = custom_thresholds or DEFAULT_CATEGORY_THRESHOLDS
        return thresholds.get(category, thresholds.get(CATEGORY_OTHER, 0.50))

    @classmethod
    def qualify_detection(
        cls,
        normalized_category: str,
        raw_label: str,
        confidence: float,
        bbox: BoundingBox,
        image_dims: Optional[Tuple[int, int]] = (640, 480),
        simulation_coords: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Aplica reglas de negocio para evaluar:
        - Si la detección pasa el umbral de su categoría.
        - Severidad estimada ('baja', 'media', 'alta', 'critica').
        - Estado de revisión ('reportado', 'pendiente_revision', 'confirmado', 'descartado').
        - Si califica como incidente formal de vía o permanece como detección visual.
        - Justificación de la decisión (explicabilidad).
        """
        img_w, img_h = image_dims if image_dims else (640, 480)
        box_w = bbox.x_max - bbox.x_min
        box_h = bbox.y_max - bbox.y_min
        box_area = box_w * box_h
        total_img_area = max(1, img_w * img_h)
        area_ratio = box_area / total_img_area

        # Centro horizontal de la caja
        box_center_x = (bbox.x_min + bbox.x_max) / 2.0
        # Zona central de la calzada (30% a 70% del ancho)
        is_in_road_center = (0.25 * img_w) <= box_center_x <= (0.75 * img_w)

        # ----------------------------------------------------------------------
        # Categoría: POSTE DE LUZ (Infraestructura vial)
        # ----------------------------------------------------------------------
        if normalized_category == CATEGORY_POLE:
            # Los postes son infraestructura esperada; severidad baja salvo evidencia de daño
            severity = "baja"
            review_status = "reportado"
            is_incident = False # Un poste normal es un activo registrado, no una emergencia
            justification = f"Poste/columna detectado ({confidence*100:.1f}% conf). Activo de infraestructura."

        # ----------------------------------------------------------------------
        # Categoría: VEGETACIÓN (Regla de invasión real vs vegetación lateral)
        # ----------------------------------------------------------------------
        elif normalized_category == CATEGORY_VEGETATION:
            # Distinción estricta: sólo es 'invasiva' si invade la franja central o tiene gran extensión
            if area_ratio > 0.05 and is_in_road_center:
                severity = "alta" if area_ratio > 0.10 else "media"
                review_status = "reportado"
                is_incident = True
                justification = (
                    f"Vegetación invasiva ocupando franja de vía ({area_ratio*100:.1f}% del encuadre). "
                    "Posible invasión de gálibo."
                )
            elif is_in_road_center:
                severity = "media"
                review_status = "pendiente_revision"
                is_incident = True
                justification = (
                    f"Vegetación detectada en eje de tránsito ({raw_label}). "
                    "Pendiente de confirmación de invasión de calzada."
                )
            else:
                # Vegetación en márgenes naturales (no invasiva)
                severity = "baja"
                review_status = "pendiente_revision"
                is_incident = False
                justification = f"Vegetación lateral/circundante ({raw_label}). No invade la calzada principal."

        # ----------------------------------------------------------------------
        # Categoría: OBSTRUCCIÓN DE VÍA
        # ----------------------------------------------------------------------
        elif normalized_category == CATEGORY_OBSTACLE:
            # Si el objeto está en la zona central de la vía representa un obstáculo directo
            if is_in_road_center:
                if raw_label in ["person", "persona", "peaton"]:
                    severity = "critica"
                    review_status = "reportado"
                    is_incident = True
                    justification = f"Presencia crítica de persona en zona de vía (conf: {confidence*100:.1f}%)"
                elif raw_label in ["car", "truck", "bus", "train", "motorcycle"]:
                    severity = "alta"
                    review_status = "reportado"
                    is_incident = True
                    justification = f"Vehículo ({raw_label}) sobre la vía férrea/calzada (conf: {confidence*100:.1f}%)"
                elif area_ratio > 0.02:
                    severity = "alta"
                    review_status = "reportado"
                    is_incident = True
                    justification = f"Obstáculo significativo ({raw_label}) bloqueando circulación"
                else:
                    severity = "media"
                    review_status = "pendiente_revision"
                    is_incident = True
                    justification = f"Objeto pequeño en vía ({raw_label}). Pendiente de confirmación."
            else:
                # Objeto periférico: clasificación prudente
                severity = "baja"
                review_status = "pendiente_revision"
                is_incident = False
                justification = f"Objeto periférico ({raw_label}) fuera del gálibo activo."

        # ----------------------------------------------------------------------
        # Categoría: OTRO / DESCONOCIDO
        # ----------------------------------------------------------------------
        else:
            if confidence >= 0.75 and is_in_road_center:
                severity = "media"
                review_status = "pendiente_revision"
                is_incident = True
                justification = f"Anomalía no catalogada ({raw_label}) en zona de vía. Requiere revisión técnica."
            else:
                severity = "baja"
                review_status = "pendiente_revision"
                is_incident = False
                justification = f"Detección no crítica de clase desconocida ({raw_label})."

        return {
            "severity": severity,
            "review_status": review_status,
            "is_incident_candidate": is_incident,
            "justification": justification,
            "is_in_road_center": is_in_road_center,
            "area_ratio": round(area_ratio, 4)
        }


# ==============================================================================
# 4. RASTREADOR Y DEDUPLICACIÓN ESPACIO-TEMPORAL
# ==============================================================================

class DeduplicationTracker:
    """
    Previene la creación masiva y redundante de incidentes/alertas
    cuando el dron sobrevuela o inspecciona el mismo elemento en fotogramas sucesivos.

    Clave de deduplicación:
    - Espacial: celda de rejilla de 2.0 m (si hay coordenadas de simulación)
    - O visual: cuantización del centro de la BBox (si no hay coordenadas)
    - Temporal: ventana configurable (por defecto 5.0 segundos).
    """

    def __init__(self, time_window_seconds: float = 5.0, spatial_grid_meters: float = 2.0):
        self.time_window_seconds = time_window_seconds
        self.spatial_grid_meters = spatial_grid_meters
        # key -> {"first_seen": datetime, "last_seen": datetime, "count": int, "record_id": Any}
        self._cache: Dict[str, Dict[str, Any]] = {}

    def _generate_key(
        self,
        drone_id: str,
        category: str,
        simulation_coords: Optional[Dict[str, float]],
        bbox: BoundingBox
    ) -> str:
        cat_key = category.lower()
        if simulation_coords and "pos_x" in simulation_coords and "pos_y" in simulation_coords:
            gx = round(simulation_coords["pos_x"] / self.spatial_grid_meters)
            gy = round(simulation_coords["pos_y"] / self.spatial_grid_meters)
            return f"spatial_{drone_id}_{cat_key}_{gx}_{gy}"
        else:
            # Cuantización de centro de bbox a resolución de 60 px
            cx = int((bbox.x_min + bbox.x_max) / 120.0)
            cy = int((bbox.y_min + bbox.y_max) / 120.0)
            return f"visual_{drone_id}_{cat_key}_{cx}_{cy}"

    def check_and_record(
        self,
        drone_id: str,
        category: str,
        bbox: BoundingBox,
        simulation_coords: Optional[Dict[str, float]] = None,
        now: Optional[datetime] = None,
        record_id: Optional[Any] = None
    ) -> Tuple[bool, Optional[str], int]:
        """
        Retorna:
        (is_duplicate: bool, dedup_key: str, repetition_count: int)
        """
        current_time = now or datetime.now(timezone.utc)
        key = self._generate_key(drone_id, category, simulation_coords, bbox)

        self._cleanup_stale_entries(current_time)

        if key in self._cache:
            entry = self._cache[key]
            elapsed = (current_time - entry["last_seen"]).total_seconds()
            if elapsed < self.time_window_seconds:
                entry["last_seen"] = current_time
                entry["count"] += 1
                return True, key, entry["count"]

        # Nuevo evento único
        self._cache[key] = {
            "first_seen": current_time,
            "last_seen": current_time,
            "count": 1,
            "record_id": record_id
        }
        return False, key, 1

    def _cleanup_stale_entries(self, current_time: datetime, max_age_seconds: float = 60.0):
        stale_keys = [
            k for k, v in self._cache.items()
            if (current_time - v["last_seen"]).total_seconds() > max_age_seconds
        ]
        for k in stale_keys:
            del self._cache[k]

    def reset(self):
        self._cache.clear()
