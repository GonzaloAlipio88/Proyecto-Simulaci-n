import pytest
import sys
from pathlib import Path
import base64
import numpy as np
import cv2

# Set path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.database import init_db

# Initialize tables for tests
init_db()

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["database"] == "connected"

def test_drone_lifecycle(client):

    # Register drone
    drone_payload = {
        "id": "drone-sim-01",
        "name": "Webots Inspector Alpha",
        "model": "DJI Matrice Webots",
        "status": "idle",
        "battery_level": 98.5,
        "current_x": 10.0,
        "current_y": 5.0,
        "current_z": 0.0,
        "current_speed": 0.0,
        "flight_mode": "autonomous"
    }
    res = client.post("/api/v1/drones", json=drone_payload)
    assert res.status_code == 200
    drone_data = res.json()
    assert drone_data["id"] == "drone-sim-01"

    # Query all drones
    res_list = client.get("/api/v1/drones")
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 1

    # Send command
    cmd_payload = {"command": "takeoff"}
    res_cmd = client.post("/api/v1/drones/drone-sim-01/command", json=cmd_payload)
    assert res_cmd.status_code == 200
    assert res_cmd.json()["new_status"] == "flying"

def test_telemetry_flow(client):
    telemetry_payload = {
        "drone_id": "drone-sim-01",
        "pos_x": 12.5,
        "pos_y": 6.8,
        "pos_z": 15.2,
        "roll": 0.02,
        "pitch": -0.01,
        "yaw": 1.57,
        "speed": 4.5,
        "battery": 95.0,
        "flight_mode": "autonomous"
    }
    res = client.post("/api/v1/telemetria", json=telemetry_payload)
    assert res.status_code == 200
    tel_data = res.json()
    assert tel_data["drone_id"] == "drone-sim-01"
    assert tel_data["pos_z"] == 15.2

    # Query latest
    res_latest = client.get("/api/v1/telemetria/drone-sim-01/latest")
    assert res_latest.status_code == 200
    assert res_latest.json()["speed"] == 4.5

    # Query history
    res_history = client.get("/api/v1/telemetria/drone-sim-01/history?limit=10")
    assert res_history.status_code == 200
    assert len(res_history.json()) >= 1

def test_detection_classes_and_status(client):
    res_classes = client.get("/api/v1/deteccion/classes")
    assert res_classes.status_code == 200
    classes = res_classes.json()["classes"]
    assert "poste_luz" in classes
    assert "vegetacion_invasiva" in classes
    assert "obstruccion_via" in classes

    res_status = client.get("/api/v1/deteccion/status")
    assert res_status.status_code == 200
    assert res_status.json()["yolo_ready"] is True

def test_camera_frame_ingestion(client):
    # Create synthetic test image (640x480) with green patch (vegetation) and a vertical pole line
    img = np.ones((480, 640, 3), dtype=np.uint8) * 128
    # Add green vegetation patch
    cv2.rectangle(img, (200, 200), (350, 350), (40, 180, 40), -1)
    # Add vertical pole
    cv2.rectangle(img, (500, 50), (515, 400), (220, 220, 220), -1)
    
    _, buffer = cv2.imencode('.jpg', img)
    b64_str = base64.b64encode(buffer).decode('utf-8')

    frame_payload = {
        "drone_id": "drone-sim-01",
        "image_base64": b64_str,
        "pos_x": 14.0,
        "pos_y": 7.0,
        "pos_z": 15.0,
        "run_detection": True
    }
    res = client.post("/api/v1/cameras/frame", json=frame_payload)
    assert res.status_code == 200
    result = res.json()
    assert result["success"] is True
    assert result["image_id"] is not None

    # Check camera status
    res_cam = client.get("/api/v1/cameras/status")
    assert res_cam.status_code == 200
    assert res_cam.json()["is_active"] is True

def test_incidents_management(client):
    inc_payload = {
        "drone_id": "drone-sim-01",
        "tipo": "vegetacion_invasiva",
        "severidad": "alta",
        "descripcion": "Vegetación densa sobre riel principal en km 14.2",
        "pos_x": 14.2,
        "pos_y": 7.1,
        "pos_z": 14.8,
        "confidence": 0.88,
        "estado": "reportado"
    }
    res = client.post("/api/v1/incidentes", json=inc_payload)
    assert res.status_code == 200
    inc_data = res.json()
    assert inc_data["tipo"] == "vegetacion_invasiva"
    inc_id = inc_data["id"]

    # Filter incidents
    res_filtered = client.get("/api/v1/incidentes?tipo=vegetacion_invasiva")
    assert res_filtered.status_code == 200
    assert any(i["id"] == inc_id for i in res_filtered.json())

    # Update incident status
    res_patch = client.patch(f"/api/v1/incidentes/{inc_id}", json={"estado": "en_revision"})
    assert res_patch.status_code == 200
    assert res_patch.json()["estado"] == "en_revision"

def test_websocket_connection(client):
    with client.websocket_connect("/ws") as websocket:
        ack = websocket.receive_json()
        assert ack["type"] == "connection_ack"
        
        # Send ping
        websocket.send_json({"type": "ping", "payload": "test"})
        pong = websocket.receive_json()
        assert pong["type"] == "pong"
        assert pong["payload"] == "test"

