import pytest
import sys
from pathlib import Path
import base64
from datetime import datetime, timezone
import numpy as np
import cv2

# Set path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.core.config import settings
from backend.app.modules.deteccion.base import VisionModel, BaseDetector
from backend.app.modules.deteccion.image_processor import ImageProcessor, ImageProcessingError
from backend.app.modules.deteccion.mock_detector import HeuristicDetector, DiagnosticDetector
from backend.app.modules.deteccion.yolo_adapter import YOLODetector
from backend.app.modules.deteccion.service import DetectionService, detection_service
from backend.app.schemas.deteccion import DetectionItem, BoundingBox

init_db()

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def sample_valid_bgr():
    """Generates a standard 640x480 BGR image with road and vegetation."""
    img = np.ones((480, 640, 3), dtype=np.uint8) * 100
    # Add green vegetation patch
    cv2.rectangle(img, (150, 200), (300, 350), (35, 180, 40), -1)
    # Add vertical pole
    cv2.rectangle(img, (480, 60), (495, 380), (200, 200, 200), -1)
    return img

@pytest.fixture
def sample_valid_base64(sample_valid_bgr):
    _, buffer = cv2.imencode('.jpg', sample_valid_bgr)
    return base64.b64encode(buffer).decode('utf-8')

@pytest.fixture
def sample_object_scene_bgr():
    """Returns authentic 640x480 test image containing detectable objects."""
    try:
        import ultralytics.utils as u
        bus_path = Path(u.ASSETS) / "bus.jpg"
        if bus_path.exists():
            img = cv2.imread(str(bus_path))
            if img is not None:
                return cv2.resize(img, (640, 480))
    except Exception:
        pass
    return np.ones((480, 640, 3), dtype=np.uint8) * 128

@pytest.fixture
def sample_object_scene_base64(sample_object_scene_bgr):
    _, buffer = cv2.imencode('.jpg', sample_object_scene_bgr)
    return base64.b64encode(buffer).decode('utf-8')


# ==============================================================================
# 1. PRUEBAS DE IMAGEN VÁLIDA
# ==============================================================================
def test_image_processor_valid_image(sample_valid_bgr):
    """Verifica que una imagen estándar uint8 640x480 sea validada y convertida correctamente."""
    valid, err = ImageProcessor.validate_image_array(sample_valid_bgr)
    assert valid is True
    assert err is None

    # Conversión BGR -> RGB -> BGR
    rgb = ImageProcessor.bgr_to_rgb(sample_valid_bgr)
    assert rgb.shape == sample_valid_bgr.shape
    # El canal azul y rojo deben intercambiarse
    assert rgb[250, 200, 0] == sample_valid_bgr[250, 200, 2]

    # Codificación a base64 y posterior decodificación
    b64 = ImageProcessor.bgr_to_base64(sample_valid_bgr)
    assert isinstance(b64, str)
    assert len(b64) > 100

    decoded = ImageProcessor.base64_to_bgr(b64)
    assert decoded is not None
    assert decoded.shape == (480, 640, 3)


# ==============================================================================
# 2. PRUEBAS DE IMAGEN VACÍA O CORRUPTA
# ==============================================================================
def test_image_processor_empty_or_corrupt_image():
    """Verifica el rechazo controlado de entradas nulas, vacías o corruptas."""
    # Matriz None
    valid, err = ImageProcessor.validate_image_array(None)
    assert valid is False
    assert "nula" in err.lower()

    # Matriz vacía (size == 0)
    empty_arr = np.zeros((0, 0, 3), dtype=np.uint8)
    valid, err = ImageProcessor.validate_image_array(empty_arr)
    assert valid is False
    assert "vacía" in err.lower()

    # Base64 corrupto / no decodificable
    assert ImageProcessor.base64_to_bgr("not-a-valid-base64-string-at-all!!") is None
    assert ImageProcessor.base64_to_bgr("") is None
    assert ImageProcessor.base64_to_bgr(None) is None

    # Bytes vacíos
    assert ImageProcessor.bytes_to_bgr(b"") is None
    assert ImageProcessor.bytes_to_bgr(b"corrupted-jpeg-header-xyz") is None


# ==============================================================================
# 3. PRUEBAS DE FORMATO Y DIMENSIONES INCORRECTOS
# ==============================================================================
def test_image_processor_invalid_format_and_dimensions():
    """Verifica la detección de tipos de datos incorrectos y dimensiones fuera de rango."""
    # Tipo float en lugar de uint8
    float_img = np.ones((100, 100, 3), dtype=np.float32)
    valid, err = ImageProcessor.validate_image_array(float_img)
    assert valid is False
    assert "uint8" in err

    # Dimensión inferior al mínimo (10x10 < 16x16)
    tiny_img = np.ones((10, 10, 3), dtype=np.uint8)
    valid, err = ImageProcessor.validate_image_array(tiny_img)
    assert valid is False
    assert "inferiores" in err.lower()

    # Número de canales no soportado (ej. 2 canales o 5 canales)
    weird_channels = np.ones((100, 100, 5), dtype=np.uint8)
    valid, err = ImageProcessor.validate_image_array(weird_channels)
    assert valid is False
    assert "canales" in err.lower()


