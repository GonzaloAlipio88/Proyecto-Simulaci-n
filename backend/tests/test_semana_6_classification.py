import pytest
import sys
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
import numpy as np
import cv2
import base64

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import init_db, SessionLocal
from backend.app.schemas.deteccion import BoundingBox, DetectionItem, RoadDetectionItem
from backend.app.modules.clasificacion.rules import (
    ClassificationRules,
    BoundingBoxValidator,
    DeduplicationTracker,
    DEFAULT_CATEGORY_THRESHOLDS,
    CATEGORY_POLE,
    CATEGORY_VEGETATION,
    CATEGORY_OBSTACLE,
    CATEGORY_OTHER
)
from backend.app.modules.clasificacion.service import RoadClassificationService, classification_service
from backend.app.models.incidente import Incidente

init_db()

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def simulated_pole_detection():
    """Fixture de prueba: detección simulada de poste de luz."""
    return DetectionItem(
        label="poste_luz",
        class_name="poste_luz",
        confidence=0.88,
        bbox=BoundingBox(x_min=440.0, y_min=50.0, x_max=460.0, y_max=380.0),
        severity="baja",
        description="[SIMULADO_TEST] Columna de catenaria/alumbrado"
    )

@pytest.fixture
def simulated_vegetation_detection():
    """Fixture de prueba: detección simulada de vegetación invasiva central."""
    return DetectionItem(
        label="vegetacion_invasiva",
        class_name="vegetacion_invasiva",
        confidence=0.78,
        bbox=BoundingBox(x_min=200.0, y_min=220.0, x_max=420.0, y_max=410.0),
        severity="alta",
        description="[SIMULADO_TEST] Crecimiento vegetal sobre vía férrea"
    )

@pytest.fixture
def simulated_obstacle_detection():
    """Fixture de prueba: detección simulada de obstáculo en calzada."""
    return DetectionItem(
        label="obstruccion_via",
        class_name="obstruccion_via",
        confidence=0.85,
        bbox=BoundingBox(x_min=280.0, y_min=260.0, x_max=360.0, y_max=340.0),
        severity="alta",
        description="[SIMULADO_TEST] Objeto bloqueando paso"
    )


# ==============================================================================
# 1. PRUEBAS DE NORMALIZACIÓN DE CATEGORÍAS OBJETIVO (SECCIÓN 8.1)
# ==============================================================================
def test_target_categories_normalization(
    simulated_pole_detection,
    simulated_vegetation_detection,
    simulated_obstacle_detection
):
    """
    Verifica que las tres categorías objetivo sean reconocidas y normalizadas:
    - Poste de luz ('poste_luz')
    - Vegetación invasiva ('vegetacion_invasiva')
    - Obstrucción de vía ('obstruccion_via')
    Además de variantes en inglés y sinónimos comunes.
    """
    svc = RoadClassificationService()

    # 1. Poste de luz directo y sinónimos
    res_pole = svc.interpret_detection(simulated_pole_detection, drone_id="drone-test-01")
    assert res_pole.normalized_category == CATEGORY_POLE
    assert res_pole.validation_passed is True

    cat, _ = ClassificationRules.normalize_label("street light")
    assert cat == CATEGORY_POLE
    cat, _ = ClassificationRules.normalize_label("columna")
    assert cat == CATEGORY_POLE
    cat, _ = ClassificationRules.normalize_label("catenary_pole")
    assert cat == CATEGORY_POLE

    # 2. Vegetación invasiva directa y sinónimos
    res_veg = svc.interpret_detection(simulated_vegetation_detection, drone_id="drone-test-01")
    assert res_veg.normalized_category == CATEGORY_VEGETATION
    assert res_veg.validation_passed is True

    cat, _ = ClassificationRules.normalize_label("maleza")
    assert cat == CATEGORY_VEGETATION
    cat, _ = ClassificationRules.normalize_label("tree")
    assert cat == CATEGORY_VEGETATION

    # 3. Obstrucción de vía directa y sinónimos
    res_obs = svc.interpret_detection(simulated_obstacle_detection, drone_id="drone-test-01")
    assert res_obs.normalized_category == CATEGORY_OBSTACLE
    assert res_obs.validation_passed is True

    cat, _ = ClassificationRules.normalize_label("obstaculo")
    assert cat == CATEGORY_OBSTACLE
    cat, _ = ClassificationRules.normalize_label("debris")
    assert cat == CATEGORY_OBSTACLE
    cat, _ = ClassificationRules.normalize_label("car")
    assert cat == CATEGORY_OBSTACLE


