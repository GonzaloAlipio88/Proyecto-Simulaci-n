import os
import sys
import time
import math
import base64
from pathlib import Path
import cv2
import numpy as np

# Add local path
script_dir = Path(__file__).resolve().parent
supervisor_dir = script_dir / "controllers" / "drone_supervisor"
sys.path.insert(0, str(supervisor_dir))

from communication import DroneCommunicationClient
from flight_controller import FlightController

def generate_synthetic_scene(t: float, step: int, flight_state: str, wp_idx: int) -> np.ndarray:
    """
    Generates realistic camera perspective frames along the inspection corridor,
    including the ground, road/track, light poles, vegetation patches, and track obstacles.
    """
    h, w = 480, 640
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # Ground: Sandy earth
    img[180:, :] = (85, 120, 150)
    # Sky: Light blue
    img[:180, :] = (230, 200, 140)

    # Road / Track perspective corridor
    pts = np.array([[260, 180], [380, 180], [540, 480], [100, 480]], np.int32)
    cv2.fillPoly(img, [pts], (70, 70, 75))
    # Road center line
    cv2.line(img, (320, 180), (320, 480), (220, 220, 220), 2)

    # Contextual targets based on current waypoint / area
    if wp_idx == 1:
        # TARGET 1: Poste de Luz (Tall vertical pole with lamp head)
        pole_x = 440
        cv2.rectangle(img, (pole_x, 100), (pole_x + 14, 380), (180, 180, 190), -1)
        cv2.rectangle(img, (pole_x - 30, 85), (pole_x + 15, 105), (100, 240, 255), -1)
        cv2.circle(img, (pole_x - 15, 95), 18, (120, 255, 255), -1)

    elif wp_idx == 2:
        # TARGET 2: Vegetación Invasiva (Overgrown bushes spilling over the road)
        bush_pts = np.array([[120, 320], [240, 280], [290, 360], [220, 440], [110, 420]], np.int32)
        cv2.fillPoly(img, [bush_pts], (30, 160, 40))
        cv2.circle(img, (180, 340), 45, (25, 140, 35), -1)
        cv2.circle(img, (240, 370), 38, (35, 180, 50), -1)

    elif wp_idx == 3:
        # TARGET 3: Obstrucción de Vía (Cajas/Obstáculos en el centro de la vía)
        cv2.rectangle(img, (270, 340), (370, 430), (35, 75, 140), -1)
        cv2.rectangle(img, (285, 300), (355, 340), (45, 90, 160), -1)
        cv2.putText(img, "CARGO", (288, 385), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    # HUD overlay with flight state and waypoint
    hud_text = f"ESTADO: {flight_state} | WP: {wp_idx} | T: {t:.1f}s"
    cv2.putText(img, hud_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    return img

def run_test_mission(backend_url: str = "http://127.0.0.1:8000"):
    print("=======================================================================")
    print("  EJECUTANDO MISIÓN DE PRUEBA OFICIAL")
    print("  1. Iniciar en posición conocida (0.0, -45.0, 0.15)")
    print("  2. Despegar a 6.0m")
    print("  3. Ir a Waypoint 1 (0.0, -20.0, 6.0) -> Hover 3s")
    print("  4. Ir a Waypoint 2 (0.0, 5.0, 6.0) -> Hover 3s")
    print("  5. Ir a Waypoint 3 (0.0, 30.0, 6.0) -> Hover 3s")
    print("  6. Regresar a Home (0.0, -45.0, 6.0) -> Hover 2s")
    print("  7. Aterrizar de manera controlada")
    print("=======================================================================")

    comm = DroneCommunicationClient(backend_url=backend_url, drone_id="drone-webots-01")
    nav = FlightController(
        home_pos=(0.0, -45.0, 0.15),
        cruise_altitude=6.0,
        waypoint_tolerance=0.60
    )

    registered = comm.register(name="DJI Mavic 2 Pro (Webots Sim)", model="DJI Mavic 2 Pro Quadrotor")
    if not registered:
        print("[AVISO] No se pudo conectar con el Backend en http://127.0.0.1:8000")
    else:
        print("[OK] Dron registrado correctamente en el Backend.")

    # Starting known position
    current_x = 0.0
    current_y = -45.0
    current_z = 0.15
    current_yaw = 1.5708 # Facing North along the track

    start_wall_time = time.time()
    sim_time = 0.0
    dt = 0.10 # 100ms per simulation step
    step = 0

    states_visited = []

    # Run until mission complete or max 60s
    while sim_time < 60.0 and not (nav.mission_complete and current_z <= 0.20):
        step += 1
        sim_time += dt

        # Update flight controller target
        target_x, target_y, target_z = nav.update(current_x, current_y, current_z, sim_time)
        state = nav.get_state()
        wp_idx = nav.get_current_waypoint_index()

        if state not in states_visited:
            states_visited.append(state)
            print(f"[{sim_time:5.1f}s] Estado: {state:12s} | Target: [{target_x:4.1f}, {target_y:4.1f}, {target_z:4.1f}] | Pos: [{current_x:4.1f}, {current_y:4.1f}, {current_z:4.1f}]")

        # Simulated physical motion towards target with damping
        if state == "TAKEOFF":
            current_z = min(target_z, current_z + 0.35)
            current_speed = 1.8
        elif state in ["NAVIGATING", "RETURNING"]:
            dx = target_x - current_x
            dy = target_y - current_y
            dist_xy = math.hypot(dx, dy)
            step_move = min(dist_xy, 0.45)
            if dist_xy > 0.01:
                current_x += (dx / dist_xy) * step_move
                current_y += (dy / dist_xy) * step_move
                current_yaw = math.atan2(dy, dx)
            # Maintain cruise altitude
            current_z += (target_z - current_z) * 0.2
            current_speed = 2.8
        elif state in ["HOVER", "HOVER_HOME"]:
            # Stationary hover: hold position exactly
            current_x += (target_x - current_x) * 0.1
            current_y += (target_y - current_y) * 0.1
            current_z += (target_z - current_z) * 0.1
            current_speed = 0.05
        elif state == "LANDING":
            # Smooth descent
            current_z = max(0.15, current_z - 0.15)
            current_x += (target_x - current_x) * 0.1
            current_y += (target_y - current_y) * 0.1
            current_speed = 0.6
        elif state == "LANDED":
            current_z = 0.15
            current_speed = 0.0

        # Send telemetry to Backend every step (10 Hz)
        comm.send_telemetry(
            pos_x=current_x,
            pos_y=current_y,
            pos_z=current_z,
            roll=0.01 if current_speed > 0.5 else 0.0,
            pitch=0.04 if current_speed > 0.5 else 0.0,
            yaw=current_yaw,
            speed=current_speed,
            battery=max(20.0, 100.0 - (sim_time * 0.3)),
            flight_mode=state,
            current_waypoint=wp_idx,
            current_mission=nav.mission_name,
            state_description=nav.state_description
        )

        # Transmit camera frames every 4 steps (~2.5 Hz)
        if step % 4 == 0:
            frame = generate_synthetic_scene(sim_time, step, state, wp_idx)
            _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            b64_frame = base64.b64encode(buffer).decode('utf-8')
            comm.send_camera_frame(
                image_base64=b64_frame,
                pos_x=current_x,
                pos_y=current_y,
                pos_z=current_z,
                run_detection=True
            )

        time.sleep(0.05) # Speed up simulation run for testing

    print("=======================================================================")
    print(f"  MISIÓN FINALIZADA EN {sim_time:.1f}s")
    print(f"  Estados completados: {' -> '.join(states_visited)}")
    print(f"  Posición final: [{current_x:.2f}, {current_y:.2f}, {current_z:.2f}m]")
    print(f"  Misión cumplida: {nav.mission_complete}")
    print("=======================================================================")

if __name__ == "__main__":
    run_test_mission()