# ==============================================================================
# 4. RESULTADO ESTRUCTURADO DE INFERENCIA
# ==============================================================================
def test_structured_inference_result(sample_valid_bgr):
    """
    Verifica que la inferencia devuelva detecciones con el contrato unificado:
    class_name, confidence, bbox (x_min, y_min, x_max, y_max), frame_id y timestamp.
    """
    detector = HeuristicDetector()
    now_utc = datetime.now(timezone.utc)
    test_frame_id = "test_frame_001"

    detections = detector.analyze(
        sample_valid_bgr,
        confidence_threshold=0.5,
        frame_id=test_frame_id,
        timestamp=now_utc
    )

    assert isinstance(detections, list)
    assert len(detections) >= 1

    for det in detections:
        assert isinstance(det, DetectionItem)
        assert det.class_name in ["poste_luz", "vegetacion_invasiva", "obstruccion_via"]
        assert det.label == det.class_name  # Sincronización garantizada
        assert 0.0 <= det.confidence <= 1.0
        assert isinstance(det.bbox, BoundingBox)
        assert det.bbox.x_min >= 0
        assert det.bbox.y_min >= 0
        assert det.bbox.x_max >= det.bbox.x_min
        assert det.bbox.y_max >= det.bbox.y_min
        assert det.frame_id == test_frame_id
        assert det.timestamp == now_utc

    # Verificación de anotación
    annotated = detector.annotate_image(sample_valid_bgr, detections)
    assert annotated is not None
    assert annotated.shape == sample_valid_bgr.shape


# ==============================================================================
# 5. MODELO AUSENTE / PESOS INEXISTENTES
# ==============================================================================
def test_yolo_adapter_missing_weights_handling(sample_valid_bgr):
    """
    Verifica que cuando los pesos no existen:
    - El adaptador YOLO NO descarga modelos pesados automáticamente.
    - No derriba el sistema.
    - Informa claramente que no está disponible (is_available=False).
    - analyze() devuelve lista vacía sin inventar detecciones.
    """
    missing_weights_path = "storage/weights/non_existent_weights_xyz123.pt"
    yolo = YOLODetector(weights_path=missing_weights_path, device="cpu")

    loaded = yolo.load_model()
    assert loaded is False
    assert yolo.is_available() is False
    assert yolo.load_error is not None
    assert "no encontrado" in yolo.load_error.lower()

    # La inferencia sobre un modelo no cargado no debe lanzar excepción
    detections = yolo.analyze(sample_valid_bgr)
    assert detections == []

    # get_model_info debe reflejar el estado real sin afirmar que es un YOLO funcional
    info = yolo.get_model_info()
    assert info["is_loaded"] is False
    assert info["is_available"] is False
    assert info["load_error"] == yolo.load_error


# ==============================================================================
# 6. ERROR DURANTE LA INFERENCIA
# ==============================================================================
class FaultyMockDetector(VisionModel):
    """Modelo simulado defectuoso para verificar captura controlada de errores."""
    def load_model(self) -> bool:
        return True
    def is_available(self) -> bool:
        return True
    def analyze(self, image, confidence_threshold=0.5, frame_id=None, timestamp=None):
        raise RuntimeError("Simulated internal GPU memory fault during inference")
    def annotate_image(self, image, detections):
        return image
    def get_model_info(self):
        return {"model_name": "faulty_mock", "backend": "mock"}

def test_inference_error_handled_gracefully(sample_valid_bgr):
    """Verifica que fallos inesperados en el modelo no derriben el servicio de detección."""
    service = DetectionService()
    faulty_model = FaultyMockDetector()
    service.set_detector(faulty_model)

    detections, annotated, elapsed_ms = service.process_frame(sample_valid_bgr, drone_id="drone-test")
    assert detections == []
    assert annotated is None
    assert elapsed_ms >= 0.0


# ==============================================================================
# 7. CARGA DE PESOS AUTÉNTICOS E INFERENCIA REAL YOLO (SEMANA 5)
# ==============================================================================
def test_authentic_yolo_weights_loading():
    """Verifica la carga auténtica de pesos YOLOv8n sin descargar de Internet."""
    yolo = YOLODetector(weights_path=settings.YOLO_WEIGHTS_PATH, device="cpu")
    loaded = yolo.load_model()
    assert loaded is True
    assert yolo.is_available() is True
    assert yolo.load_error is None
    assert yolo.mode == "pretrained_generic"
    assert len(yolo.class_mapping) == 80
    assert "person" in yolo.class_mapping.values()
    assert "bus" in yolo.class_mapping.values()


