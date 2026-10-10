import os
import sys
import math
import base64
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
import numpy as np

logger = logging.getLogger("drone_supervisor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# --------------------------------------------------------------------------
# Cross-platform Webots library resolution
# Windows: looks for Controller.dll
# Linux/macOS (Webots Cloud): WEBOTS_HOME env var must be set, or
#   the controller Python path is already injected by Webots itself.
# --------------------------------------------------------------------------
_platform = sys.platform

if _platform == "win32":
    _win_candidates = [
        os.environ.get("WEBOTS_HOME", ""),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Webots"),
        r"C:\Program Files\Webots",
    ]
    webots_home = next(
        (c for c in _win_candidates
         if c and os.path.exists(os.path.join(c, "lib", "controller", "Controller.dll"))),
        None
    )
    if webots_home:
        os.environ["WEBOTS_HOME"] = webots_home
        lib_ctrl = os.path.join(webots_home, "lib", "controller")
        mingw_bin = os.path.join(webots_home, "msys64", "mingw64", "bin")
        if hasattr(os, "add_dll_directory"):
            for _d in [lib_ctrl, mingw_bin]:
                if os.path.exists(_d):
                    os.add_dll_directory(_d)
        for _py_folder in ["python", "python312", "python311", "python310"]:
            _wpy = os.path.join(lib_ctrl, _py_folder)
            if os.path.exists(_wpy) and _wpy not in sys.path:
                sys.path.insert(0, _wpy)
                break
else:
    # Linux/macOS: Webots injects the controller path automatically.
    # If WEBOTS_HOME is set we add the python binding path.
    _wh = os.environ.get("WEBOTS_HOME", "")
    if _wh:
        _linux_pypath = os.path.join(_wh, "lib", "controller", "python")
        if os.path.exists(_linux_pypath) and _linux_pypath not in sys.path:
            sys.path.insert(0, _linux_pypath)

try:
    from controller import Robot  # type: ignore
except ImportError:
    Robot = None
    logger.warning("Webots 'controller' module not found. Will fail at runtime if not in simulation.")

try:
    import cv2
except ImportError:
    cv2 = None
    logger.error("opencv-python not installed. Camera capture will be disabled.")

# Controller local modules
script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(script_dir))
from communication import DroneCommunicationClient  # type: ignore
from flight_controller import FlightController  # type: ignore

def clamp(value, value_min, value_max):
    return min(max(value, value_min), value_max)

