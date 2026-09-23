"""
Controlador BASICO para el proyecto:
Dron de escaneo para prevencion de accidentes viales - Cienaga, Magdalena

Funcion principal: el dron patrulla un tramo de carretera siguiendo una
lista de waypoints, y usa su camara para detectar posibles obstaculos
en la via mediante un umbral de color simple (deteccion basica, sin ML).

Este es un punto de partida: el algoritmo de deteccion es intencionalmente
simple para poder mostrar el flujo completo del proyecto. Se puede
reemplazar mas adelante por un modelo entrenado (por ejemplo YOLO) sin
cambiar la logica de vuelo.
"""

from controller import Robot
import numpy as np
import math

# ---------------------------------------------------------------------
# Configuracion general
# ---------------------------------------------------------------------

TIME_STEP = 8

# Waypoints sobre la carretera (x, y) en metros, altura de vuelo fija.
WAYPOINTS = [
    (-20, 0),
    (-10, 0),
    (0, 0),
    (10, 0),
    (20, 0),
]
CRUISE_ALTITUDE = 5.0     # metros
WAYPOINT_TOLERANCE = 0.5  # metros

# Ganancias PID basicas (valores tipicos usados en el ejemplo Mavic2Pro
# de Webots, ajustar segun se necesite)
K_VERTICAL_THRUST = 68.5
K_VERTICAL_OFFSET = 0.6
K_VERTICAL_P = 3.0
K_ROLL_P = 50.0
K_PITCH_P = 30.0


class DroneController:
    def __init__(self):
        self.robot = Robot()

        # --- Sensores ---
        self.imu = self.robot.getDevice("inertial unit")
        self.imu.enable(TIME_STEP)

        self.gps = self.robot.getDevice("gps")
        self.gps.enable(TIME_STEP)

        self.gyro = self.robot.getDevice("gyro")
        self.gyro.enable(TIME_STEP)

        self.camera = self.robot.getDevice("camera")
        self.camera.enable(TIME_STEP)

        # --- Motores (4 rotores) ---
        self.motors = [
            self.robot.getDevice("front left propeller"),
            self.robot.getDevice("front right propeller"),
            self.robot.getDevice("rear left propeller"),
            self.robot.getDevice("rear right propeller"),
        ]
        for m in self.motors:
            m.setPosition(float("inf"))
            m.setVelocity(1.0)

        self.current_waypoint = 0
        self.alertas = []  # log simple de alertas generadas

    # -------------------------------------------------------------
    # Deteccion de obstaculos (basica, por umbral de color)
    # -------------------------------------------------------------
    def detectar_obstaculo(self):
        """
        Analiza la imagen de la camara y busca regiones que contrasten
        fuertemente con el color de la carretera (gris oscuro).
        Devuelve True si hay una region sospechosa de tamano relevante.
        """
        width = self.camera.getWidth()
        height = self.camera.getHeight()
        image = self.camera.getImageArray()  # lista [x][y][r,g,b]

        if image is None:
            return False

        img = np.array(image, dtype=np.uint8)  # shape: (width, height, 3)

        # Color aproximado de la carretera (gris oscuro ~ 38,38,38)
        road_color = np.array([38, 38, 38])
        diff = np.abs(img.astype(int) - road_color)
        distancia_color = diff.sum(axis=2)

        # Pixeles que se alejan bastante del color de la via
        mask = distancia_color > 90
        pixeles_detectados = np.count_nonzero(mask)

        total_pixeles = width * height
        proporcion = pixeles_detectados / total_pixeles

        # Umbral simple: si mas de un 3% de la imagen contrasta con
        # la via, se considera que hay un obstaculo relevante
        return proporcion > 0.03

    # -------------------------------------------------------------
    # Vuelo por waypoints con estabilizacion PID basica
    # -------------------------------------------------------------
    def run(self):
        while self.robot.step(TIME_STEP) != -1:
            roll, pitch, _ = self.imu.getRollPitchYaw()
            x, y, altitude = self.gps.getValues()
            roll_vel, pitch_vel, _ = self.gyro.getValues()

            # --- Waypoint actual ---
            if self.current_waypoint >= len(WAYPOINTS):
                # Ruta completada: aterrizar en el ultimo punto
                target_x, target_y = WAYPOINTS[-1]
            else:
                target_x, target_y = WAYPOINTS[self.current_waypoint]

            dx = target_x - x
            dy = target_y - y
            distancia = math.sqrt(dx * dx + dy * dy)

            if distancia < WAYPOINT_TOLERANCE and self.current_waypoint < len(WAYPOINTS):
                self.current_waypoint += 1
                print(f"[RUTA] Waypoint alcanzado, avanzando al siguiente "
                      f"({self.current_waypoint}/{len(WAYPOINTS)})")

            # --- Deteccion de obstaculos en cada paso ---
            if self.detectar_obstaculo():
                pos_actual = (round(x, 1), round(y, 1))
                if pos_actual not in self.alertas:
                    self.alertas.append(pos_actual)
                    print(f"[ALERTA] Posible obstaculo detectado en la via "
                          f"cerca de x={pos_actual[0]}, y={pos_actual[1]}")

            # --- Control basico de altitud y orientacion (PID simple) ---
            roll_input = K_ROLL_P * max(-1, min(1, roll)) + roll_vel
            pitch_input = K_PITCH_P * max(-1, min(1, pitch)) + pitch_vel

            # Empuje vertical objetivo para mantener altitud de crucero
            vertical_error = CRUISE_ALTITUDE - altitude + K_VERTICAL_OFFSET
            vertical_input = K_VERTICAL_P * (vertical_error ** 3)

            front_left = K_VERTICAL_THRUST + vertical_input - roll_input + pitch_input
            front_right = K_VERTICAL_THRUST + vertical_input + roll_input + pitch_input
            rear_left = K_VERTICAL_THRUST + vertical_input - roll_input - pitch_input
            rear_right = K_VERTICAL_THRUST + vertical_input + roll_input - pitch_input

            self.motors[0].setVelocity(front_left)
            self.motors[1].setVelocity(-front_right)
            self.motors[2].setVelocity(-rear_left)
            self.motors[3].setVelocity(rear_right)


if __name__ == "__main__":
    DroneController().run()