def test_authentic_yolo_inference_real(sample_object_scene_bgr):
    """Verifica que la inferencia real de YOLO produzca detecciones válidas sobre una imagen con objetos."""
    yolo = YOLODetector(weights_path=settings.YOLO_WEIGHTS_PATH, device="cpu")
    yolo.load_model()
    detections = yolo.analyze(sample_object_scene_bgr, confidence_threshold=0.3)
    assert len(detections) >= 1
    for det in detections:
        assert isinstance(det, DetectionItem)
        assert det.class_name in yolo.class_mapping.values()
        assert 0.3 <= det.confidence <= 1.0
        assert det.bbox.x_min >= 0
        assert det.bbox.y_min >= 0
        assert det.bbox.x_max > det.bbox.x_min
        assert det.bbox.y_max > det.bbox.y_min


def test_confidence_threshold_filtering(sample_object_scene_bgr):
    """Verifica que el umbral de confianza filtre adecuadamente las detecciones."""
    yolo = YOLODetector(weights_path=settings.YOLO_WEIGHTS_PATH, device="cpu")
    yolo.load_model()
    low_thresh_dets = yolo.analyze(sample_object_scene_bgr, confidence_threshold=0.25)
    high_thresh_dets = yolo.analyze(sample_object_scene_bgr, confidence_threshold=0.90)
    assert len(low_thresh_dets) >= len(high_thresh_dets)


def test_missing_dependencies_simulation(monkeypatch):
    """Verifica el comportamiento cuando la biblioteca ultralytics no está disponible."""
    import builtins
    orig_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "ultralytics":
            raise ImportError("No module named 'ultralytics'")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    yolo = YOLODetector(weights_path=settings.YOLO_WEIGHTS_PATH, device="cpu")
    success = yolo.load_model()
    assert success is False
    assert yolo.is_available() is False
    assert yolo.mode == "library_missing"
    assert "ultralytics" in yolo.load_error.lower()


def test_detector_selection_and_fallback():
    """Verifica la selección del detector en DetectionService y el fallback a OpenCV."""
    # 1. Configuración activa con YOLO operativo
    svc = DetectionService()
    assert svc.is_fallback is False
    assert svc.detector.is_available() is True
    assert svc.detector.get_model_info()["backend"] == "yolo"

    # 2. Simulación de fallo en ruta de pesos -> Fallback automático a HeuristicDetector
    from unittest.mock import patch
    with patch.object(settings, "YOLO_WEIGHTS_PATH", "storage/weights/nonexistent_fake.pt"):
        svc_fallback = DetectionService()
        assert svc_fallback.is_fallback is True
        assert svc_fallback.detector.get_model_info()["backend"] == "opencv"
        st = svc_fallback.get_status()
        assert st["is_fallback"] is True
        assert st["backend"] == "opencv"
        assert st["yolo_ready"] is False


# ==============================================================================
# 8. INICIALIZACIÓN ÚNICA DEL MODELO (SINGLETON / CACHED LOAD)
# ==============================================================================
def test_single_model_initialization():
    """Verifica que invocar load_model múltiples veces no reintente la carga si ya está inicializado."""
    detector = HeuristicDetector()
    assert detector.is_available() is True
    result = detector.load_model()
    assert result is True

    # También verificar singleton en YOLODetector
    yolo = YOLODetector(weights_path=settings.YOLO_WEIGHTS_PATH, device="cpu")
    assert yolo.load_model() is True
    assert yolo.load_model() is True


# ==============================================================================
# 9. MODO DE DIAGNÓSTICO EXPLÍCITO (NO INVENTA DETECCIONES)
# ==============================================================================
def test_explicit_diagnostic_mode(sample_valid_bgr):
    """Verifica que el modo diagnóstico reporte explícitamente y no invente detecciones falsas."""
    diagnostic = DiagnosticDetector(reason="Pesos YOLO ausentes en entorno de test")
    assert diagnostic.is_available() is False

    info = diagnostic.get_model_info()
    assert info["is_diagnostic"] is True
    assert "ausentes" in info["reason"]

    # Debe devolver 0 detecciones siempre
    detections = diagnostic.analyze(sample_valid_bgr)
    assert len(detections) == 0