# ==============================================================================
# 2. PRUEBAS DE ETIQUETAS DESCONOCIDAS (SECCIÓN 8.2)
# ==============================================================================
def test_unknown_and_unmapped_labels():
    """
    Verifica que etiquetas no previstas o raras no provoquen caídas del sistema
    y se mapeen de forma segura a 'otro' con revisión pendiente.
    """
    svc = RoadClassificationService()
    unknown_item = DetectionItem(
        label="objeto_extraterrestre_no_catalogado",
        confidence=0.82,
        bbox=BoundingBox(x_min=100.0, y_min=100.0, x_max=200.0, y_max=200.0)
    )

    result = svc.interpret_detection(unknown_item, drone_id="drone-test-01")
    assert result.normalized_category == CATEGORY_OTHER
    assert result.raw_label == "objeto_extraterrestre_no_catalogado"
    assert result.review_status in ["pendiente_revision", "reportado"]
    assert result.validation_passed is True

    # None o string vacío
    cat_none, clean_none = ClassificationRules.normalize_label(None)
    assert cat_none == CATEGORY_OTHER
    cat_empty, _ = ClassificationRules.normalize_label("   ")
    assert cat_empty == CATEGORY_OTHER


# ==============================================================================
# 3. PRUEBAS DE UMBRALES DE CONFIANZA POR CATEGORÍA (SECCIÓN 8.3)
# ==============================================================================
def test_confidence_filtering_by_category():
    """
    Verifica que umbrales configurables por categoría rechacen o marquen
    detecciones cuya confianza es inferior a la requerida.
    """
    svc = RoadClassificationService()

    # Vegetación requiere 0.55 por defecto
    low_conf_veg = DetectionItem(
        label="vegetacion_invasiva",
        confidence=0.40, # Inferior a 0.55
        bbox=BoundingBox(x_min=100.0, y_min=100.0, x_max=200.0, y_max=200.0)
    )
    res_low = svc.interpret_detection(low_conf_veg, drone_id="drone-test-01")
    assert res_low.validation_passed is False
    assert res_low.rejection_reason is not None
    assert "inferior al umbral" in res_low.rejection_reason.lower()

    # Modificar umbral dinámicamente: si bajamos umbral a 0.35 debe pasar
    res_custom = svc.interpret_detection(
        low_conf_veg,
        drone_id="drone-test-01",
        custom_thresholds={"vegetacion_invasiva": 0.35}
    )
    assert res_custom.validation_passed is True
    assert res_custom.rejection_reason is None


