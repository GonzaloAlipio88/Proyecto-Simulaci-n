import io
import sys
import uuid
import pytest
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import cv2

# Set path to root
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import init_db
from backend.app.core.config import settings
from backend.app.modules.deteccion.base import VisionModel
from backend.app.modules.deteccion.service import detection_service
from backend.app.modules.deteccion.mock_detector import HeuristicDetector, DiagnosticDetector
from backend.app.schemas.deteccion import DetectionItem, BoundingBox

init_db()

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def create_test_image_bytes(format="jpeg", width=320, height=240, with_objects=True) -> bytes:
    """Helper to generate valid JPEG or PNG bytes in memory."""
    img = np.ones((height, width, 3), dtype=np.uint8) * 120
    if with_objects:
        # Add a green block (heuristically detectable as vegetacion_invasiva)
        cv2.rectangle(img, (50, 50), (150, 150), (35, 180, 40), -1)
        # Add a vertical grey pole (heuristically detectable as poste_luz)
        cv2.rectangle(img, (220, 20), (235, 200), (210, 210, 210), -1)

    ext = ".png" if format.lower() == "png" else ".jpg"
    ok, buf = cv2.imencode(ext, img)
    assert ok, f"Error encoding test image to {ext}"
    return buf.tobytes()


# ==============================================================================
# 1. CARGA VÁLIDA DE JPG
# ==============================================================================
def test_upload_valid_jpg(client):
    """1. Carga válida de JPG: procesa la imagen y devuelve estructura completa."""
    jpg_bytes = create_test_image_bytes(format="jpeg", width=320, height=240, with_objects=True)
    files = {"file": ("inspeccion_via.jpg", io.BytesIO(jpg_bytes), "image/jpeg")}

    response = client.post("/api/v1/imagenes/analyze", files=files)
    assert response.status_code == 200, f"Error response: {response.text}"
    data = response.json()

    assert data["format"] == "JPEG"
    assert data["original_filename"] == "inspeccion_via.jpg"
    assert data["dimensions"]["width"] == 320
    assert data["dimensions"]["height"] == 240
    assert data["dimensions"]["channels"] == 3
    assert data["status"] in ["success", "no_detections"]
    assert "analysis_id" in data
    assert data["size_bytes"] == len(jpg_bytes)
    assert data["processing_time_ms"] > 0


# ==============================================================================
# 2. CARGA VÁLIDA DE PNG
# ==============================================================================
def test_upload_valid_png(client):
    """2. Carga válida de PNG: procesa correctamente formato PNG."""
    png_bytes = create_test_image_bytes(format="png", width=250, height=200, with_objects=True)
    files = {"file": ("drone_scan.png", io.BytesIO(png_bytes), "image/png")}

    response = client.post("/api/v1/imagenes/analyze", files=files)
    assert response.status_code == 200, f"Error response: {response.text}"
    data = response.json()

    assert data["format"] == "PNG"
    assert data["original_filename"] == "drone_scan.png"
    assert data["dimensions"]["width"] == 250
    assert data["dimensions"]["height"] == 200
    assert data["status"] in ["success", "no_detections"]


