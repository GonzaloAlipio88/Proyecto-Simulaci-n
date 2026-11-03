# SEMANA 8 — GESTIÓN DE INCIDENTES Y PERSISTENCIA SQLITE
**Sistema de Detección e Inspección de Vías con Dron Autónomo**

Documentación Técnica de Entrega  
Fecha: 30 de Octubre de 2026  
Rol: Ingeniero Sénior de Backend, Bases de Datos SQLite e Inspección Vial

---

## 1. Resumen Ejecutivo y Alcance

En la **Semana 8**, se completó y robusteció el módulo integral de **Gestión de Incidentes y Persistencia en SQLite**. Este módulo permite registrar, deduplicar, consultar, actualizar, eliminar y supervisar las anomalías viales detectadas por el sistema de visión artificial (Semana 5 y 6) y la carga de imágenes externas (Semana 7).

```
                      +-------------------------------------------------------+
                      |               Webots / Cámara / Upload                |
                      |          Ingesta de Frames & Detecciones IA           |
                      +-------------------------------------------------------+
                                                  |
                                                  v
                      +-------------------------------------------------------+
                      |         RoadClassificationService (Semana 6)          |
                      |  - Calificación de anomalías candidatas a incidente   |
                      |  - Deduplicación visual en streaming                  |
                      +-------------------------------------------------------+
                                                  |
                                                  v IncidenteCreate
                      +-------------------------------------------------------+
                      |           IncidenteService (Semana 8)                 |
                      |  - Deduplicación espacio-temporal (5s / 2.5m)         |
                      |  - Validación de campos estrictos (Pydantic v2)       |
                      |  - Tolerancia a fallos de BD con db.rollback()        |
                      |  - CRUD completo (Create, Read, Update, Delete, Stats)|
                      +-------------------------------------------------------+
                                        |                   |
                                        v                   v
             +-------------------------------+   +-------------------------------+
             |       SQLite Database         |   |    FastAPI WebSocket /ws      |
             |  - Tabla 'incidentes' (1500+) |   |  - Canal 'incident'           |
             |  - Coordenadas simulación 3D  |   |  - Canal 'incident_updated'   |
             |  - Enlace a registro de foto  |   |  - Canal 'incident_deleted'   |
             +-------------------------------+   +-------------------------------+
                                                           |
                                                           v
                                         +-----------------------------------+
                                         |    Dashboard React (TypeScript)   |
                                         |  - Componente IncidentLog         |
                                         |  - Filtros tipo, severidad, estado|
                                         |  - Enlace a fotografía capturada  |
                                         |  - Eliminación y actualización    |
                                         +-----------------------------------+
```

---

## 2. Representación de Detecciones Viales y Metadatos

El sistema normaliza y cataloga rigurosamente los siguientes tipos de anomalías:

| Tipo (`tipo`) | Descripción | Criterio de Riesgo | Severidad Predeterminada |
| :--- | :--- | :--- | :--- |
| `poste_luz` | Postes de alumbrado o columnas de catenaria a lo largo de las vías | Activo de infraestructura fija; inventariable | `baja` (a menos que haya daño estructural) |
| `vegetacion_invasiva` | Maleza, ramas o árboles que invaden la franja central o el gálibo | Riesgo de bloqueo visual o roce con material rodante | `alta` o `media` |
| `obstruccion_via` | Rocas, escombros, personas o vehículos sobre los rieles o calzada | Riesgo crítico de colisión o descarrilamiento | `critica` o `alta` |
| `otro` | Anomalías no catalogadas o detecciones de clases externas | Requiere validación técnica preventiva | `baja` o `media` |