class DroneSupervisorController:
    # DJI Mavic 2 Pro empirical PID constants for Webots
    K_VERTICAL_THRUST = 68.5  # Base hover lift
    K_VERTICAL_OFFSET = 0.6   # Stabilization vertical offset
    K_VERTICAL_P = 3.0        # Altitude proportional gain
    K_ROLL_P = 50.0           # Roll stabilization gain
    K_PITCH_P = 30.0          # Pitch stabilization gain
    MAX_YAW_DISTURBANCE = 0.4
    MAX_PITCH_DISTURBANCE = -0.7

    def __init__(self, backend_url="http://127.0.0.1:8000"):
        if Robot is None:
            raise RuntimeError("Webots Robot API not found. Verify WEBOTS_HOME or Python environment.")

        self.robot = Robot()
        self.time_step = int(self.robot.getBasicTimeStep())
        self.comm = DroneCommunicationClient(backend_url=backend_url, drone_id="drone-webots-01")
        self.nav = FlightController(
            home_pos=(0.0, -45.0, 0.15),
            cruise_altitude=6.0,
            waypoint_tolerance=0.60
        )

        # Enable Sensors
        self.camera = self.robot.getDevice("camera")
        if self.camera:
            self.camera.enable(self.time_step * 4)

        self.imu = self.robot.getDevice("inertial unit")
        if self.imu:
            self.imu.enable(self.time_step)

        self.gps = self.robot.getDevice("gps")
        if self.gps:
            self.gps.enable(self.time_step)

        self.gyro = self.robot.getDevice("gyro")
        if self.gyro:
            self.gyro.enable(self.time_step)

        # Propeller Motors
        self.front_left_motor = self.robot.getDevice("front left propeller")
        self.front_right_motor = self.robot.getDevice("front right propeller")
        self.rear_left_motor = self.robot.getDevice("rear left propeller")
        self.rear_right_motor = self.robot.getDevice("rear right propeller")

        # Camera gimbal pitch motor
        self.camera_pitch_motor = self.robot.getDevice("camera pitch")
        if self.camera_pitch_motor:
            self.camera_pitch_motor.setPosition(0.35) # Angle camera slightly downward for road inspection

        for m in [self.front_left_motor, self.front_right_motor, self.rear_left_motor, self.rear_right_motor]:
            if m:
                m.setPosition(float('inf'))
                m.setVelocity(1.0)

        self.step_counter = 0
        self.prev_x, self.prev_y, self.prev_z = 0.0, -45.0, 0.15
        self.current_speed = 0.0
        self.battery = 100.0

        # Register drone in backend
        self.comm.register(name="DJI Mavic 2 Pro (Webots Sim)", model="DJI Mavic 2 Pro Quadrotor")

    def run(self):
        print("===================================================================")
        print("   CONTROLADOR AUTÓNOMO DE MISIÓN INICIADO EN WEBOTS")
        print("   Misión: DESPEGUE -> WAYPOINTS (1, 2, 3) -> HOVER -> RTL -> ATERRIZAJE")
        print("===================================================================")

        last_telemetry_time = 0.0
        last_frame_time = 0.0
        last_status_print_time = 0.0
        saved_first_frame = False

        evidence_frame_path = script_dir.parent.parent / "latest_webots_camera_frame.jpg"

        while self.robot.step(self.time_step) != -1:
            self.step_counter += 1
            sim_time = self.robot.getTime()

            # 1. Read Sensors
            roll, pitch, yaw = self.imu.getRollPitchYaw() if self.imu else (0.0, 0.0, 0.0)
            pos_x, pos_y, altitude = self.gps.getValues() if self.gps else (0.0, -45.0, 0.15)
            roll_acc, pitch_acc, _ = self.gyro.getValues() if self.gyro else (0.0, 0.0, 0.0)

            # Speed estimation
            dt = self.time_step / 1000.0
            dx = pos_x - self.prev_x
            dy = pos_y - self.prev_y
            dz = altitude - self.prev_z
            self.current_speed = math.sqrt(dx*dx + dy*dy + dz*dz) / max(dt, 0.001)
            self.prev_x, self.prev_y, self.prev_z = pos_x, pos_y, altitude

            # Battery discharge simulation
            self.battery = max(10.0, 100.0 - (sim_time * 0.08))

            # 2. Update Flight State Machine & Target Position
            target_x, target_y, target_z = self.nav.update(pos_x, pos_y, altitude, sim_time)
            flight_state = self.nav.get_state()
            target_altitude = self.nav.target_altitude

            # Periodic Flight Telemetry Print to Console
            if (sim_time - last_status_print_time) >= 1.0:
                last_status_print_time = sim_time
                print(f"[DRON EN VUELO REAL] T={sim_time:5.1f}s | Estado: {flight_state:11s} | Pos: [{pos_x:5.2f}, {pos_y:5.2f}, {altitude:5.2f}m] | Vel: {self.current_speed:4.2f}m/s | Bat: {self.battery:4.1f}%")

            # 3. Dynamic Flight Controls & Disturbance Calculations
            roll_disturbance = 0.0
            pitch_disturbance = 0.0
            yaw_disturbance = 0.0

            if flight_state == "LANDED":
                # Complete engine cut on ground
                front_left = 0.0
                front_right = 0.0
                rear_left = 0.0
                rear_right = 0.0
            else:
                if flight_state in ["NAVIGATING", "RETURNING"]:
                    delta_x = target_x - pos_x
                    delta_y = target_y - pos_y
                    dist_xy = math.hypot(delta_x, delta_y)
                    target_bearing = math.atan2(delta_y, delta_x)

                    # Yaw alignment difference normalized to [-pi, pi]
                    angle_diff = (target_bearing - yaw + math.pi) % (2 * math.pi) - math.pi
                    yaw_disturbance = clamp(0.4 * angle_diff / math.pi, -self.MAX_YAW_DISTURBANCE, self.MAX_YAW_DISTURBANCE)

                    # Forward pitch tilt proportional to remaining distance
                    if abs(angle_diff) < 0.8:
                        pitch_disturbance = clamp(-0.35 * min(dist_xy, 1.8), self.MAX_PITCH_DISTURBANCE, 0.0)
                    else:
                        # Prioritize yaw orientation before moving full speed forward
                        pitch_disturbance = -0.05

                elif flight_state in ["HOVER", "HOVER_HOME"]:
                    # Exact position hold with zero attitude perturbation
                    yaw_disturbance = 0.0
                    pitch_disturbance = 0.0
                    roll_disturbance = 0.0

                elif flight_state == "LANDING":
                    # Gentle vertical descent over launch pad
                    delta_x = target_x - pos_x
                    delta_y = target_y - pos_y
                    yaw_disturbance = 0.0
                    pitch_disturbance = clamp(delta_y * 0.1, -0.1, 0.1)
                    roll_disturbance = clamp(-delta_x * 0.1, -0.1, 0.1)

                # PID Attitude & Altitude computation
                roll_input = self.K_ROLL_P * clamp(roll, -1.0, 1.0) + roll_acc + roll_disturbance
                pitch_input = self.K_PITCH_P * clamp(pitch, -1.0, 1.0) + pitch_acc + pitch_disturbance
                yaw_input = yaw_disturbance

                clamped_alt_diff = clamp(target_altitude - altitude + self.K_VERTICAL_OFFSET, -1.0, 1.0)
                vertical_input = self.K_VERTICAL_P * pow(clamped_alt_diff, 3.0)

                # Motor mixing matrix
                front_left = self.K_VERTICAL_THRUST + vertical_input - yaw_input + pitch_input - roll_input
                front_right = self.K_VERTICAL_THRUST + vertical_input + yaw_input + pitch_input + roll_input
                rear_left = self.K_VERTICAL_THRUST + vertical_input + yaw_input - pitch_input - roll_input
                rear_right = self.K_VERTICAL_THRUST + vertical_input - yaw_input - pitch_input + roll_input

            # Apply motor velocities
            self.front_left_motor.setVelocity(front_left)
            self.front_right_motor.setVelocity(-front_right)
            self.rear_left_motor.setVelocity(-rear_left)
            self.rear_right_motor.setVelocity(rear_right)

            # 4. Transmit Telemetry to FastAPI Backend (~10 Hz)
            if (sim_time - last_telemetry_time) >= 0.10:
                last_telemetry_time = sim_time
                self.comm.send_telemetry(
                    pos_x=pos_x,
                    pos_y=pos_y,
                    pos_z=altitude,
                    roll=roll,
                    pitch=pitch,
                    yaw=yaw,
                    speed=self.current_speed,
                    battery=self.battery,
                    flight_mode=flight_state,
                    current_waypoint=self.nav.get_current_waypoint_index(),
                    current_mission=self.nav.mission_name,
                    state_description=self.nav.state_description
                )

            # 5. Capture & Send Camera Frame (~2.5 Hz)
            if (sim_time - last_frame_time) >= 0.40 and self.camera and cv2 is not None:
                last_frame_time = sim_time
                img_data = self.camera.getImage()
                if img_data:
                    w = self.camera.getWidth()
                    h = self.camera.getHeight()
                    if w > 0 and h > 0:
                        np_arr = np.frombuffer(img_data, dtype=np.uint8).reshape((h, w, 4))
                        bgr = np_arr[:, :, :3].copy()  # BGRA -> BGR, contiguous copy
                        # Write local evidence frame (latest frame from real Webots camera)
                        cv2.imwrite(str(evidence_frame_path), bgr)
                        if not saved_first_frame:
                            saved_first_frame = True
                            logger.info(f"[CÁMARA REAL WEBOTS] Primer frame capturado ({w}x{h} px) -> {evidence_frame_path.name}")
                            print(f"[CÁMARA REAL WEBOTS] Primer frame real capturado con éxito ({w}x{h} px). Guardado en {evidence_frame_path.name}")
                        ok, enc = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                        if ok:
                            b64 = base64.b64encode(enc).decode('utf-8')
                            iso_ts = datetime.now(timezone.utc).isoformat()
                            self.comm.send_camera_frame(
                                image_base64=b64,
                                pos_x=pos_x,
                                pos_y=pos_y,
                                pos_z=altitude,
                                run_detection=True,
                                timestamp=iso_ts
                            )

            if self.nav.mission_complete and flight_state == "LANDED":
                print("[Webots Drone Supervisor] MISIÓN COMPLETADA CON ÉXITO. APAGANDO SISTEMAS.")
                # Hold motors cut for a few seconds then finish
                time.sleep(1.0)
                break

if __name__ == "__main__":
    controller = DroneSupervisorController()
    controller.run()
