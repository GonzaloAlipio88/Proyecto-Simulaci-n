# Especificación Técnica de Arquitectura

## 1. Módulos del Sistema Backend

| Módulo | Responsabilidad | Archivos Clave |
|---|---|---|
| **drones** | Gestión del ciclo de vida del dron, registro, estado operacional y despacho de comandos remotos de vuelo (takeoff, land, hover, rth). | `backend/app/modules/drones/service.py`<br>`backend/app/api/v1/endpoints/drones.py` |
| **telemetria** | Ingesta de coordenadas tridimensionales (X, Y, Z), orientación (Roll, Pitch, Yaw), velocidad y batería. Emite eventos en tiempo real vía WebSocket. | `backend/app/modules/telemetria/service.py`<br>`backend/app/api/v1/endpoints/telemetria.py` |
| **cameras** | Recepción de fotogramas en base64 desde Webots, llamada al pipeline de visión, extracción de detecciones y generación de stream en vivo. | `backend/app/modules/cameras/service.py`<br>`backend/app/api/v1/endpoints/cameras.py` |
| **deteccion** | Pipeline de visión artificial con clase base abstracta `BaseDetector`, detector heurístico OpenCV operativo y adaptador listo para pesos YOLO. | `backend/app/modules/deteccion/base.py`<br>`backend/app/modules/deteccion/service.py` |
| **imagenes** | Guardado físico de fotogramas originales y anotados en disco, registro de metadatos en SQLite y entrega binaria segura vía endpoints REST. | `backend/app/modules/imagenes/service.py`<br>`backend/app/api/v1/endpoints/imagenes.py` |
| **incidentes** | Clasificación de anomalías detectadas en vía, severidades (baja, media, alta, crítica), persistencia en SQLite y actualización de estado de atención. | `backend/app/modules/incidentes/service.py`<br>`backend/app/api/v1/endpoints/incidentes.py` |

---

## 2. Esquema de Datos SQLite

* **`drones`**: `id` (PK), `name`, `model`, `status`, `battery_level`, `current_x`, `current_y`, `current_z`, `current_speed`, `flight_mode`, `last_seen_at`.
* **`telemetria`**: `id` (PK auto), `drone_id`, `timestamp`, `pos_x`, `pos_y`, `pos_z`, `roll`, `pitch`, `yaw`, `speed`, `battery`, `flight_mode`.
* **`imagenes`**: `id` (PK auto), `drone_id`, `filename`, `file_path`, `captured_at`, `pos_x`, `pos_y`, `pos_z`, `has_detections`, `detection_count`, `annotated_filename`.
* **`incidentes`**: `id` (PK auto), `drone_id`, `tipo`, `severidad`, `descripcion`, `pos_x`, `pos_y`, `pos_z`, `confidence`, `imagen_id`, `estado`, `timestamp`.

---

## 3. Protocolo WebSocket en Tiempo Real (`ws://127.0.0.1:8000/ws`)

1. **`connection_ack`**: Mensaje de bienvenida y conteo de clientes activos.
2. **`telemetry`**: Emisión continua de coordenadas 3D, velocidad y batería.
3. **`camera_stream`**: Emisión del fotograma procesado con las cajas delimitadoras y tiempos de inferencia.
4. **`incident`**: Alerta inmediata cuando una anomalía en vía sobrepasa el umbral de confianza o severidad.
5. **`drone_command`**: Retransmisión de órdenes desde el operador humano hacia el controlador del dron.