### 2.1 Campos Disponibles del Incidente
Cada incidente almacenado en la tabla `incidentes` de SQLite contiene:
- **`id`** (`INTEGER PRIMARY KEY AUTOINCREMENT`): Identificador único del incidente.
- **`drone_id`** (`VARCHAR(50)`): Identificador del dron o fuente que reportó la detección.
- **`tipo`** (`VARCHAR(50)`): Tipo de incidente normalizado (`poste_luz`, `vegetacion_invasiva`, `obstruccion_via`, `otro`).
- **`severidad`** (`VARCHAR(20)`): Nivel de urgencia (`baja`, `media`, `alta`, `critica`).
- **`descripcion`** (`VARCHAR(500)`): Justificación técnica y detalle de la anomalía.
- **`pos_x`, `pos_y`, `pos_z`** (`FLOAT`): Coordenadas locales métricas en el mundo 3D de simulación Webots. Si no hay telemetría, se registra `None` honesto (no se inventan coordenadas GPS ficticias ni origen `0,0,0`).
- **`coordenadas_tipo`** (`VARCHAR(50)`): Sistema de referencia (`simulacion_webots`).
- **`confidence`** (`FLOAT`): Grado de certeza de la detección (0.0 a 1.0).
- **`imagen_id`** (`INTEGER`): ID foráneo a la tabla `imagenes` que almacena la captura original y anotada.
- **`imagen_url`** (propiedad dinámica): Ruta URL `/api/v1/imagenes/{imagen_id}` para visualización inmediata en dashboard o navegadores.
- **`estado`** (`VARCHAR(30)`): Ciclo de vida (`reportado`, `en_revision`, `atendido`, `descartado`).
- **`timestamp`** (`DATETIME`): Marca temporal UTC del suceso.

---

## 3. Persistencia en SQLite y Migración No Destructiva

El archivo de base de datos se ubica en `backend/storage/data.db` y ya cuenta con más de 1,500 incidentes registrados previamente.

### 3.1 Garantía de Migración Idempotente y Cero Pérdida de Datos
Para garantizar compatibilidad con bases de datos preexistentes:
- La función `init_db()` en `backend/app/core/database.py` inspecciona los esquemas activos mediante `PRAGMA table_info(incidentes)`.
- Si la columna `coordenadas_tipo` no existe, ejecuta automáticamente un `ALTER TABLE incidentes ADD COLUMN coordenadas_tipo VARCHAR(50) DEFAULT 'simulacion_webots'`.
- **Resultado:** Se preserva el 100% de la información histórica sin necesidad de reiniciar la base de datos ni recrear tablas.

---

## 4. Deduplicación Espacio-Temporal de Incidentes

Para evitar que el sobrevuelo continuo de un dron genere decenas de registros idénticos por segundo en la base de datos:

1. **Ventana Temporal (`dedup_window_seconds`):** 5.0 segundos.
2. **Radio Espacial (`dedup_distance_meters`):** 2.5 metros euclidianos ($D = \sqrt{\Delta x^2 + \Delta y^2}$).
3. **Regla de Deduplicación:**
   - Si se reporta un incidente con el mismo `drone_id` y `tipo` dentro de los últimos 5 segundos y a una distancia $\le 2.5\text{ m}$:
     - **No se inserta un nuevo registro.**
     - Se actualiza la confianza del incidente existente si la nueva medición es más precisa (`cand.confidence = max(cand.confidence, new_confidence)`).
     - Se actualiza la marca de tiempo al evento más reciente.
     - Se retorna el incidente existente al cliente HTTP.
4. **Bypass Opcional (`allow_duplicate=true`):**
   - El endpoint `POST /api/v1/incidentes?allow_duplicate=true` permite forzar la creación explícita cuando un operador humano o un flujo específico así lo requiera.

---

## 5. Especificación de Endpoints REST API

Todos los endpoints se exponen bajo el prefijo `/api/v1/incidentes`:

### 5.1 `POST /api/v1/incidentes`
Registra un incidente en SQLite aplicando deduplicación automática.

- **Parámetros Query:**
  - `allow_duplicate` (`bool`, por defecto `false`): Si es `true`, omite la deduplicación.
- **Cuerpo de Solicitud (JSON):**
  ```json
  {
    "drone_id": "drone-sim-01",
    "tipo": "obstruccion_via",
    "severidad": "critica",
    "descripcion": "Roca de 40cm sobre riel izquierdo en km 14.2",
    "pos_x": 14.2,
    "pos_y": 7.1,
    "pos_z": 14.8,
    "coordenadas_tipo": "simulacion_webots",
    "confidence": 0.94,
    "imagen_id": 1132,
    "estado": "reportado"
  }
  ```
