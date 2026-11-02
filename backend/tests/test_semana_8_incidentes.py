import time
import math
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch
from sqlalchemy.exc import OperationalError

from backend.app.main import app
from backend.app.core.database import SessionLocal, get_db
from backend.app.models.incidente import Incidente
from backend.app.models.imagen import ImageRecord
from backend.app.schemas.incidente import IncidenteCreate


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────────────────────
# 1. Persistencia y Almacenamiento en SQLite
# ──────────────────────────────────────────────────────────────────────────────

def test_incidente_creation_and_persistence(client, db_session):
    """
    Verifica que un incidente válido se almacene correctamente en la base de datos SQLite
    con todos sus campos (id, drone_id, tipo, severidad, descripcion, ubicación 3D,
    coordenadas_tipo, confianza, estado, timestamp) y que esté disponible tras la llamada.
    """
    payload = {
        "drone_id": "drone-sim-persist-01",
        "tipo": "obstruccion_via",
        "severidad": "critica",
        "descripcion": "Roca de gran tamaño bloqueando el riel izquierdo en km 12.4",
        "pos_x": 12.4,
        "pos_y": 3.8,
        "pos_z": 5.2,
        "coordenadas_tipo": "simulacion_webots",
        "confidence": 0.94,
        "estado": "reportado"
    }

    res = client.post("/api/v1/incidentes?allow_duplicate=true", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["id"] is not None
    assert data["drone_id"] == "drone-sim-persist-01"
    assert data["tipo"] == "obstruccion_via"
    assert data["severidad"] == "critica"
    assert data["descripcion"] == payload["descripcion"]
    assert data["pos_x"] == 12.4
    assert data["pos_y"] == 3.8
    assert data["pos_z"] == 5.2
    assert data["coordenadas_tipo"] == "simulacion_webots"
    assert data["confidence"] == 0.94
    assert data["estado"] == "reportado"
    assert data["timestamp"] is not None

    # Comprobación directa en SQLite con una sesión fresca
    inc_db = db_session.query(Incidente).filter(Incidente.id == data["id"]).first()
    assert inc_db is not None
    assert inc_db.drone_id == "drone-sim-persist-01"
    assert inc_db.tipo == "obstruccion_via"
    assert inc_db.pos_x == 12.4


def test_incidente_persistence_across_sessions(client):
    """
    Verifica que los datos sigan disponibles en SQLite simulando el cierre y apertura
    de sesiones de base de datos (reinicio de conexiones).
    """
    payload = {
        "drone_id": "drone-sim-persist-02",
        "tipo": "vegetacion_invasiva",
        "severidad": "alta",
        "descripcion": "Ramas de árbol invadiendo gálibo superior en km 8.1",
        "pos_x": 8.1,
        "pos_y": -2.3,
        "pos_z": 7.0,
        "confidence": 0.87,
        "estado": "reportado"
    }

    res = client.post("/api/v1/incidentes?allow_duplicate=true", json=payload)
    assert res.status_code == 200
    created_id = res.json()["id"]

    # Simular nueva sesión independiente
    fresh_session = SessionLocal()
    try:
        record = fresh_session.query(Incidente).filter(Incidente.id == created_id).first()
        assert record is not None
        assert record.id == created_id
        assert record.tipo == "vegetacion_invasiva"
        assert record.severidad == "alta"
        assert record.pos_y == -2.3
    finally:
        fresh_session.close()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Consultas y Filtros Múltiples (Listado, Paginación y Búsqueda)
# ──────────────────────────────────────────────────────────────────────────────

def test_incidente_query_filters(client):
    """
    Verifica que el endpoint GET /incidentes permita filtrar de forma coherente
    por tipo, severidad, estado, drone_id, confianza mínima y búsqueda libre.
    """
    unique_drone = f"drone-filter-{int(time.time() * 1000)}"

    # Crear 3 incidentes distintos
    client.post("/api/v1/incidentes?allow_duplicate=true", json={
        "drone_id": unique_drone,
        "tipo": "poste_luz",
        "severidad": "baja",
        "descripcion": "Poste de alumbrado en margen de vía km 1.0",
        "pos_x": 1.0, "pos_y": 2.0, "pos_z": 3.0,
        "confidence": 0.65, "estado": "reportado"
    })
    client.post("/api/v1/incidentes?allow_duplicate=true", json={
        "drone_id": unique_drone,
        "tipo": "vegetacion_invasiva",
        "severidad": "alta",
        "descripcion": "Maleza cubriendo rieles en km 2.0",
        "pos_x": 2.0, "pos_y": 2.0, "pos_z": 3.0,
        "confidence": 0.89, "estado": "en_revision"
    })
    client.post("/api/v1/incidentes?allow_duplicate=true", json={
        "drone_id": unique_drone,
        "tipo": "obstruccion_via",
        "severidad": "critica",
        "descripcion": "Escombros metálicos en km 3.0",
        "pos_x": 3.0, "pos_y": 2.0, "pos_z": 3.0,
        "confidence": 0.95, "estado": "atendido"
    })

    # Filtro por drone_id
    res_drone = client.get(f"/api/v1/incidentes?drone_id={unique_drone}")
    assert res_drone.status_code == 200
    drone_items = res_drone.json()
    assert len(drone_items) == 3

    # Filtro por tipo
    res_tipo = client.get(f"/api/v1/incidentes?drone_id={unique_drone}&tipo=poste_luz")
    assert res_tipo.status_code == 200
    assert len(res_tipo.json()) == 1
    assert res_tipo.json()[0]["tipo"] == "poste_luz"

    # Filtro por severidad
    res_sev = client.get(f"/api/v1/incidentes?drone_id={unique_drone}&severidad=critica")
    assert res_sev.status_code == 200
    assert len(res_sev.json()) == 1
    assert res_sev.json()[0]["severidad"] == "critica"

    # Filtro por estado
    res_est = client.get(f"/api/v1/incidentes?drone_id={unique_drone}&estado=atendido")
    assert res_est.status_code == 200
    assert len(res_est.json()) == 1
    assert res_est.json()[0]["estado"] == "atendido"

    # Filtro por confianza mínima
    res_conf = client.get(f"/api/v1/incidentes?drone_id={unique_drone}&min_confidence=0.85")
    assert res_conf.status_code == 200
    assert len(res_conf.json()) == 2  # 0.89 y 0.95

    # Búsqueda de texto libre en descripción
    res_search = client.get(f"/api/v1/incidentes?drone_id={unique_drone}&search=Escombros")
    assert res_search.status_code == 200
    assert len(res_search.json()) == 1
    assert "Escombros" in res_search.json()[0]["descripcion"]

    # Paginación (skip y limit)
    res_page = client.get(f"/api/v1/incidentes?drone_id={unique_drone}&skip=1&limit=1")
    assert res_page.status_code == 200
    assert len(res_page.json()) == 1


def test_incidente_get_by_id_and_not_found(client):
    """
    Verifica la consulta individual por ID y la gestión del error 404 ante ID inexistente.
    """
    # 1. Crear un incidente
    res = client.post("/api/v1/incidentes?allow_duplicate=true", json={
        "drone_id": "drone-sim-id-test",
        "tipo": "poste_luz",
        "severidad": "baja",
        "descripcion": "Poste km 5",
        "pos_x": 5.0, "pos_y": 1.0, "pos_z": 2.0,
        "confidence": 0.70
    })
    assert res.status_code == 200
    inc_id = res.json()["id"]

    # 2. Consultar por ID existente
    res_get = client.get(f"/api/v1/incidentes/{inc_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == inc_id

    # 3. Consultar por ID inexistente
    res_404 = client.get("/api/v1/incidentes/99999999")
    assert res_404.status_code == 404
    assert "no encontrado" in res_404.json()["detail"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Actualización y Ciclo de Vida (PATCH)
# ──────────────────────────────────────────────────────────────────────────────

def test_incidente_update_lifecycle(client):
    """
    Verifica la actualización controlada de estado, severidad y descripción (PATCH).
    """
    # 1. Crear incidente
    res = client.post("/api/v1/incidentes?allow_duplicate=true", json={
        "drone_id": "drone-sim-patch",
        "tipo": "obstruccion_via",
        "severidad": "media",
        "descripcion": "Objeto sin identificar en calzada",
        "confidence": 0.75,
        "estado": "reportado"
    })
    inc_id = res.json()["id"]

    # 2. Pasar a en_revision
    res_patch1 = client.patch(f"/api/v1/incidentes/{inc_id}", json={
        "estado": "en_revision",
        "severidad": "alta",
        "descripcion": "Confirmado: neumático abandonado en zona de riel"
    })
    assert res_patch1.status_code == 200
    data1 = res_patch1.json()
    assert data1["estado"] == "en_revision"
    assert data1["severidad"] == "alta"
    assert "Confirmado" in data1["descripcion"]

    # 3. Pasar a atendido
    res_patch2 = client.patch(f"/api/v1/incidentes/{inc_id}", json={
        "estado": "atendido"
    })
    assert res_patch2.status_code == 200
    assert res_patch2.json()["estado"] == "atendido"

    # 4. Actualizar ID inexistente
    res_patch_404 = client.patch("/api/v1/incidentes/99999999", json={"estado": "descartado"})
    assert res_patch_404.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# 4. Eliminación de Incidentes (DELETE)
# ──────────────────────────────────────────────────────────────────────────────

def test_incidente_deletion(client, db_session):
    """
    Verifica la eliminación permanente de un incidente y el retorno 404 posterior.
    """
    # 1. Crear incidente
    res = client.post("/api/v1/incidentes?allow_duplicate=true", json={
        "drone_id": "drone-sim-delete",
        "tipo": "otro",
        "severidad": "baja",
        "descripcion": "Detección espuria que debe ser eliminada",
        "confidence": 0.51
    })
    inc_id = res.json()["id"]

    # 2. Eliminarlo
    res_del = client.delete(f"/api/v1/incidentes/{inc_id}")
    assert res_del.status_code == 200
    del_data = res_del.json()
    assert del_data["success"] is True
    assert del_data["id"] == inc_id

    # 3. Comprobar que ya no existe por API
    res_check = client.get(f"/api/v1/incidentes/{inc_id}")
    assert res_check.status_code == 404

    # 4. Comprobar directamente en SQLite
    inc_in_db = db_session.query(Incidente).filter(Incidente.id == inc_id).first()
    assert inc_in_db is None

    # 5. Eliminar ID inexistente
    res_del_404 = client.delete("/api/v1/incidentes/99999999")
    assert res_del_404.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# 5. Deduplicación Espacio-Temporal en Fotogramas Consecutivos
# ──────────────────────────────────────────────────────────────────────────────

def test_deduplication_rule_identical_frames(client, db_session):
    """
    Verifica que al recibir múltiples reportes idénticos en fotogramas sucesivos
    (mismo dron, misma anomalía, posición dentro del radio de 2.5m y en menos de 5s),
    el sistema NO genere múltiples incidentes duplicados en SQLite.
    """
    drone_name = f"drone-dedup-{int(time.time() * 1000)}"
    initial_payload = {
        "drone_id": drone_name,
        "tipo": "obstruccion_via",
        "severidad": "alta",
        "descripcion": "Obstáculo en riel detectado por visión en fotograma 1",
        "pos_x": 100.0,
        "pos_y": 50.0,
        "pos_z": 5.0,
        "confidence": 0.82
    }

    # Primer envío: debe crear un nuevo incidente
    res1 = client.post("/api/v1/incidentes", json=initial_payload)
    assert res1.status_code == 200
    first_id = res1.json()["id"]

    # Segundo envío inmediato (fotograma siguiente, posición casi idéntica a 0.2m)
    second_payload = dict(initial_payload)
    second_payload["pos_x"] = 100.1  # desplazamiento insignificante de 0.1m
    second_payload["pos_y"] = 50.1
    second_payload["confidence"] = 0.89  # mayor confianza

    res2 = client.post("/api/v1/incidentes", json=second_payload)
    assert res2.status_code == 200
    second_id = res2.json()["id"]

    # Debe retornar el mismo ID (reutilizado por deduplicación)
    assert first_id == second_id
    assert res2.json()["confidence"] == 0.89

    # Verificar en SQLite que sólo existe 1 registro para este dron y tipo
    count = db_session.query(Incidente).filter(
        Incidente.drone_id == drone_name,
        Incidente.tipo == "obstruccion_via"
    ).count()
    assert count == 1

    # Tercer envío forzando allow_duplicate=true: debe crear un nuevo registro
    res3 = client.post("/api/v1/incidentes?allow_duplicate=true", json=second_payload)
    assert res3.status_code == 200
    third_id = res3.json()["id"]
    assert third_id != first_id

    # Cuarto envío a posición distante (> 2.5m, por ejemplo a 20m): no es duplicado
    distant_payload = dict(initial_payload)
    distant_payload["pos_x"] = 125.0
    distant_payload["pos_y"] = 75.0
    res4 = client.post("/api/v1/incidentes", json=distant_payload)
    assert res4.status_code == 200
    fourth_id = res4.json()["id"]
    assert fourth_id != first_id
    assert fourth_id != third_id


# ──────────────────────────────────────────────────────────────────────────────
# 6. Validación Estricta de Datos Inválidos
# ──────────────────────────────────────────────────────────────────────────────

def test_invalid_data_validation(client):
    """
    Verifica que el backend valide estrictamente los datos de entrada y rechace
    valores inválidos con HTTP 422 sin generar fallos internos.
    """
    # 1. Tipo de anomalía no permitido
    res_tipo = client.post("/api/v1/incidentes", json={
        "drone_id": "drone-valid",
        "tipo": "ovni_extraterrestre",
        "descripcion": "Descripción válida",
        "confidence": 0.80
    })
    assert res_tipo.status_code == 422

    # 2. Severidad no permitida
    res_sev = client.post("/api/v1/incidentes", json={
        "drone_id": "drone-valid",
        "tipo": "poste_luz",
        "severidad": "catastrofica_extrema",
        "descripcion": "Descripción válida",
        "confidence": 0.80
    })
    assert res_sev.status_code == 422

    # 3. Confianza fuera de rango (< 0.0 o > 1.0)
    res_conf_high = client.post("/api/v1/incidentes", json={
        "drone_id": "drone-valid",
        "tipo": "poste_luz",
        "descripcion": "Descripción válida",
        "confidence": 1.50
    })
    assert res_conf_high.status_code == 422

    res_conf_low = client.post("/api/v1/incidentes", json={
        "drone_id": "drone-valid",
        "tipo": "poste_luz",
        "descripcion": "Descripción válida",
        "confidence": -0.20
    })
    assert res_conf_low.status_code == 422

    # 4. Identificador de dron vacío
    res_drone_empty = client.post("/api/v1/incidentes", json={
        "drone_id": "   ",
        "tipo": "poste_luz",
        "descripcion": "Descripción válida",
        "confidence": 0.80
    })
    assert res_drone_empty.status_code == 422

    # 5. Descripción vacía o menor a 3 caracteres
    res_desc_empty = client.post("/api/v1/incidentes", json={
        "drone_id": "drone-valid",
        "tipo": "poste_luz",
        "descripcion": "  ",
        "confidence": 0.80
    })
    assert res_desc_empty.status_code == 422

    # 6. Coordenadas no numéricas enviadas por JSON
    res_coord_str = client.post("/api/v1/incidentes", json={
        "drone_id": "drone-valid",
        "tipo": "poste_luz",
        "descripcion": "Descripción válida",
        "confidence": 0.80,
        "pos_x": "coordenada_invalida_no_numerica"
    })
    assert res_coord_str.status_code == 422

    # 7. Validación directa de Pydantic rechazando NaN e Inf
    with pytest.raises(ValueError, match="números finitos válidos"):
        IncidenteCreate(
            drone_id="drone-valid",
            tipo="poste_luz",
            descripcion="Descripción válida",
            confidence=0.80,
            pos_x=float("nan")
        )

    with pytest.raises(ValueError, match="números finitos válidos"):
        IncidenteCreate(
            drone_id="drone-valid",
            tipo="poste_luz",
            descripcion="Descripción válida",
            confidence=0.80,
            pos_y=float("inf")
        )


# ──────────────────────────────────────────────────────────────────────────────
# 7. Resiliencia y Manejo Seguro de Errores de Base de Datos
# ──────────────────────────────────────────────────────────────────────────────

def test_database_error_handling_resilience(client):
    """
    Verifica que ante errores inesperados o excepciones de la base de datos,
    el backend gestione el error de forma controlada (HTTP 500) y continúe
    operando con normalidad sin detener el proceso del servidor.
    """
    with patch("backend.app.api.v1.endpoints.incidentes.incidente_service.create_incidente") as mock_create:
        mock_create.side_effect = OperationalError("database is locked", {}, None)

        res = client.post("/api/v1/incidentes", json={
            "drone_id": "drone-resilience",
            "tipo": "poste_luz",
            "descripcion": "Prueba de resiliencia ante fallo de BD",
            "confidence": 0.80
        })
        # Debe capturarse y responder con error controlado 500
        assert res.status_code == 500
        assert "base de datos" in res.json()["detail"].lower()

    # Tras el fallo simulado, el backend sigue completamente operativo
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "online"



# ──────────────────────────────────────────────────────────────────────────────
# 8. Vinculación y Consulta de Fotografías de Incidentes
# ──────────────────────────────────────────────────────────────────────────────

def test_incidente_image_linking_and_retrieval(client, db_session):
    """
    Verifica la vinculación de imágenes registradas con el incidente y los endpoints
    de consulta de imagen asociada (GET /incidentes/{id}/imagen).
    """
    # 1. Crear un registro de imagen en SQLite
    img_record = ImageRecord(
        drone_id="drone-photo-test",
        filename="test_incident_photo.jpg",
        file_path="storage/images/test_incident_photo.jpg",
        captured_at=datetime.utcnow(),
        pos_x=15.0, pos_y=8.0, pos_z=6.0,
        has_detections=True,
        detection_count=1
    )
    db_session.add(img_record)
    db_session.commit()
    db_session.refresh(img_record)

    # 2. Crear incidente vinculado a esa imagen
    res_inc = client.post("/api/v1/incidentes?allow_duplicate=true", json={
        "drone_id": "drone-photo-test",
        "tipo": "vegetacion_invasiva",
        "severidad": "alta",
        "descripcion": "Vegetación vinculada a imagen fotográfica",
        "pos_x": 15.0, "pos_y": 8.0, "pos_z": 6.0,
        "confidence": 0.91,
        "imagen_id": img_record.id
    })
    assert res_inc.status_code == 200
    inc_data = res_inc.json()
    assert inc_data["imagen_id"] == img_record.id
    assert inc_data["imagen_url"] == f"/api/v1/imagenes/{img_record.id}"

    # 3. Consultar metadata de imagen asociada al incidente
    res_img = client.get(f"/api/v1/incidentes/{inc_data['id']}/imagen")
    assert res_img.status_code == 200
    img_meta = res_img.json()
    assert img_meta["image_id"] == img_record.id
    assert img_meta["filename"] == "test_incident_photo.jpg"

    # 4. Consultar imagen para un incidente que NO tiene imagen asociada
    res_no_img_inc = client.post("/api/v1/incidentes?allow_duplicate=true", json={
        "drone_id": "drone-photo-test",
        "tipo": "poste_luz",
        "descripcion": "Incidente sin imagen asociada",
        "confidence": 0.70
    })
    no_img_id = res_no_img_inc.json()["id"]

    res_no_img = client.get(f"/api/v1/incidentes/{no_img_id}/imagen")
    assert res_no_img.status_code == 404
    assert "no tiene una imagen asociada" in res_no_img.json()["detail"].lower()


# ──────────────────────────────────────────────────────────────────────────────
# 9. Métricas y Estadísticas de Incidentes (GET /stats)
# ──────────────────────────────────────────────────────────────────────────────

def test_incident_stats_endpoint(client):
    """
    Verifica que el endpoint GET /incidentes/stats devuelva estadísticas coherentes:
    totales, distribución por tipo, severidad, estado y confianza promedio.
    """
    res = client.get("/api/v1/incidentes/stats")
    assert res.status_code == 200
    stats = res.json()

    assert "total_incidentes" in stats
    assert isinstance(stats["total_incidentes"], int)
    assert stats["total_incidentes"] >= 0

    assert "por_tipo" in stats
    assert isinstance(stats["por_tipo"], dict)

    assert "por_severidad" in stats
    assert isinstance(stats["por_severidad"], dict)

    assert "por_estado" in stats
    assert isinstance(stats["por_estado"], dict)

    assert "con_imagen" in stats
    assert "sin_imagen" in stats
    assert "confianza_promedio" in stats
    assert isinstance(stats["confianza_promedio"], float)


# ──────────────────────────────────────────────────────────────────────────────
# 10. Notificación en Tiempo Real vía WebSocket
# ──────────────────────────────────────────────────────────────────────────────

def test_websocket_incident_notifications(client):
    """
    Verifica que al registrar un nuevo incidente, se difunda un mensaje WebSocket
    de tipo 'incident' con el payload completo.
    """
    with client.websocket_connect("/ws") as websocket:
        ack = websocket.receive_json()
        assert ack["type"] == "connection_ack"

        # Crear incidente vía HTTP mientras WebSocket está conectado
        unique_desc = f"Incidente WebSocket test {time.time()}"
        res = client.post("/api/v1/incidentes?allow_duplicate=true", json={
            "drone_id": "drone-ws-test",
            "tipo": "obstruccion_via",
            "severidad": "critica",
            "descripcion": unique_desc,
            "confidence": 0.96
        })
        assert res.status_code == 200
        created_id = res.json()["id"]

        # Recibir mensaje difundido por WebSocket
        ws_msg = websocket.receive_json()
        assert ws_msg["type"] == "incident"
        payload = ws_msg["data"]
        assert payload["id"] == created_id
        assert payload["drone_id"] == "drone-ws-test"
        assert payload["tipo"] == "obstruccion_via"
        assert payload["descripcion"] == unique_desc
