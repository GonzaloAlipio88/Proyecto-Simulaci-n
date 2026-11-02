export interface Drone {
  id: string;
  name: string;
  model: string;
  status: 'idle' | 'flying' | 'hovering' | 'returning' | 'landed' | 'emergency';
  battery_level: number;
  current_x: number;
  current_y: number;
  current_z: number;
  current_speed: number;
  flight_mode: string;
  last_seen_at?: string;
}

export interface TelemetryData {
  id?: number;
  drone_id: string;
  timestamp: string;
  pos_x: number;
  pos_y: number;
  pos_z: number;
  roll: number;
  pitch: number;
  yaw: number;
  speed: number;
  battery: number;
  flight_mode: string;
  current_waypoint?: number;
  current_mission?: string;
  state_description?: string;
}


export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

export interface DetectionItem {
  id?: string;
  label: 'poste_luz' | 'vegetacion_invasiva' | 'obstruccion_via' | 'otro' | string;
  normalized_category?: 'poste_luz' | 'vegetacion_invasiva' | 'obstruccion_via' | 'otro' | string;
  raw_label?: string;
  confidence: number;
  bbox: BoundingBox;
  severity: 'baja' | 'media' | 'alta' | 'critica';
  review_status?: 'reportado' | 'pendiente_revision' | 'confirmado' | 'descartado';
  description?: string;
  justification?: string;
  timestamp?: string;
  simulation_coords?: {
    pos_x: number;
    pos_y: number;
    pos_z: number;
  } | null;
  coordinate_system?: string;
  is_duplicate?: boolean;
  repetition_count?: number;
  is_incident_candidate?: boolean;
}

export interface CameraFrameStream {
  drone_id: string;
  timestamp: string;
  frame_base64: string;
  detections: DetectionItem[];
  total_detected: number;
  total_raw?: number;
  inference_time_ms: number;
  classification_time_ms?: number;
  image_id: number;
  width?: number;
  height?: number;
  is_fresh?: boolean;
}

export interface Incidente {
  id: number;
  drone_id: string;
  tipo: 'poste_luz' | 'vegetacion_invasiva' | 'obstruccion_via' | 'otro';
  severidad: 'baja' | 'media' | 'alta' | 'critica';
  descripcion: string;
  pos_x?: number | null;
  pos_y?: number | null;
  pos_z?: number | null;
  coordenadas_tipo?: string;
  confidence: number;
  imagen_id?: number | null;
  imagen_url?: string | null;
  estado: 'reportado' | 'en_revision' | 'atendido' | 'descartado';
  timestamp: string;
}

export interface IncidenteStats {
  total_incidentes: number;
  por_tipo: Record<string, number>;
  por_severidad: Record<string, number>;
  por_estado: Record<string, number>;
  con_imagen: number;
  sin_imagen: number;
  confianza_promedio: number;
  ultimo_incidente_timestamp?: string | null;
}


export interface CameraStatus {
  is_active: boolean;
  last_frame_timestamp?: string;
  resolution: string;
  fps: number;
  connected_drones: string[];
}

export interface DetectionStatus {
  model_type: string;
  is_loaded: boolean;
  confidence_threshold: number;
  yolo_ready: boolean;
  yolo_model_loaded: boolean;
  configured_model_type: string;
  ultralytics_available: boolean;
  weights_path?: string;
  weights_exist: boolean;
  active_model: string;
  backend: string;
  device: string;
  is_available: boolean;
  is_fallback: boolean;
  is_diagnostic: boolean;
  model_mode?: string;
  load_error?: string | null;
  last_inference_error?: string | null;
  classes?: string[];
  total_classes?: number;
}

export interface ImageDimensions {
  width: number;
  height: number;
  channels: number;
}

export interface ModelInfo {
  name: string;
  backend: string;
  is_available: boolean;
  is_fallback: boolean;
  is_diagnostic: boolean;
  model_mode?: string;
  device: string;
  warnings: string[];
}

export interface ImageAnalysisResponse {
  analysis_id: string;
  original_filename: string;
  stored_filename?: string | null;
  dimensions: ImageDimensions;
  format: string;
  size_bytes: number;
  timestamp: string;
  status: 'success' | 'no_detections' | 'error';
  detections: DetectionItem[];
  total_detected: number;
  total_valid: number;
  total_rejected: number;
  has_location: boolean;
  simulation_coords?: {
    pos_x: number;
    pos_y: number;
    pos_z: number;
  } | null;
  gps_coords?: Record<string, any> | null;
  location_notice: string;
  inference_time_ms: number;
  classification_time_ms: number;
  processing_time_ms: number;
  model_info: ModelInfo;
  image_id?: number | null;
  original_image_url?: string | null;
  annotated_image_url?: string | null;
  annotated_image_base64?: string | null;
}