- **Respuesta (200 OK):** Objeto `IncidenteResponse` completo con `id`, `timestamp` e `imagen_url`.

### 5.2 `GET /api/v1/incidentes`
Consulta la lista de incidentes con filtros combinables, ordenación y paginación.

- **Parámetros Query Opcionales:**
  - `tipo`: Filtrar por categoría (`poste_luz`, `vegetacion_invasiva`, `obstruccion_via`, `otro`).
  - `severidad`: Filtrar por nivel (`baja`, `media`, `alta`, `critica`).
  - `estado`: Filtrar por estado (`reportado`, `en_revision`, `atendido`, `descartado`).
  - `drone_id`: Filtrar por identificador de dron.
  - `min_confidence`: Confianza mínima (entre 0.0 y 1.0).
  - `has_image`: Filtrar por presencia de fotografía asociada (`true` / `false`).
  - `start_date`: Fecha y hora mínima (ISO 8601).
  - `end_date`: Fecha y hora máxima (ISO 8601).
  - `search`: Búsqueda de subcadena insensible a mayúsculas en la descripción.
  - `order_by`: Orden temporal (`desc` o `asc`, por defecto `desc`).
  - `skip`: Cantidad de registros a omitir para paginación (por defecto `0`).
  - `limit`: Límite de resultados devueltos (1 a 500, por defecto `100`).

### 5.3 `GET /api/v1/incidentes/stats`
Devuelve un informe estadístico consolidado de la base de datos:
```json
{
  "total_incidentes": 1508,
  "por_tipo": {
    "obstruccion_via": 932,
    "vegetacion_invasiva": 452,
    "poste_luz": 121,
    "otro": 3
  },
  "por_severidad": {
    "critica": 535,
    "alta": 602,
    "media": 250,
    "baja": 121
  },
  "por_estado": {
    "reportado": 1404,
    "en_revision": 81,
    "atendido": 20,
    "descartado": 3
  },
  "con_imagen": 1452,
  "sin_imagen": 56,
  "confianza_promedio": 0.8245,
  "ultimo_incidente_timestamp": "2026-10-31T00:16:15"
}
```

### 5.4 `GET /api/v1/incidentes/{incidente_id}`
Recupera los detalles de un incidente específico por su identificador primario. Retorna `404 Not Found` si no existe.

### 5.5 `GET /api/v1/incidentes/{incidente_id}/imagen`
Consulta los metadatos de la imagen asociada al incidente, o descarga directamente el archivo JPG si se especifica `?download=true`. Retorna `404 Not Found` si el incidente no tiene imagen vinculada.

### 5.6 `PATCH /api/v1/incidentes/{incidente_id}`
Actualiza campos operativos del incidente:
```json
{
  "estado": "en_revision",
  "severidad": "alta",
  "descripcion": "Verificación confirmada por operador técnico"
}
```

### 5.7 `DELETE /api/v1/incidentes/{incidente_id}`
Elimina de forma permanente el incidente de SQLite y emite un evento WebSocket `incident_deleted`.

---

## 6. Manejo Seguro de Errores y Resiliencia

El backend implementa un patrón robusto para evitar que fallos en la base de datos detengan el proceso del servidor:

1. **Validación de Datos (HTTP 422):**
   - Coordenadas con valores no numéricos, `NaN` o `Inf` se rechazan en la capa de esquemas Pydantic.
   - Textos vacíos o compuestos únicamente de espacios en blanco son bloqueados.
   - Valores fuera de rango para `confidence` ($<0$ o $>1$) son interceptados.
2. **Rollback de Transacción Automático:**
   - Todo bloque `try` que interactúa con la sesión SQLAlchemy incluye `except SQLAlchemyError: db.rollback()`.
   - Se devuelven respuestas HTTP 500 descriptivas al cliente, evitando dejar sesiones de base de datos colgadas.