# ==============================================================================
# 10. INTEGRACIÓN CON BACKEND Y ENDPOINTS REST
# ==============================================================================
def test_api_standalone_detect_endpoint(client, sample_object_scene_base64, sample_valid_base64):
    """Prueba el endpoint /api/v1/deteccion/detect con imagen con objetos, sin objetos y corrupta."""
    # 1. Petición válida con escena de objetos
    payload = {
        "drone_id": "drone-sim-vision",
        "image_base64": sample_object_scene_base64,
        "threshold": 0.4,
        "frame_id": "frame_test_01"
    }
    res = client.post("/api/v1/deteccion/detect", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["drone_id"] == "drone-sim-vision"
    assert data["total_detected"] >= 1
    assert "model_name" in data
    assert data["backend_used"] == "yolo"
    assert data["processed_time_ms"] > 0

    first_det = data["detections"][0]
    assert "class_name" in first_det
    assert "label" in first_det
    assert "bbox" in first_det

    # 2. Petición válida con imagen sin objetos (no inventa detecciones)
    payload_empty = {
        "drone_id": "drone-sim-vision",
        "image_base64": sample_valid_base64,
        "threshold": 0.5
    }
    res_empty = client.post("/api/v1/deteccion/detect", json=payload_empty)
    assert res_empty.status_code == 200
    assert res_empty.json()["total_detected"] == 0

    # 3. Petición corrupta (debe rechazar con 400)
    corrupt_payload = {
        "drone_id": "drone-sim-vision",
        "image_base64": "corrupted_non_image_base64"
    }
    res_corrupt = client.post("/api/v1/deteccion/detect", json=corrupt_payload)
    assert res_corrupt.status_code == 400


def test_api_vision_status_endpoint(client):
    """Verifica que /api/v1/deteccion/status reporte el estado completo del motor."""
    res = client.get("/api/v1/deteccion/status")
    assert res.status_code == 200
    status = res.json()
    assert status["model_type"] == "yolo"
    assert status["is_loaded"] is True
    assert status["yolo_ready"] is True
    assert status["ultralytics_available"] is True
    assert status["weights_exist"] is True
    assert status["backend"] == "yolo"
    assert status["device"] == "cpu"
    assert status["is_fallback"] is False
    assert status["model_mode"] == "pretrained_generic"
    assert len(status["classes"]) == 80


def test_api_camera_frame_integration(client, sample_object_scene_base64):
    """
    Verifica que la ingesta de fotogramas por /api/v1/cameras/frame
    invoque el motor de visión y conserve toda la compatibilidad con las semanas 1-4.
    """
    frame_payload = {
        "drone_id": "drone-webots-vision-test",
        "image_base64": sample_object_scene_base64,
        "pos_x": 5.0,
        "pos_y": 10.0,
        "pos_z": 6.0,
        "run_detection": True
    }
    res = client.post("/api/v1/cameras/frame", json=frame_payload)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["success"] is True
    assert body["detections_count"] >= 1
    assert "inference_time_ms" in body
    assert body["width"] == 640
    assert body["height"] == 480


def test_semana_11_dynamic_confidence_threshold_get_and_set(client):
    """
    Semana 11: Valida el control dinámico del umbral de confianza de visión (0.15 - 0.50):
    1. Consulta de umbral actual vía GET /api/v1/deteccion/threshold.
    2. Modificación dinámica vía PUT /api/v1/deteccion/threshold sin reinicio.
    3. Validación de sincronización en /api/v1/deteccion/status y en el singleton detection_service.
    4. Rechazo de valores fuera del intervalo permitido [0.15, 0.50] con HTTP 422.
    """
    from backend.app.modules.deteccion.service import detection_service

    # 1. Consulta inicial
    get_res = client.get("/api/v1/deteccion/threshold")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "confidence_threshold" in data
    assert data["min_threshold"] == 0.15
    assert data["max_threshold"] == 0.50
    initial_threshold = data["confidence_threshold"]

    # 2. Modificación válida a 0.35
    put_res = client.put("/api/v1/deteccion/threshold", json={"threshold": 0.35})
    assert put_res.status_code == 200
    put_data = put_res.json()
    assert put_data["confidence_threshold"] == 0.35
    assert detection_service.get_confidence_threshold() == 0.35

    # 3. Verificación de sincronización en status
    status_res = client.get("/api/v1/deteccion/status")
    assert status_res.status_code == 200
    assert status_res.json()["confidence_threshold"] == 0.35

    # 4. Modificación vía POST alternativa
    post_res = client.post("/api/v1/deteccion/threshold", json={"threshold": 0.20})
    assert post_res.status_code == 200
    assert post_res.json()["confidence_threshold"] == 0.20
    assert detection_service.get_confidence_threshold() == 0.20

    # 5. Rechazo estricto de valores inferiores a 0.15
    low_res = client.put("/api/v1/deteccion/threshold", json={"threshold": 0.10})
    assert low_res.status_code == 422

    # 6. Rechazo estricto de valores superiores a 0.50
    high_res = client.put("/api/v1/deteccion/threshold", json={"threshold": 0.65})
    assert high_res.status_code == 422

    # 7. Restaurar umbral inicial seguro
    client.put("/api/v1/deteccion/threshold", json={"threshold": initial_threshold})
    assert detection_service.get_confidence_threshold() == initial_threshold


