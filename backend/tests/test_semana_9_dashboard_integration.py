import io
import base64
from pathlib import Path
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
    - GET /api/v1/drones/mission/waypoints
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

    wp_res = client.get("/api/v1/drones/mission/waypoints")
    assert wp_res.status_code == 200
    wps = wp_res.json()
    assert len(wps) == 5
    assert [w["index"] for w in wps] == [1, 2, 3, 4, 5]


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


def test_semana_9_bidirectional_drone_commands_and_webots_controller(client):
    """
    Verifica la comunicación bidireccional de comandos entre el Dashboard, FastAPI y el
    FlightController de Webots:
    - Encolado y actualización en SQLite de takeoff, hover, resume_patrol, return_to_home, land y set_waypoint.
    - Consumo de la cola por parte de Webots (GET /api/v1/drones/{id}/commands?consume=true).
    - Ejecución real en FlightController y amortiguación horizontal (compute_hover_damping).
    """
    from simulation.controllers.drone_supervisor.flight_controller import FlightController

    drone_id = "drone-webots-cmd-test"
    reg_res = client.post(
        "/api/v1/drones",
        json={
            "id": drone_id,
            "name": "Dron Webots Test Bidireccional",
            "model": "Mavic 2 PRO",
            "status": "idle",
            "battery_level": 100.0,
            "current_x": 0.0,
            "current_y": -45.0,
            "current_z": 0.15,
            "current_speed": 0.0,
            "flight_mode": "INIT",
        },
    )
    assert reg_res.status_code == 200

    # Limpiar cola previa si existiera
    client.get(f"/api/v1/drones/{drone_id}/commands?consume=true")

    commands_to_test = [
        ("takeoff", "flying", "TAKEOFF"),
        ("hover", "hovering", "HOVER"),
        ("resume_patrol", "flying", "RESUME_PATROL"),
        ("return_to_home", "returning", "RETURN_TO_HOME"),
        ("land", "landed", "LAND"),
    ]

    for cmd_str, expected_status, expected_norm in commands_to_test:
        res = client.post(
            f"/api/v1/drones/{drone_id}/command",
            json={"command": cmd_str, "params": {}},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["new_status"] == expected_status
        assert body["canonical_command"] == expected_norm

    # El controlador de Webots consulta y consume la cola de comandos
    q_res = client.get(f"/api/v1/drones/{drone_id}/commands?consume=true")
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert q_data["count"] == 5
    assert [c["command"] for c in q_data["commands"]] == [
        "TAKEOFF",
        "HOVER",
        "RESUME_PATROL",
        "RETURN_TO_HOME",
        "LAND",
    ]

    # Una segunda consulta tras consume=true debe venir vacía
    q_empty = client.get(f"/api/v1/drones/{drone_id}/commands?consume=true")
    assert q_empty.status_code == 200
    assert q_empty.json()["count"] == 0

    # Verificar máquina de estados de FlightController ante cada comando remoto
    fc = FlightController(cruise_altitude=6.0)
    # 1. Verificación de estado inicial seguro READY_ON_GROUND (motores apagados en tierra)
    assert fc.state == "READY_ON_GROUND"
    assert "READY_ON_GROUND" in fc.state_description or "en tierra" in fc.state_description.lower()
    # update() sin comando no debe despegar automáticamente
    init_tgt = fc.update(0.0, -45.0, 0.15, sim_time=0.5, battery=100.0)
    assert fc.state == "READY_ON_GROUND"
    assert init_tgt[2] <= 0.20

    # 2. Despegue explícito mediante comando TAKEOFF
    res_takeoff = fc.execute_command("TAKEOFF", (0.0, -45.0, 0.2), sim_time=1.0)
    assert res_takeoff["accepted"] is True
    assert fc.state == "TAKEOFF"

    res_hover = fc.execute_command("HOVER", (0.0, -20.0, 6.0), sim_time=5.0)
    assert res_hover["accepted"] is True
    assert fc.state == "HOVER"
    assert fc.manual_hold is True
    # Verificar que en manual_hold el dron mantiene la posición indefinidamente hasta recibir RESUME_PATROL
    fc.update(0.0, -20.0, 6.0, sim_time=35.0)
    assert fc.state == "HOVER"

    res_resume = fc.execute_command("RESUME_PATROL", (0.0, -20.0, 6.0), sim_time=36.0)
    assert res_resume["accepted"] is True
    assert fc.state == "NAVIGATING"
    assert fc.manual_hold is False

    res_wp = fc.execute_command(
        "SET_WAYPOINT", (0.0, -15.0, 6.0), sim_time=37.0, params={"waypoint_index": 3}
    )
    assert res_wp["accepted"] is True
    assert fc.state == "NAVIGATING"
    assert fc.current_wp_idx == 2  # WP3 (0-based index 2)

    res_rth = fc.execute_command("RETURN_TO_HOME", (0.0, 0.0, 6.0), sim_time=40.0)
    assert res_rth["accepted"] is True
    assert fc.state == "RETURNING"

    res_land = fc.execute_command("LAND", (0.0, -45.0, 6.0), sim_time=50.0)
    assert res_land["accepted"] is True
    assert fc.state == "LANDING"

    # Simular aterrizaje completo y verificar re-despegue desde LANDED
    fc.state = "LANDED"
    res_retakeoff = fc.execute_command("TAKEOFF", (0.0, -45.0, 0.15), sim_time=55.0)
    assert res_retakeoff["accepted"] is True
    assert fc.state == "TAKEOFF"

    # 3. Verificación de Failsafe de Batería Crítica (< 20%)
    fc.state = "NAVIGATING"
    assert fc.battery_critical_active is False
    # Con batería normal no se dispara el failsafe
    fc.update(0.0, -10.0, 6.0, sim_time=60.0, battery=45.0)
    assert fc.state == "NAVIGATING"
    assert fc.battery_critical_active is False

    # Con batería crítica (< 20%), el controlador transiciona automáticamente a RETURNING (RTH)
    tgt_rth = fc.update(0.0, -10.0, 6.0, sim_time=65.0, battery=18.5)
    assert fc.state == "RETURNING"
    assert fc.battery_critical_active is True
    assert "Batería crítica" in fc.state_description
    assert tgt_rth[0] == fc.home_x
    assert tgt_rth[1] == fc.home_y

    # Prioridad absoluta de retorno: RESUME_PATROL debe ser rechazado
    res_resume_blocked = fc.execute_command("RESUME_PATROL", (0.0, -10.0, 6.0), sim_time=66.0)
    assert res_resume_blocked["accepted"] is False
    assert fc.state == "RETURNING"

    # Despegue también debe ser rechazado ante batería crítica
    res_takeoff_blocked = fc.execute_command("TAKEOFF", (0.0, -10.0, 6.0), sim_time=67.0)
    assert res_takeoff_blocked["accepted"] is False
    assert fc.state == "RETURNING"

    # Aterrizaje controlado forzoso por el operador SI debe permitirse (sin conflicto con LAND)
    res_land_allowed = fc.execute_command("LAND", (0.0, -10.0, 6.0), sim_time=68.0)
    assert res_land_allowed["accepted"] is True
    assert fc.state == "LANDING"

    # Verificar amortiguación de velocidad horizontal en HOVER/LANDING
    pitch_corr, roll_corr = fc.compute_hover_damping(
        pos_x=0.0, pos_y=-15.0, target_x=0.0, target_y=-15.0, vx=2.0, vy=0.0, yaw=0.0
    )
    assert pitch_corr > 0.0  # Frena velocidad frontal positiva


def test_semana_9_webots_frame_hybrid_detection(client):
    """
    Verifica que el fotograma real capturado en Webots (simulation/latest_webots_camera_frame.jpg)
    sea procesado por el pipeline híbrido (YOLO + complemento heurístico OpenCV para Webots)
    y detecte el poste de alumbrado público del corredor vial.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    webots_frame_path = repo_root / "simulation" / "latest_webots_camera_frame.jpg"
    assert webots_frame_path.exists()

    frame_bytes = webots_frame_path.read_bytes()
    b64_str = base64.b64encode(frame_bytes).decode("utf-8")

    res = client.post(
        "/api/v1/cameras/frame",
        json={
            "drone_id": "drone-webots-01",
            "image_base64": b64_str,
            "pos_x": 0.0,
            "pos_y": 22.0,
            "pos_z": 6.0,
            "run_detection": True,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["detections_count"] >= 1
    labels = [d["label"] for d in data["detections"]]
    assert "poste_luz" in labels


def test_semana_9_sqlalchemy_base_unification():
    """
    Verifica que app.core.database y backend.app.core.database compartan exactamente
    la misma instancia de módulo y declarative_base(), con las 4 tablas registradas.
    """
    import app.core.database as app_db
    import backend.app.core.database as backend_db

    assert app_db is backend_db
    assert app_db.Base is backend_db.Base
    tables = set(backend_db.Base.metadata.tables.keys())
    assert {"drones", "telemetria", "imagenes", "incidentes"}.issubset(tables)