3. **Resiliencia en Streaming:**
   - Si ocurre una anomalía al guardar un incidente durante la ingesta de vídeo en `camera_service.py`, el error se registra en el log y el flujo de fotogramas hacia el dashboard WebSocket continúa operando sin interrupción.

---

## 7. Pruebas Automatizadas

Se añadieron 12 pruebas unitarias e integrales en `backend/tests/test_semana_8_incidentes.py`, cubriendo:
1. `test_incidente_creation_and_persistence`: Registro y verificación de columnas en SQLite.
2. `test_incidente_persistence_across_sessions`: Persistencia entre reconexiones independientes.
3. `test_incidente_query_filters`: Filtrado combinado por tipo, severidad, estado, drone, confianza y búsqueda.
4. `test_incidente_get_by_id_and_not_found`: Consulta por ID y manejo del 404.
5. `test_incidente_update_lifecycle`: Transiciones de estado (reportado -> en_revision -> atendido).
6. `test_incidente_deletion`: Borrado físico y verificación en SQLite.
7. `test_deduplication_rule_identical_frames`: Verificación de deduplicación espacio-temporal vs `allow_duplicate=true`.
8. `test_invalid_data_validation`: Rechazo de tipos inválidos, textos vacíos, coordenadas no finitas y confianza fuera de rango.
9. `test_database_error_handling_resilience`: Simulación de bloqueo de BD (`OperationalError`) con respuesta controlada y servidor activo.
10. `test_incidente_image_linking_and_retrieval`: Vinculación de imágenes y consulta de fotografía asociada.
11. `test_incident_stats_endpoint`: Cálculo de métricas agregadas.
12. `test_websocket_incident_notifications`: Emisión y recepción de eventos WebSocket en tiempo real.

### 7.1 Ejecución de las Pruebas

Para ejecutar únicamente la suite de incidentes:
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_semana_8_incidentes.py -v
```

Para ejecutar la suite completa de regresión del proyecto (Semanas 5, 6, 7 y 8):
```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/ -v
```

**Resultado de la ejecución completa:**
```
======================= 63 passed, 2 warnings in 12.29s =======================
```
- Total de pruebas pasando: **63 / 63 (100% éxito)**.
- 0 fallos, 0 regresiones.

---

## 8. Informe de Estado de Integración

### ¿Qué funciona al 100%?
- Persistencia confiable de incidentes en SQLite con retención de datos históricos.
- Endpoints completos para crear, consultar, filtrar, paginar, ordenar, obtener estadísticas, actualizar y eliminar incidentes.
- Deduplicación espacio-temporal para evitar alertas repetidas en ráfaga.
- Vinculación bidireccional entre incidentes y fotografías capturadas (`imagen_id`, `imagen_url`).
- Tolerancia a fallos con `db.rollback()` ante bloqueos o errores de SQLite.
- Integración en tiempo real con WebSocket para clientes del dashboard React.
- Componente frontend `IncidentLog` con filtros dinámicos, visualización de fotografía vinculada y eliminación controlada.

### ¿Qué no funciona o tiene limitaciones conocidas?
- En el entorno de simulación Webots no se dispone de sensor GPS real, por lo que la ubicación reportada corresponde honestamente a coordenadas cartesianas métricas locales de simulación (`pos_x`, `pos_y`, `pos_z`), y `gps_coords` permanece como `None` deliberadamente.
- El modelo `yolov8n.pt` actual es un modelo general preentrenado con COCO; las clasificaciones viales se infieren según las reglas de negocio de la Semana 6 hasta contar con pesos especializados entrenados específicamente para vías férreas colombianas.

### ¿Qué falta integrar en semanas posteriores?
- Módulo de generación de reportes y exportación en formatos PDF o Excel.
- Sistema de analítica predictiva de desgaste vial basado en la frecuencia acumulada de incidentes por tramo kilométrico.
- Integración con autenticación de usuarios y roles de operador de vía vs auditor de infraestructura.