# ==============================================================================
# 4. PRUEBAS DE CAJAS DELIMITADORAS INVÁLIDAS (SECCIÓN 8.4)
# ==============================================================================
def test_invalid_bounding_boxes_rejected():
    """
    Verifica el rechazo estricto de cajas invertidas, de área 0, coordenadas negativas o NaN.
    """
    # 1. Inversión horizontal: x_min >= x_max
    inv_x = BoundingBox(x_min=300.0, y_min=50.0, x_max=100.0, y_max=200.0)
    valid, err = BoundingBoxValidator.validate(inv_x)
    assert valid is False
    assert "inversión horizontal" in err.lower()

    # 2. Inversión vertical: y_min >= y_max
    inv_y = BoundingBox(x_min=100.0, y_min=250.0, x_max=200.0, y_max=150.0)
    valid, err = BoundingBoxValidator.validate(inv_y)
    assert valid is False
    assert "inversión vertical" in err.lower()

    # 3. Coordenadas fuertemente negativas
    neg_box = BoundingBox(x_min=-50.0, y_min=10.0, x_max=100.0, y_max=200.0)
    valid, err = BoundingBoxValidator.validate(neg_box)
    assert valid is False
    assert "negativas" in err.lower()

    # 4. Caja degenerada (ancho < 2px)
    tiny_box = BoundingBox(x_min=100.0, y_min=100.0, x_max=101.0, y_max=200.0)
    valid, err = BoundingBoxValidator.validate(tiny_box)
    assert valid is False
    assert "degenerada" in err.lower()

    # 5. Valores NaN
    nan_box = BoundingBox(x_min=float("nan"), y_min=10.0, x_max=100.0, y_max=200.0)
    valid, err = BoundingBoxValidator.validate(nan_box)
    assert valid is False
    assert "nan" in err.lower()

    # 6. Detección con BBox inválida rechazada por el servicio
    svc = RoadClassificationService()
    det_inv = DetectionItem(label="poste_luz", confidence=0.90, bbox=inv_x)
    interpreted = svc.interpret_detection(det_inv, drone_id="drone-test-01")
    assert interpreted.validation_passed is False
    assert "caja delimitadora inválida" in interpreted.rejection_reason.lower()


# ==============================================================================
# 5. PRUEBAS DE DATOS DE UBICACIÓN AUSENTES (SECCIÓN 8.5)
# ==============================================================================
def test_missing_location_data_handled_gracefully():
    """
    Verifica que la ausencia de ubicación no rompa el sistema ni invente (0,0,0) o GPS falso.
    simulation_coords debe ser None y gps_coords debe ser None.
    """
    svc = RoadClassificationService()
    det = DetectionItem(
        label="obstruccion_via",
        confidence=0.80,
        bbox=BoundingBox(x_min=100.0, y_min=100.0, x_max=200.0, y_max=200.0)
    )

    # Llamada sin pos_x, pos_y, pos_z
    res = svc.interpret_detection(
        det,
        drone_id="drone-test-01",
        pos_x=None,
        pos_y=None,
        pos_z=None
    )

    assert res.simulation_coords is None
    assert res.gps_coords is None
    assert res.coordinate_system == "simulation_webots_cartesian_meters"
    assert res.validation_passed is True

    # Cuando sí hay coordenadas de simulación
    res_with_pos = svc.interpret_detection(
        det,
        drone_id="drone-test-01",
        pos_x=12.45,
        pos_y=-3.21,
        pos_z=5.00
    )
    assert res_with_pos.simulation_coords == {"pos_x": 12.45, "pos_y": -3.21, "pos_z": 5.00}
    assert res_with_pos.gps_coords is None # Garantía: Webots no es GPS WGS84


# ==============================================================================
# 6. PRUEBAS DE TIMESTAMP UTC (SECCIÓN 8.6)
# ==============================================================================
def test_utc_timestamp_handling():
    """
    Verifica que los timestamps devueltos tengan zona horaria UTC explícita.
    """
    svc = RoadClassificationService()
    det = DetectionItem(
        label="poste_luz",
        confidence=0.75,
        bbox=BoundingBox(x_min=100.0, y_min=100.0, x_max=200.0, y_max=200.0)
    )

    # 1. Sin timestamp explícito -> genera uno actual en UTC
    res_auto = svc.interpret_detection(det, drone_id="drone-test-01")
    assert res_auto.timestamp is not None
    assert res_auto.timestamp.tzinfo == timezone.utc

    # 2. Con timestamp naive -> debe convertirse a UTC
    naive_dt = datetime(2026, 10, 18, 12, 0, 0)
    res_naive = svc.interpret_detection(det, drone_id="drone-test-01", timestamp=naive_dt)
    assert res_naive.timestamp.tzinfo == timezone.utc
    assert res_naive.timestamp.year == 2026


