import math
import time
from typing import List, Tuple, Dict, Any, Optional

class MissionWaypoint:
    def __init__(self, x: float, y: float, z: float, hover_time: float = 3.0, description: str = ""):
        self.x = x
        self.y = y
        self.z = z
        self.hover_time = hover_time
        self.description = description

class FlightController:
    """
    Flight Controller and Mission State Machine for Surveillance Quadrotor.
    Controls takeoff, navigation between waypoints, hovering, return to launch, and controlled landing.
    """

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

        # Definition of Test Mission Waypoints
        self.waypoints: List[MissionWaypoint] = [
            MissionWaypoint(0.0, -20.0, cruise_altitude, hover_time=3.0, description="Waypoint 1: Sector Sur - Tramo Inicial"),
            MissionWaypoint(0.0, 5.0, cruise_altitude, hover_time=3.0, description="Waypoint 2: Sector Central - Vegetación en Vía"),
            MissionWaypoint(0.0, 30.0, cruise_altitude, hover_time=3.0, description="Waypoint 3: Sector Norte - Obstáculos y Postes")
        ]

        # State Machine States
        # INIT -> TAKEOFF -> NAVIGATING -> HOVER -> ... -> RETURNING -> HOVER_HOME -> LANDING -> LANDED
        self.state = "INIT"
        self.current_wp_idx = 0
        self.hover_start_time: Optional[float] = None
        self.state_start_time = time.time()
        self.target_altitude = 0.15
        self.current_target = (self.home_x, self.home_y, self.cruise_altitude)
        self.state_description = "Iniciando sistema y calibración de sensores"
        self.mission_complete = False

    def get_state(self) -> str:
        return self.state

    def get_current_waypoint_index(self) -> int:
        if self.state in ["NAVIGATING", "HOVER"]:
            return self.current_wp_idx + 1
        return 0

    def get_mission_info(self) -> Dict[str, Any]:
        return {
            "mission_name": self.mission_name,
            "state": self.state,
            "current_waypoint": self.get_current_waypoint_index(),
            "total_waypoints": len(self.waypoints),
            "state_description": self.state_description,
            "mission_complete": self.mission_complete,
            "target_altitude": self.target_altitude
        }

    def update(self, current_x: float, current_y: float, current_z: float, sim_time: float) -> Tuple[float, float, float]:
        """
        Updates flight state machine based on current 3D position and simulation time.
        Returns (target_x, target_y, target_z).
        """
        if self.state == "INIT":
            self.state = "TAKEOFF"
            self.target_altitude = self.cruise_altitude
            self.current_target = (self.home_x, self.home_y, self.cruise_altitude)
            self.state_description = f"Despegando a altitud crucero de {self.cruise_altitude:.1f}m"
            print(f"[FlightController] Transición: -> {self.state} ({self.state_description})")

        elif self.state == "TAKEOFF":
            self.target_altitude = self.cruise_altitude
            self.current_target = (self.home_x, self.home_y, self.cruise_altitude)
            # Reached target altitude
            if current_z >= (self.cruise_altitude - 0.4):
                self.state = "NAVIGATING"
                self.current_wp_idx = 0
                wp = self.waypoints[0]
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
                self.hover_start_time = sim_time
                self.state_description = f"Hover de inspección en Waypoint {self.current_wp_idx + 1} ({wp.hover_time:.1f}s)"
                print(f"[FlightController] Waypoint {self.current_wp_idx + 1} alcanzado (dist={dist_xy:.2f}m). Transición: -> HOVER")

        elif self.state == "HOVER":
            wp = self.waypoints[self.current_wp_idx]
            self.current_target = (wp.x, wp.y, wp.z)
            self.target_altitude = wp.z

            elapsed_hover = sim_time - (self.hover_start_time or sim_time)
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
            elapsed_hover = sim_time - (self.hover_start_time or sim_time)

            if elapsed_hover >= 2.0:
                self.state = "LANDING"
                self.state_description = "Iniciando descenso vertical controlado"
                print(f"[FlightController] Transición: -> LANDING")

        elif self.state == "LANDING":
            self.current_target = (self.home_x, self.home_y, 0.15)
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
            self.target_altitude = 0.0
            self.current_target = (self.home_x, self.home_y, 0.0)

        return self.current_target
