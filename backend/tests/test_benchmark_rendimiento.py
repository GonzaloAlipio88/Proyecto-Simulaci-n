"""
Prueba y Benchmark de Rendimiento Real - Semana 11
Mide empíricamente:
- Tiempos de respuesta de endpoints REST (/health, /drones, /deteccion/status, /incidentes/stats, etc.)
- Latencia de escrituras y lecturas en SQLite
- Tiempos de inferencia y FPS: YOLOv8n (CPU), OpenCV Heurístico e Ingesta completa de fotograma
- Continuidad de telemetría y estabilidad del controlador de vuelo (1,000 ciclos)
Genera el reporte JSON en docs/BENCHMARK_SEMANA_11_METRICAS.json
"""
import time
import json
import base64
import statistics
from pathlib import Path
import pytest
import numpy as np
import cv2
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.modules.deteccion.yolo_adapter import YOLODetector
from backend.app.modules.deteccion.mock_detector import HeuristicDetector
from flight_controller import FlightController

@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_ejecutar_benchmark_rendimiento_semana_11(client):
    repo_root = Path(__file__).resolve().parent.parent.parent
    results = {}

    print("\n" + "=" * 80)
    print("MEDICIONES DE RENDIMIENTO REALES — SEMANA 11")
    print("=" * 80)

    # 1. LATENCIA DE ENDPOINTS REST
    print("\n[1/4] Midiendo latencia de Endpoints REST (30 llamadas cada uno)...")
    endpoints_to_measure = [
        ("GET /health", "GET", "/health", None),
        ("GET /api/v1/drones", "GET", "/api/v1/drones", None),
        ("GET /api/v1/deteccion/status", "GET", "/api/v1/deteccion/status", None),
        ("GET /api/v1/deteccion/threshold", "GET", "/api/v1/deteccion/threshold", None),
        ("GET /api/v1/incidentes/stats", "GET", "/api/v1/incidentes/stats", None),
        ("PUT /api/v1/deteccion/threshold", "PUT", "/api/v1/deteccion/threshold", {"threshold": 0.28}),
    ]

    rest_metrics = {}
    for label, method, url, body in endpoints_to_measure:
        times = []
        for _ in range(30):
            t0 = time.perf_counter()
            if method == "GET":
                res = client.get(url)
            elif method == "PUT":
                res = client.put(url, json=body)
            t1 = time.perf_counter()
            assert res.status_code == 200
            times.append((t1 - t0) * 1000.0)

        sorted_t = sorted(times)
        p50 = statistics.median(sorted_t)
        p95 = sorted_t[int(len(sorted_t) * 0.95)]
        mean_t = statistics.mean(sorted_t)
        rest_metrics[label] = {
            "mean_ms": round(mean_t, 2),
            "p50_ms": round(p50, 2),
            "p95_ms": round(p95, 2),
            "min_ms": round(min(sorted_t), 2),
            "max_ms": round(max(sorted_t), 2),
        }
        print(f" -> {label:35s}: Promedio={mean_t:5.2f}ms | P50={p50:5.2f}ms | P95={p95:5.2f}ms")

    # Restaurar umbral por defecto
    client.put("/api/v1/deteccion/threshold", json={"threshold": 0.25})
    results["rest_endpoints"] = rest_metrics

    # 2. OPERACIONES DE BASE DE DATOS (ESCRITURAS SQLITE)
    print("\n[2/4] Midiendo latencia de operaciones en SQLite...")
    # Registrar dron
    client.post("/api/v1/drones/register", json={
        "id": "drone-bench-01",
        "name": "Dron Benchmark",
        "model": "Mavic 2 PRO",
        "status": "flying"
    })

    incident_write_times = []
    for i in range(25):
        t0 = time.perf_counter()
        res = client.post("/api/v1/incidentes?allow_duplicate=true", json={
            "drone_id": "drone-bench-01",
            "tipo": "obstruccion_via",
            "severidad": "media",
            "descripcion": f"Incidente benchmark #{i}",
            "pos_x": float(i % 10),
            "pos_y": float(-30 + i),
            "pos_z": 6.0,
            "confidence": 0.85
        })
        t1 = time.perf_counter()
        assert res.status_code in (200, 201)
        incident_write_times.append((t1 - t0) * 1000.0)

    telemetry_write_times = []
    for i in range(25):
        t0 = time.perf_counter()
        res = client.post("/api/v1/telemetria", json={
            "drone_id": "drone-bench-01",
            "pos_x": 0.0,
            "pos_y": -45.0 + i,
            "pos_z": 6.0,
            "roll": 0.01,
            "pitch": -0.02,
            "yaw": 0.0,
            "speed": 4.5,
            "battery": 95.0 - (i * 0.1),
            "flight_mode": "NAVIGATING"
        })
        t1 = time.perf_counter()
        assert res.status_code == 200
        telemetry_write_times.append((t1 - t0) * 1000.0)

    db_metrics = {
        "incident_create_ms": {
            "mean_ms": round(statistics.mean(incident_write_times), 2),
            "p50_ms": round(statistics.median(incident_write_times), 2),
            "p95_ms": round(sorted(incident_write_times)[int(len(incident_write_times) * 0.95)], 2),
        },
        "telemetry_ingest_ms": {
            "mean_ms": round(statistics.mean(telemetry_write_times), 2),
            "p50_ms": round(statistics.median(telemetry_write_times), 2),
            "p95_ms": round(sorted(telemetry_write_times)[int(len(telemetry_write_times) * 0.95)], 2),
        }
    }
    print(f" -> Inserción de incidente en SQLite:   Promedio={db_metrics['incident_create_ms']['mean_ms']}ms | P95={db_metrics['incident_create_ms']['p95_ms']}ms")
    print(f" -> Ingesta de telemetría en SQLite:  Promedio={db_metrics['telemetry_ingest_ms']['mean_ms']}ms | P95={db_metrics['telemetry_ingest_ms']['p95_ms']}ms")
    results["database_performance"] = db_metrics

    # 3. VISIÓN ARTIFICIAL (YOLO vs HEURÍSTICO vs INGESTA FOTOGRAMA)
    print("\n[3/4] Midiendo Visión Artificial sobre fotograma real de Webots...")
    frame_path = repo_root / "simulation" / "latest_webots_camera_frame.jpg"
    assert frame_path.exists(), f"No existe {frame_path}"
    real_img = cv2.imread(str(frame_path))
    h, w = real_img.shape[:2]

    # A. Heurístico OpenCV
    heur_detector = HeuristicDetector()
    heur_times = []
    heur_count = 0
    for _ in range(25):
        t0 = time.perf_counter()
        dets = heur_detector.analyze(real_img, confidence_threshold=0.25)
        t1 = time.perf_counter()
        heur_times.append((t1 - t0) * 1000.0)
        heur_count = len(dets)

    heur_mean = statistics.mean(heur_times)
    heur_p50 = statistics.median(heur_times)
    heur_p95 = sorted(heur_times)[int(len(heur_times) * 0.95)]
    heur_fps = 1000.0 / heur_mean if heur_mean > 0 else 0
    print(f" -> Heurístico OpenCV: Promedio={heur_mean:5.2f}ms | P50={heur_p50:5.2f}ms | P95={heur_p95:5.2f}ms | FPS={heur_fps:5.1f} | Detecciones={heur_count}")

    # B. YOLOv8n (CPU)
    yolo_weights = repo_root / "backend" / "storage" / "weights" / "yolov8n.pt"
    if not yolo_weights.exists():
        yolo_weights = repo_root / "storage" / "weights" / "best.pt"
    yolo_metrics = None
    if yolo_weights.exists():
        yolo_det = YOLODetector(weights_path=str(yolo_weights), device="cpu")
        if yolo_det.load_model():
            yolo_times = []
            yolo_count = 0
            yolo_det.analyze(real_img, confidence_threshold=0.25) # warmup
            for _ in range(20):
                t0 = time.perf_counter()
                dets = yolo_det.analyze(real_img, confidence_threshold=0.25)
                t1 = time.perf_counter()
                yolo_times.append((t1 - t0) * 1000.0)
                yolo_count = len(dets)
            y_mean = statistics.mean(yolo_times)
            y_p50 = statistics.median(yolo_times)
            y_p95 = sorted(yolo_times)[int(len(yolo_times) * 0.95)]
            y_fps = 1000.0 / y_mean if y_mean > 0 else 0
            yolo_metrics = {
                "mean_ms": round(y_mean, 2),
                "p50_ms": round(y_p50, 2),
                "p95_ms": round(y_p95, 2),
                "fps": round(y_fps, 1),
                "detections": yolo_count,
                "mode": yolo_det.mode
            }
            print(f" -> YOLOv8n (CPU):     Promedio={y_mean:5.2f}ms | P50={y_p50:5.2f}ms | P95={y_p95:5.2f}ms | FPS={y_fps:5.1f} | Detecciones={yolo_count} ({yolo_det.mode})")

    # C. Ingesta Completa de Fotograma HTTP
    b64_str = base64.b64encode(frame_path.read_bytes()).decode("utf-8")
    ingest_times = []
    for _ in range(15):
        t0 = time.perf_counter()
        res = client.post("/api/v1/cameras/frame", json={
            "drone_id": "drone-bench-01",
            "image_base64": b64_str,
            "pos_x": 0.0,
            "pos_y": -15.0,
            "pos_z": 6.0,
            "run_detection": True
        })
        t1 = time.perf_counter()
        assert res.status_code == 200
        ingest_times.append((t1 - t0) * 1000.0)

    ingest_mean = statistics.mean(ingest_times)
    ingest_p50 = statistics.median(ingest_times)
    ingest_p95 = sorted(ingest_times)[int(len(ingest_times) * 0.95)]
    ingest_fps = 1000.0 / ingest_mean if ingest_mean > 0 else 0
    print(f" -> Pipeline Ingesta:  Promedio={ingest_mean:5.2f}ms | P50={ingest_p50:5.2f}ms | P95={ingest_p95:5.2f}ms | FPS Efectivo={ingest_fps:5.1f}")

    results["vision_performance"] = {
        "image_resolution": f"{w}x{h}",
        "opencv_heuristic": {
            "mean_ms": round(heur_mean, 2),
            "p50_ms": round(heur_p50, 2),
            "p95_ms": round(heur_p95, 2),
            "fps": round(heur_fps, 1),
            "detections": heur_count
        },
        "yolo_cpu": yolo_metrics,
        "full_camera_ingest_pipeline": {
            "mean_ms": round(ingest_mean, 2),
            "p50_ms": round(ingest_p50, 2),
            "p95_ms": round(ingest_p95, 2),
            "fps": round(ingest_fps, 1)
        }
    }

    # 4. SIMULACIÓN Y CONTINUIDAD DE TELEMETRÍA (1,000 CICLOS)
    print("\n[4/4] Prueba de Resistencia y Estabilidad (1,000 ciclos de simulación continuos)...")
    fc = FlightController(cruise_altitude=6.0, home_pos=(0.0, -45.0, 0.15))
    states_visited = set()
    t_start = time.perf_counter()
    errors_count = 0

    # 100 ciclos en tierra
    for i in range(100):
        tgt = fc.update(0.0, -45.0, 0.15, sim_time=i * 0.05, battery=100.0)
        states_visited.add(fc.state)
        if fc.state != "READY_ON_GROUND":
            errors_count += 1

    # Despegue explícito
    fc.execute_command("TAKEOFF", (0.0, -45.0, 0.15), sim_time=5.0)
    states_visited.add(fc.state)

    # Ascenso
    z = 0.15
    for i in range(100, 200):
        z = min(6.0, z + 0.1)
        tgt = fc.update(0.0, -45.0, z, sim_time=i * 0.05, battery=99.0)
        states_visited.add(fc.state)

    # Navegación y patrullaje
    curr_y = -45.0
    for i in range(200, 800):
        if fc.state == "NAVIGATING":
            curr_y = min(30.0, curr_y + 0.25)
        tgt = fc.update(0.0, curr_y, 6.0, sim_time=i * 0.05, battery=90.0 - (i * 0.02))
        states_visited.add(fc.state)

    # Failsafe de batería crítica (<20%)
    fc.update(0.0, curr_y, 6.0, sim_time=801 * 0.05, battery=18.0)
    states_visited.add(fc.state)

    # Retorno y aterrizaje en base
    for i in range(802, 1000):
        curr_y = max(-45.0, curr_y - 0.4)
        z_curr = 6.0 if curr_y > -44.0 else max(0.12, 6.0 - (i - 900) * 0.08)
        tgt = fc.update(0.0, curr_y, z_curr, sim_time=i * 0.05, battery=17.0)
        states_visited.add(fc.state)

    t_elapsed = time.perf_counter() - t_start
    avg_cycle_ms = (t_elapsed / 1000.0) * 1000.0
    throughput_hz = 1000.0 / t_elapsed

    print(f" -> 1,000 ciclos en {t_elapsed:.4f}s | {avg_cycle_ms:.4f}ms/ciclo ({throughput_hz:.0f} Hz)")
    print(f" -> Estados recorridos: {sorted(list(states_visited))}")
    assert errors_count == 0

    results["simulation_endurance"] = {
        "total_cycles": 1000,
        "elapsed_seconds": round(t_elapsed, 4),
        "avg_cycle_ms": round(avg_cycle_ms, 4),
        "frequency_hz": round(throughput_hz, 1),
        "states_visited": sorted(list(states_visited)),
        "errors_count": errors_count,
        "status": "PASS"
    }

    # Guardar métricas en docs/BENCHMARK_SEMANA_11_METRICAS.json
    metrics_path = repo_root / "docs" / "BENCHMARK_SEMANA_11_METRICAS.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n -> Resultados guardados en: {metrics_path}")
    print("=" * 80)