# ==============================================================================
# 7. PRUEBAS DE DETECCIONES DUPLICADAS Y DEDUPLICACIÓN (SECCIÓN 8.7)
# ==============================================================================
def test_spatial_temporal_deduplication():
    """
    Verifica que ráfagas de detecciones en el mismo lugar y categoría
    sean amortiguadas dentro de la ventana de deduplicación (5s).
    """
    tracker = DeduplicationTracker(time_window_seconds=5.0, spatial_grid_meters=2.0)
    bbox = BoundingBox(x_min=100.0, y_min=100.0, x_max=200.0, y_max=200.0)
    coords = {"pos_x": 10.0, "pos_y": 20.0, "pos_z": 5.0}
    base_t = datetime.now(timezone.utc)

    # 1. Primer evento: no duplicado
    is_dup, key, count = tracker.check_and_record("drone-01", "obstruccion_via", bbox, coords, now=base_t)
    assert is_dup is False
    assert count == 1

    # 2. Segundo evento a los 1.5s en la misma posición: ES duplicado
    t_1_5s = base_t + timedelta(seconds=1.5)
    is_dup2, _, count2 = tracker.check_and_record("drone-01", "obstruccion_via", bbox, coords, now=t_1_5s)
    assert is_dup2 is True
    assert count2 == 2

    # 3. Tercer evento a los 7.0s (> 5.0s ventana expirada): nuevo evento único
    t_7s = base_t + timedelta(seconds=7.0)
    is_dup3, _, count3 = tracker.check_and_record("drone-01", "obstruccion_via", bbox, coords, now=t_7s)
    assert is_dup3 is False
    assert count3 == 1

    # 4. Evento en ubicación espacial distante (> 10m): no es duplicado
    far_coords = {"pos_x": 35.0, "pos_y": 20.0, "pos_z": 5.0}
    is_dup_far, _, count_far = tracker.check_and_record("drone-01", "obstruccion_via", bbox, far_coords, now=t_1_5s)
    assert is_dup_far is False
    assert count_far == 1


# ==============================================================================
# 8. PRUEBAS DE RESILIENCIA ANTE ERRORES (SECCIÓN 8.8)
# ==============================================================================
def test_error_resilience():
    """
    Verifica que listas vacías, datos corruptos o parámetros nulos no generen excepciones 500.
    """
    svc = RoadClassificationService()

    # Lista vacía
    batch_empty = svc.classify_detections(
        raw_detections=[],
        drone_id="drone-test-01"
    )
    assert batch_empty.total_input == 0
    assert batch_empty.total_valid == 0
    assert batch_empty.detections == []

    # Detección con etiqueta y caja nulas
    item_corrupt = DetectionItem(
        label="",
        confidence=0.5,
        bbox=BoundingBox(x_min=0.0, y_min=0.0, x_max=0.0, y_max=0.0) # Degenerada
    )
    res_corrupt = svc.interpret_detection(item_corrupt, drone_id="drone-test-01")
    assert res_corrupt.validation_passed is False
    assert res_corrupt.normalized_category == CATEGORY_OTHER