# ==============================================================================
# 3. ARCHIVO VACÍO
# ==============================================================================
def test_upload_empty_file(client):
    """3. Archivo vacío (0 bytes): debe rechazarse con HTTP 400 y mensaje claro."""
    files = {"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}

    response = client.post("/api/v1/imagenes/analyze", files=files)
    assert response.status_code == 400
    assert "vacío" in response.json()["detail"].lower()


# ==============================================================================
# 4. IMAGEN CORRUPTA
# ==============================================================================
def test_upload_corrupt_image(client):
    """4. Imagen corrupta: datos binarios no decodificables como imagen deben rechazarse con HTTP 400."""
    corrupt_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF" + b"CORRUPTED_GARBAGE_DATA" * 50
    files = {"file": ("corrupt.jpg", io.BytesIO(corrupt_bytes), "image/jpeg")}

    response = client.post("/api/v1/imagenes/analyze", files=files)
    assert response.status_code == 400
    assert "corrupto" in response.json()["detail"].lower() or "no corresponde a una imagen" in response.json()["detail"].lower()


# ==============================================================================
# 5. FORMATO NO PERMITIDO
# ==============================================================================
def test_upload_forbidden_extension(client):
    """5. Formato no permitido (.txt, .exe, .pdf, .sh): rechazo con HTTP 400."""
    for bad_ext in ["payload.exe", "document.pdf", "script.sh", "notes.txt"]:
        files = {"file": (bad_ext, io.BytesIO(b"dummy data text content"), "text/plain")}
        response = client.post("/api/v1/imagenes/analyze", files=files)
        assert response.status_code == 400
        assert "no permit" in response.json()["detail"].lower() or "no admitida" in response.json()["detail"].lower()


# ==============================================================================
# 6. ARCHIVO SUPERIOR AL LÍMITE (10 MB)
# ==============================================================================
def test_upload_exceeds_size_limit(client):
    """6. Archivo superior a 10 MB: debe rechazarse con HTTP 413 o HTTP 400 antes de procesarlo."""
    # Simular payload de 10.5 MB en memoria
    oversized_size = 10 * 1024 * 1024 + 512 * 1024
    oversized_bytes = b"0" * oversized_size
    files = {"file": ("huge_image.jpg", io.BytesIO(oversized_bytes), "image/jpeg")}

    response = client.post("/api/v1/imagenes/analyze", files=files)
    assert response.status_code in [413, 400]
    detail = response.json()["detail"].lower()
    assert "excede el tamaño máximo" in detail or "10 mb" in detail


# ==============================================================================
# 7. TIPO MIME MANIPULADO
# ==============================================================================
def test_upload_spoofed_mime_type(client):
    """7. Tipo MIME manipulado: archivo ejecutable disfrazado como image/jpeg debe rechazarse."""
    fake_exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00This program cannot be run in DOS mode."
    files = {"file": ("malicious.jpg", io.BytesIO(fake_exe_bytes), "image/jpeg")}

    response = client.post("/api/v1/imagenes/analyze", files=files)
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "corrupto" in detail or "no corresponde a una imagen" in detail or "inválida" in detail


# ==============================================================================
# 8. ERROR DEL MOTOR DE VISIÓN MANEJADO
# ==============================================================================
def test_vision_engine_error_handled(client):
    """8. Error del motor de visión: si el detector lanza excepción, se maneja limpiamente sin caer el servidor."""
    class CrashingDetector(VisionModel):
        def load_model(self):
            return True
        def analyze(self, image, confidence_threshold=0.5, frame_id=None, timestamp=None):
            raise RuntimeError("Fallo forzado de memoria en inferencia GPU simulada")
        def annotate_image(self, image, detections):
            return image
        def is_available(self):
            return True
        def get_model_info(self):
            return {"model_name": "CrashDetector", "backend": "mock", "is_available": True}

    prev_detector = detection_service.detector
    try:
        detection_service.set_detector(CrashingDetector())
        jpg_bytes = create_test_image_bytes(format="jpeg", width=100, height=100)
        files = {"file": ("test_crash.jpg", io.BytesIO(jpg_bytes), "image/jpeg")}

        # El endpoint o el servicio deben absorber el error y retornar 200 con no_detections o 500 controlado sin romper el proceso
        response = client.post("/api/v1/imagenes/analyze", files=files)
        assert response.status_code in [200, 500]
        if response.status_code == 200:
            data = response.json()
            assert data["status"] in ["no_detections", "error"]
            assert data["total_valid"] == 0
        else:
            assert "error interno" in response.json()["detail"].lower()
    finally:
        detection_service.set_detector(prev_detector)


# ==============================================================================
# 9. MODELO NO DISPONIBLE / MODO DIAGNÓSTICO
# ==============================================================================
def test_model_unavailable_diagnostic_mode(client):
    """9. Modelo no disponible: modo diagnóstico informa limitaciones honestamente sin inventar detecciones."""
    diagnostic = DiagnosticDetector(reason="Pesos YOLO no encontrados en storage/weights")
    prev_detector = detection_service.detector
    try:
        detection_service.set_detector(diagnostic)
        jpg_bytes = create_test_image_bytes(format="jpeg", width=120, height=120)
        files = {"file": ("diag_test.jpg", io.BytesIO(jpg_bytes), "image/jpeg")}

        response = client.post("/api/v1/imagenes/analyze", files=files)
        assert response.status_code == 200
        data = response.json()

        assert data["total_valid"] == 0
        assert data["status"] == "no_detections"
        assert data["model_info"]["is_diagnostic"] is True
        # Debe haber advertencias sobre el modo diagnóstico
        assert len(data["model_info"]["warnings"]) > 0
        assert any("diagnóstico" in w.lower() for w in data["model_info"]["warnings"])
    finally:
        detection_service.set_detector(prev_detector)


# ==============================================================================
# 10. IMAGEN SIN DETECCIONES
# ==============================================================================
def test_image_without_detections(client):
    """10. Imagen sin detecciones: se distingue claramente de un análisis fallido."""
    # Imagen lisa y vacía (sin objetos ni vegetación)
    empty_scene_bytes = create_test_image_bytes(format="jpeg", width=200, height=150, with_objects=False)
    files = {"file": ("via_despejada.jpg", io.BytesIO(empty_scene_bytes), "image/jpeg")}

    response = client.post("/api/v1/imagenes/analyze", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "no_detections"
    assert data["total_valid"] == 0
    assert len(data["detections"]) == 0
    assert data["analysis_id"] is not None


# ==============================================================================
# 11. RESPUESTA ESTRUCTURADA CORRECTA
# ==============================================================================
def test_structured_response_fields(client):
    """11. Respuesta estructurada: verifica la presencia y tipo de todos los campos exigidos."""
    jpg_bytes = create_test_image_bytes(format="jpeg", width=300, height=200, with_objects=True)
    files = {"file": ("inspeccion_completa.jpg", io.BytesIO(jpg_bytes), "image/jpeg")}

    response = client.post("/api/v1/imagenes/analyze?confidence_threshold=0.3", files=files)
    assert response.status_code == 200
    data = response.json()

    required_fields = [
        "analysis_id", "original_filename", "stored_filename", "dimensions",
        "format", "size_bytes", "timestamp", "status", "detections",
        "total_detected", "total_valid", "total_rejected", "has_location",
        "simulation_coords", "gps_coords", "location_notice",
        "inference_time_ms", "classification_time_ms", "processing_time_ms",
        "model_info", "annotated_image_base64"
    ]
    for field in required_fields:
        assert field in data, f"Falta el campo requerido: {field}"

    assert isinstance(data["dimensions"]["width"], int)
    assert isinstance(data["dimensions"]["height"], int)
    assert isinstance(data["model_info"]["warnings"], list)
    assert isinstance(data["detections"], list)


# ==============================================================================
# 12. AUSENCIA DE COORDENADAS FICTICIAS
# ==============================================================================
def test_no_fictitious_coordinates(client):
    """12. Ausencia de coordenadas ficticias: fotografías externas reportan coordenadas nulas y aviso claro."""
    jpg_bytes = create_test_image_bytes(format="jpeg", width=200, height=200)
    files = {"file": ("foto_usuario.jpg", io.BytesIO(jpg_bytes), "image/jpeg")}

    response = client.post("/api/v1/imagenes/analyze", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["has_location"] is False
    assert data["simulation_coords"] is None
    assert data["gps_coords"] is None
    assert "no disponible" in data["location_notice"].lower()

    # Cada detección individual tampoco debe tener coordenadas inventadas
    for det in data["detections"]:
        assert det.get("simulation_coords") is None
        assert det.get("gps_coords") is None


# ==============================================================================
# 13. INTEGRACIÓN CON ENDPOINT ALIAS (/images/analyze)
# ==============================================================================
def test_endpoint_alias_images_analyze(client):
    """13. Integración de endpoint: tanto /api/v1/imagenes/analyze como /api/v1/images/analyze responden."""
    png_bytes = create_test_image_bytes(format="png", width=180, height=180)
    files = {"file": ("alias_test.png", io.BytesIO(png_bytes), "image/png")}

    res_alias = client.post("/api/v1/images/analyze", files=files)
    assert res_alias.status_code == 200
    data = res_alias.json()
    assert data["original_filename"] == "alias_test.png"
    assert data["format"] == "PNG"


# ==============================================================================
# 14. REGRESIÓN DE LAS FUNCIONALIDADES DE SEMANAS 1–6
# ==============================================================================
def test_regression_previous_weeks_endpoints(client):
    """14. Regresión: verificar que endpoints anteriores (/health, /drones, /telemetria, /deteccion/status) sigan funcionando."""
    # Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "online"

    # Deteccion status (Semana 5)
    res_status = client.get("/api/v1/deteccion/status")
    assert res_status.status_code == 200
    assert "model_type" in res_status.json()

    # Categorias viales (Semana 6)
    res_cats = client.get("/api/v1/deteccion/categories")
    assert res_cats.status_code == 200
    assert "target_categories" in res_cats.json()
    assert "poste_luz" in res_cats.json()["target_categories"]

    # Listar imágenes almacenadas
    res_imgs = client.get("/api/v1/imagenes")
    assert res_imgs.status_code == 200
    assert isinstance(res_imgs.json(), list)

    # Incidentes
    res_inc = client.get("/api/v1/incidentes")
    assert res_inc.status_code == 200
    assert isinstance(res_inc.json(), list)
