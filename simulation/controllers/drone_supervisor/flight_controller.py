import math
import time
from typing import List, Tuple, Dict, Any, Optional


def _clamp(value: float, value_min: float, value_max: float) -> float:
    return min(max(value, value_min), value_max)


class MissionWaypoint:
    def __init__(self, x: float, y: float, z: float, hover_time: float = 3.0, description: str = ""):
        self.x = x
        self.y = y
        self.z = z
        self.hover_time = hover_time
        self.description = description

    def to_dict(self, index: int) -> Dict[str, Any]:
        return {
            "index": index,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "hover_time": self.hover_time,
            "description": self.description,
        }


class FlightController:
    """
    Flight Controller and Mission State Machine for Surveillance Quadrotor.
    Controls takeoff, navigation between the 5 road waypoints, hovering with horizontal
    velocity damping, return to launch (RTH), controlled landing, and remote commands
    received from FastAPI / Dashboard (TAKEOFF, HOVER, RESUME_PATROL, RETURN_TO_HOME, LAND).
    """

    # PD gains for horizontal position hold and velocity damping in HOVER / TAKEOFF
    K_HOVER_POS_P = 0.18
    K_HOVER_VEL_D = 0.22
    MAX_HOVER_TILT = 0.35

    def __init__(
        self,
        home_pos: Tuple[float, float, float] = (0.0, -45.0, 0.15),
        cruise_altitude: float = 6.0,
        waypoint_tolerance: float = 0.55
    ):
        self.home_x, self.home_y, self.home_z = home_pos
        self.cruise_altitude = cruise_altitude
        self.waypoint_tolerance = waypoint_tolerance
        self.mission_name = "Mision_Inspeccion_Vigilancia_Vias"

        # Definición de los 5 Waypoints oficiales sobre el corredor vial (inspection_zone.wbt)
        self.waypoints: List[MissionWaypoint] = [
            MissionWaypoint(0.0, -30.0, cruise_altitude, hover_time=3.0, description="Waypoint 1: Sector Sur - Poste de Alumbrado Inicial"),
            MissionWaypoint(0.0, -15.0, cruise_altitude, hover_time=3.0, description="Waypoint 2: Tramo Sur-Centro - Pinos y Borde Vial"),
            MissionWaypoint(0.0, 0.0, cruise_altitude, hover_time=3.0, description="Waypoint 3: Sector Central - Cajas en Vía y Poste Central"),
            MissionWaypoint(0.0, 15.0, cruise_altitude, hover_time=3.0, description="Waypoint 4: Tramo Centro-Norte - Parche de Vegetación Invasiva"),
            MissionWaypoint(0.0, 30.0, cruise_altitude, hover_time=3.0, description="Waypoint 5: Sector Norte - Roca en Vía y Poste Norte"),
        ]

        # State Machine States:
        # READY_ON_GROUND -> TAKEOFF -> NAVIGATING -> HOVER -> ... -> RETURNING -> HOVER_HOME -> LANDING -> LANDED
        self.state = "READY_ON_GROUND"
        self.current_wp_idx = 0
        self.hover_start_time: Optional[float] = None
        self.state_start_time = time.time()
        self.target_altitude = 0.15
        self.current_target = (self.home_x, self.home_y, 0.15)
        self.state_description = "Dron en tierra listo para misión. En espera de comando TAKEOFF."
        self.mission_complete = False
        self.manual_hold = False
        self.battery_critical_active = False
        self.battery_failsafe_triggered = False
        self.last_command_executed: Optional[str] = None
        self.command_history: List[Dict[str, Any]] = []

    def get_state(self) -> str:
        return self.state

    def get_current_waypoint_index(self) -> int:
        if self.state in ["NAVIGATING", "HOVER"]:
            return min(self.current_wp_idx + 1, len(self.waypoints))
        return 0

    def get_waypoints_dict(self) -> List[Dict[str, Any]]:
        return [wp.to_dict(i + 1) for i, wp in enumerate(self.waypoints)]

    def get_mission_info(self) -> Dict[str, Any]:
        return {
            "mission_name": self.mission_name,
            "state": self.state,
            "current_waypoint": self.get_current_waypoint_index(),
            "total_waypoints": len(self.waypoints),
            "state_description": self.state_description,
            "mission_complete": self.mission_complete,
            "manual_hold": self.manual_hold,
            "target_altitude": self.target_altitude,
            "last_command_executed": self.last_command_executed,
        }

    def compute_hover_damping(
        self,
        pos_x: float,
        pos_y: float,
        target_x: float,
        target_y: float,
        vx: float,
        vy: float,
        yaw: float,
    ) -> Tuple[float, float]:
        """
        Computes (pitch_disturbance, roll_disturbance) in the drone body frame
        to actively damp horizontal velocity (vx, vy) and hold (target_x, target_y)
        during HOVER, HOVER_HOME, TAKEOFF, and LANDING.
        """
        cos_yaw = math.cos(yaw)
        sin_yaw = math.sin(yaw)

        # Error de posición proyectado al marco del cuerpo del dron (adelante / izquierda)
        err_x = target_x - pos_x
        err_y = target_y - pos_y
        err_forward = err_x * cos_yaw + err_y * sin_yaw
        err_left = -err_x * sin_yaw + err_y * cos_yaw

        # Velocidad horizontal proyectada al marco del cuerpo del dron
        vel_forward = vx * cos_yaw + vy * sin_yaw
        vel_left = -vx * sin_yaw + vy * cos_yaw

        # En Mavic2Pro: pitch_disturbance negativo inclina la nariz abajo (acelera hacia adelante),
        # por lo tanto +K_HOVER_VEL_D * vel_forward frena el avance por inercia.
        pitch_disturbance = _clamp(
            -self.K_HOVER_POS_P * err_forward + self.K_HOVER_VEL_D * vel_forward,
            -self.MAX_HOVER_TILT,
            self.MAX_HOVER_TILT,
        )
        roll_disturbance = _clamp(
            -self.K_HOVER_POS_P * err_left + self.K_HOVER_VEL_D * vel_left,
            -self.MAX_HOVER_TILT,
            self.MAX_HOVER_TILT,
        )
        return pitch_disturbance, roll_disturbance

    def execute_command(
        self,
        command: str,
        current_pos: Tuple[float, float, float] = (0.0, -45.0, 0.15),
        sim_time: float = 0.0,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a remote command received from the backend/dashboard on the flight state machine:
        - TAKEOFF
        - HOVER
        - RESUME_PATROL
        - RETURN_TO_HOME (or RTL / RTH)
        - LAND
        - SET_WAYPOINT
        """
        raw = (command or "").strip().upper()
        cx, cy, cz = current_pos
        prev_state = self.state

        if raw == "TAKEOFF":
            if self.battery_critical_active:
                return {
                    "accepted": False,
                    "command": raw,
                    "previous_state": prev_state,
                    "new_state": self.state,
                    "message": "Comando rechazado: Batería crítica (<20%). Despegue deshabilitado por seguridad.",
                }
            self.state = "TAKEOFF"
            self.manual_hold = False
            self.mission_complete = False
            self.target_altitude = self.cruise_altitude
            self.current_target = (cx, cy, self.cruise_altitude)
            self.state_description = f"Comando remoto TAKEOFF: Despegando a {self.cruise_altitude:.1f}m"

        elif raw == "HOVER":
            self.state = "HOVER"
            self.manual_hold = True
            self.mission_complete = False
            hold_alt = max(cz, self.cruise_altitude if cz < 0.8 else cz)
            self.target_altitude = hold_alt
            self.current_target = (cx, cy, hold_alt)
            self.hover_start_time = sim_time
            self.state_description = f"Comando remoto HOVER: Manteniendo posición en ({cx:.1f}, {cy:.1f}, {hold_alt:.1f}m)"

        elif raw == "RESUME_PATROL":
            if self.battery_critical_active:
                return {
                    "accepted": False,
                    "command": raw,
                    "previous_state": prev_state,
                    "new_state": self.state,
                    "message": "Comando rechazado: Retorno automático por batería crítica (<20%) prioritario en curso.",
                }
            self.manual_hold = False
            self.mission_complete = False
            if self.current_wp_idx >= len(self.waypoints):
                self.current_wp_idx = 0
            wp = self.waypoints[self.current_wp_idx]
            if cz < 1.0 or prev_state in ("INIT", "READY_ON_GROUND", "LANDED"):
                self.state = "TAKEOFF"
                self.target_altitude = self.cruise_altitude
                self.current_target = (cx, cy, self.cruise_altitude)
                self.state_description = f"Comando remoto RESUME_PATROL: Despegando para ir a {wp.description}"
            else:
                self.state = "NAVIGATING"
                self.target_altitude = wp.z
                self.current_target = (wp.x, wp.y, wp.z)
                self.state_description = f"Comando remoto RESUME_PATROL: Patrullando hacia {wp.description}"

        elif raw in ("RETURN_TO_HOME", "RTL", "RTH"):
            self.state = "RETURNING"
            self.manual_hold = False
            self.mission_complete = False
            self.target_altitude = self.cruise_altitude
            self.current_target = (self.home_x, self.home_y, self.cruise_altitude)
            self.state_description = f"Comando remoto RETURN_TO_HOME: Regresando a base ({self.home_x:.1f}, {self.home_y:.1f})"

        elif raw == "LAND":
            self.state = "LANDING"
            self.manual_hold = False
            self.target_altitude = max(0.15, cz)
            self.current_target = (cx, cy, 0.15)
            self.state_description = f"Comando remoto LAND: Descenso controlado en ({cx:.1f}, {cy:.1f})"

        elif raw == "SET_WAYPOINT":
            wp_num = int((params or {}).get("waypoint_index", 1))
            idx = max(0, min(len(self.waypoints) - 1, wp_num - 1))
            self.current_wp_idx = idx
            self.manual_hold = False
            self.mission_complete = False
            wp = self.waypoints[self.current_wp_idx]
            self.state = "NAVIGATING"
            self.target_altitude = wp.z
            self.current_target = (wp.x, wp.y, wp.z)
            self.state_description = f"Comando remoto SET_WAYPOINT: Dirigiéndose a {wp.description}"

        else:
            return {
                "accepted": False,
                "command": raw,
                "previous_state": prev_state,
                "new_state": self.state,
                "message": f"Comando desconocido: {command}",
            }

        self.last_command_executed = raw
        entry = {
            "command": raw,
            "previous_state": prev_state,
            "new_state": self.state,
            "target": self.current_target,
            "sim_time": sim_time,
        }
        self.command_history.append(entry)
        print(f"[FlightController] Comando remoto ejecutado: {raw} ({prev_state} -> {self.state})")
        return {"accepted": True, **entry}

    def update(
        self,
        current_x: float,
        current_y: float,
        current_z: float,
        sim_time: float,
        battery: Optional[float] = None
    ) -> Tuple[float, float, float]:
        """
        Updates flight state machine based on current 3D position, simulation time,
        and optional battery level for critical failsafe.
        Returns (target_x, target_y, target_z).
        """
        # 0. Failsafe por batería crítica (< 20%): Retorno automático prioritario a base
        if battery is not None and battery < 20.0:
            if not self.battery_critical_active and self.state in ("TAKEOFF", "NAVIGATING", "HOVER"):
                self.battery_critical_active = True
                self.battery_failsafe_triggered = True
                self.state = "RETURNING"
                self.manual_hold = False
                self.mission_complete = False
                self.target_altitude = self.cruise_altitude
                self.current_target = (self.home_x, self.home_y, self.cruise_altitude)
                self.state_description = f"Batería crítica ({battery:.1f}% < 20%): Retorno automático prioritario a base (RTH)"
                print(f"[FlightController] ¡ALERTA BATERÍA CRÍTICA! ({battery:.1f}%). Retorno automático activado -> RETURNING")
                self.command_history.append({
                    "command": "RETURN_TO_HOME",
                    "trigger": "BATTERY_CRITICAL",
                    "battery": battery,
                    "sim_time": sim_time,
                })
                return self.current_target

        if self.state in ("INIT", "READY_ON_GROUND"):
            self.state = "READY_ON_GROUND"
            self.target_altitude = 0.15
            self.current_target = (self.home_x, self.home_y, 0.15)
            self.state_description = "Dron en tierra listo para misión. En espera de comando TAKEOFF."
            return self.current_target

        elif self.state == "TAKEOFF":
            self.target_altitude = self.cruise_altitude
            tx, ty, _ = self.current_target
            self.current_target = (tx, ty, self.cruise_altitude)
            # Reached target altitude
            if current_z >= (self.cruise_altitude - 0.4):
                self.state = "NAVIGATING"
                if self.current_wp_idx >= len(self.waypoints):
                    self.current_wp_idx = 0
                wp = self.waypoints[self.current_wp_idx]
                self.current_target = (wp.x, wp.y, wp.z)
                self.state_description = f"Navegando hacia {wp.description}"
                print(f"[FlightController] Altitud alcanzada ({current_z:.2f}m). Transición: -> {self.state} ({self.state_description})")

        elif self.state == "NAVIGATING":
            wp = self.waypoints[self.current_wp_idx]
            self.current_target = (wp.x, wp.y, wp.z)
            self.target_altitude = wp.z
            dist_xy = math.hypot(wp.x - current_x, wp.y - current_y)

            if dist_xy <= self.waypoint_tolerance:
                # Reached waypoint -> transition to HOVER
                self.state = "HOVER"
                self.manual_hold = False
                self.hover_start_time = sim_time
                self.state_description = f"Hover de inspección en Waypoint {self.current_wp_idx + 1} ({wp.hover_time:.1f}s)"
                print(f"[FlightController] Waypoint {self.current_wp_idx + 1} alcanzado (dist={dist_xy:.2f}m). Transición: -> HOVER")

        elif self.state == "HOVER":
            if self.manual_hold:
                # Mantener posición indefinidamente por orden explícita del operador
                tx, ty, tz = self.current_target
                self.target_altitude = tz
                self.state_description = f"Hover manual activo en ({tx:.1f}, {ty:.1f}, {tz:.1f}m) — esperando comando"
                return self.current_target

            wp = self.waypoints[self.current_wp_idx]
            self.current_target = (wp.x, wp.y, wp.z)
            self.target_altitude = wp.z

            elapsed_hover = sim_time - (self.hover_start_time if self.hover_start_time is not None else sim_time)
            remaining = max(0.0, wp.hover_time - elapsed_hover)
            self.state_description = f"Inspeccionando en Waypoint {self.current_wp_idx + 1} ({remaining:.1f}s restantes)"

            if elapsed_hover >= wp.hover_time:
                # Hover complete
                self.current_wp_idx += 1
                if self.current_wp_idx < len(self.waypoints):
                    # Proceed to next waypoint
                    self.state = "NAVIGATING"
                    next_wp = self.waypoints[self.current_wp_idx]
                    self.current_target = (next_wp.x, next_wp.y, next_wp.z)
                    self.state_description = f"Navegando hacia {next_wp.description}"
                    print(f"[FlightController] Hover completado. Transición: -> NAVIGATING a Waypoint {self.current_wp_idx + 1}")
                else:
                    # All waypoints completed -> Return to Home
                    self.state = "RETURNING"
                    self.current_target = (self.home_x, self.home_y, self.cruise_altitude)
                    self.target_altitude = self.cruise_altitude
                    self.state_description = "Retorno automático a base (RTL)"
                    print(f"[FlightController] Todos los waypoints visitados. Transición: -> RETURNING a base ({self.home_x}, {self.home_y})")

        elif self.state == "RETURNING":
            self.current_target = (self.home_x, self.home_y, self.cruise_altitude)
            self.target_altitude = self.cruise_altitude
            dist_home_xy = math.hypot(self.home_x - current_x, self.home_y - current_y)

            if dist_home_xy <= self.waypoint_tolerance:
                self.state = "HOVER_HOME"
                self.hover_start_time = sim_time
                self.state_description = "Alineación vertical sobre base antes de aterrizar (2s)"
                print(f"[FlightController] Sobre base de despegue. Transición: -> HOVER_HOME")

        elif self.state == "HOVER_HOME":
            self.current_target = (self.home_x, self.home_y, self.cruise_altitude)
            self.target_altitude = self.cruise_altitude
            elapsed_hover = sim_time - (self.hover_start_time if self.hover_start_time is not None else sim_time)

            if elapsed_hover >= 2.0:
                self.state = "LANDING"
                self.state_description = "Iniciando descenso vertical controlado"
                print(f"[FlightController] Transición: -> LANDING")

        elif self.state == "LANDING":
            tx, ty, _ = self.current_target
            self.current_target = (tx, ty, 0.15)
            # Smooth descent trajectory
            self.target_altitude = max(0.12, self.target_altitude - 0.015)
            self.state_description = f"Aterrizando... Altitud: {current_z:.2f}m"

            if current_z <= 0.25:
                self.state = "LANDED"
                self.target_altitude = 0.0
                self.mission_complete = True
                self.state_description = "Aterrizaje controlado completado con éxito. Motores detenidos."
                print(f"[FlightController] ¡Aterrizaje exitoso! Dron en tierra ({current_z:.2f}m). Misión completada.")

        elif self.state == "LANDED":
            tx, ty, _ = self.current_target
            self.target_altitude = 0.0
            self.current_target = (tx, ty, 0.0)

        return self.current_target