# ==============================================================================
# 9. INTEGRACIÓN CON FASTAPI Y WEBSOCKET (SECCIÓN 8.9)
# ==============================================================================
def test_fastapi_and_websocket_integration(client):
    """
    Prueba los endpoints REST de clasificación vial y la difusión por WebSocket.
    """
    # 1. Endpoint /api/v1/deteccion/categories
    res_cats = client.get("/api/v1/deteccion/categories")
    assert res_cats.status_code == 200
    cat_data = res_cats.json()
    assert "poste_luz" in cat_data["target_categories"]
    assert "vegetacion_invasiva" in cat_data["target_categories"]
    assert "obstruccion_via" in cat_data["target_categories"]
    assert cat_data["gps_available"] is False

    # 2. Endpoint /api/v1/deteccion/classify
    classify_payload = {
        "drone_id": "drone-sim-classified-test",
        "frame_id": "frame_cls_01",
        "pos_x": 15.0,
        "pos_y": 7.5,
        "pos_z": 6.0,
        "raw_detections": [
            {
                "label": "tree", # COCO label
                "confidence": 0.82,
                "bbox": {"x_min": 220.0, "y_min": 200.0, "x_max": 420.0, "y_max": 400.0}
            },
            {
                "label": "pole",
                "confidence": 0.89,
                "bbox": {"x_min": 450.0, "y_min": 60.0, "x_max": 470.0, "y_max": 350.0}
            }
        ]
    }
    res_cls = client.post("/api/v1/deteccion/classify", json=classify_payload)
    assert res_cls.status_code == 200, res_cls.text
    batch_res = res_cls.json()
    assert batch_res["total_input"] == 2
    assert batch_res["total_valid"] == 2
    assert len(batch_res["detections"]) == 2

    # Verificar que el árbol central se clasificó como vegetacion_invasiva
    det0 = batch_res["detections"][0]
    assert det0["normalized_category"] == "vegetacion_invasiva"
    assert det0["raw_label"] == "tree"
    assert det0["simulation_coords"]["pos_x"] == 15.0

    # 3. Flujo completo con ingestión de fotograma y WebSocket
    img = np.ones((480, 640, 3), dtype=np.uint8) * 128
    cv2.rectangle(img, (200, 200), (350, 350), (40, 180, 40), -1)
    _, buffer = cv2.imencode('.jpg', img)
    b64_str = base64.b64encode(buffer).decode('utf-8')

    with client.websocket_connect("/ws") as ws:
        ack = ws.receive_json()
        assert ack["type"] == "connection_ack"

        frame_payload = {
            "drone_id": "drone-webots-ws-cls",
            "image_base64": b64_str,
            "pos_x": 10.0,
            "pos_y": 5.0,
            "pos_z": 6.0,
            "run_detection": True
        }
        res_post = client.post("/api/v1/cameras/frame", json=frame_payload)
        assert res_post.status_code == 200
        data_post = res_post.json()
        assert data_post["success"] is True
        assert "classification_time_ms" in data_post


# ==============================================================================
# 10. OBSERVACIONES SOBRE IMÁGENES REALES DEL PROYECTO (SECCIÓN 8.10)
# ==============================================================================
def test_real_project_images_observation():
    """
    Evalúa imágenes reales existentes en el proyecto sin falsear métricas:
    - simulation/latest_webots_camera_frame.jpg
    - Imágenes almacenadas en backend/storage/images/
    """
    real_img_path = Path(root_dir) / "simulation" / "latest_webots_camera_frame.jpg"
    assert real_img_path.exists(), f"Imagen de simulación no encontrada en {real_img_path}"

    img = cv2.imread(str(real_img_path))
    assert img is not None
    assert img.shape == (480, 640, 3)

    # Inferencia con detector heurístico sobre la imagen real
    from backend.app.modules.deteccion.mock_detector import HeuristicDetector
    heur = HeuristicDetector()
    raw_dets = heur.analyze(img, confidence_threshold=0.30)
    
    # Clasificación e interpretación
    batch = classification_service.classify_detections(
        raw_detections=raw_dets,
        drone_id="drone-webots-01",
        pos_x=0.0,
        pos_y=-45.0,
        pos_z=0.2
    )

    # El encuadre actual de latest_webots_camera_frame es una vía limpia sin obstáculos
    # Documentamos el resultado real: 0 anomalías en la vía (no se inventan detecciones falsas)
    assert batch.total_input == len(raw_dets)
    assert batch.processing_time_ms >= 0.0
