import io
import base64
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _generate_synthetic_image_bytes(fmt: str = ".jpg", width: int = 320, height: int = 240) -> bytes:
    """Genera una imagen sintética válida codificada en JPG o PNG."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    # Fondo gris vial
    img[:] = (60, 60, 60)
    # Franja verde en zona central (vegetación simulada)
    cv2.rectangle(img, (110, 80), (210, 190), (30, 180, 40), -1)
    # Columna vertical (poste simulado)
    cv2.rectangle(img, (40, 20), (60, 210), (200, 200, 220), -1)
    ok, buf = cv2.imencode(fmt, img)
    assert ok
    return buf.tobytes()


def test_semana_9_dashboard_initial_sync_endpoints(client):
    """
    Verifica todos los endpoints que consulta el dashboard en su arranque y sincronización periódica:
    - GET /health
    - GET /api/v1/deteccion/status
    - GET /api/v1/deteccion/categories
    - GET /api/v1/cameras/status
    - GET /api/v1/drones
    """
    h_res = client.get("/health")
    assert h_res.status_code == 200
    assert h_res.json()["status"] == "online"

    det_res = client.get("/api/v1/deteccion/status")
    assert det_res.status_code == 200
    det_data = det_res.json()
    for field in [
        "model_type",
        "is_loaded",
        "confidence_threshold",
        "yolo_ready",
        "active_model",
        "backend",
        "device",
        "is_available",
        "is_fallback",
        "is_diagnostic",
    ]:
        assert field in det_data

    cat_res = client.get("/api/v1/deteccion/categories")
    assert cat_res.status_code == 200
    cat_data = cat_res.json()
    assert "poste_luz" in cat_data["target_categories"]
    assert "vegetacion_invasiva" in cat_data["target_categories"]
    assert "obstruccion_via" in cat_data["target_categories"]
    assert "default_thresholds" in cat_data

    cam_res = client.get("/api/v1/cameras/status")
    assert cam_res.status_code == 200
    cam_data = cam_res.json()
    assert "is_active" in cam_data
    assert "resolution" in cam_data

    drones_res = client.get("/api/v1/drones")
    assert drones_res.status_code == 200
    assert isinstance(drones_res.json(), list)


def test_semana_9_manual_jpg_and_png_analysis_and_sqlite_incident_promotion(client):
    """
    Verifica el flujo completo de la sección de Análisis de Imágenes Externas (JPG y PNG)
    en el dashboard y la promoción de una detección a incidente en SQLite.
    """
    for ext, mime in [(".jpg", "image/jpeg"), (".png", "image/png")]:
        img_bytes = _generate_synthetic_image_bytes(fmt=ext)
        files = {"file": (f"test_sem9{ext}", io.BytesIO(img_bytes), mime)}
        res = client.post(
            "/api/v1/imagenes/analyze?confidence_threshold=0.35&save_to_storage=true",
            files=files,
        )
        assert res.status_code == 200
        data = res.json()

        assert data["original_filename"] == f"test_sem9{ext}"
        assert data["status"] in ("success", "no_detections")
        assert data["has_location"] is False
        assert data["simulation_coords"] is None
        assert data["gps_coords"] is None
        assert "annotated_image_base64" in data
        assert data["annotated_image_base64"] is not None
        assert "model_info" in data
        assert data["image_id"] is not None

        # Promover detección o resultado del análisis a incidente SQLite desde el dashboard
        inc_payload = {
            "drone_id": "external_upload",
            "tipo": "vegetacion_invasiva",
            "severidad": "media",
            "descripcion": f"Incidencia registrada desde análisis manual ({data['original_filename']})",
            "pos_x": None,
            "pos_y": None,
            "pos_z": None,
            "coordenadas_tipo": "imagen_externa_sin_gps",
            "confidence": 0.82,
            "imagen_id": data["image_id"],
            "estado": "reportado",
        }
        inc_res = client.post("/api/v1/incidentes?allow_duplicate=true", json=inc_payload)
        assert inc_res.status_code == 200
        inc_created = inc_res.json()
        assert inc_created["id"] > 0
        assert inc_created["imagen_id"] == data["image_id"]

        # Verificar descarga de la evidencia vinculada como lo hace IncidentLog
        img_dl = client.get(f"/api/v1/incidentes/{inc_created['id']}/imagen?download=true")
        assert img_dl.status_code == 200
        assert len(img_dl.content) > 100

        # Limpiar incidente de prueba
        del_res = client.delete(f"/api/v1/incidentes/{inc_created['id']}")
        assert del_res.status_code == 200


def test_semana_9_camera_frame_stream_and_latest_frame_recovery(client):
    """
    Verifica que al ingresar un fotograma desde el dron, el endpoint de recuperación
    GET /api/v1/cameras/{drone_id}/latest-frame devuelva la información completa
    para poblar LiveCameraFeed.
    """
    jpg_bytes = _generate_synthetic_image_bytes(fmt=".jpg")
    b64_str = base64.b64encode(jpg_bytes).decode("utf-8")

    frame_res = client.post(
        "/api/v1/cameras/frame",
        json={
            "drone_id": "drone-sem9-01",
            "image_base64": b64_str,
            "pos_x": 15.2,
            "pos_y": -3.4,
            "pos_z": 12.0,
            "run_detection": True,
        },
    )
    assert frame_res.status_code == 200
    frame_data = frame_res.json()
    assert frame_data["success"] is True

    latest_res = client.get("/api/v1/cameras/drone-sem9-01/latest-frame?annotated=true")
    assert latest_res.status_code == 200
    latest_info = latest_res.json()
    assert latest_info["available"] is True
    assert latest_info["drone_id"] == "drone-sem9-01"
    assert latest_info["frame_base64"] is not None
    assert latest_info["width"] == 320
    assert latest_info["height"] == 240

