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
  label: 'poste_luz' | 'vegetacion_invasiva' | 'obstruccion_via' | string;
  confidence: number;
  bbox: BoundingBox;
  severity: 'baja' | 'media' | 'alta' | 'critica';
  description?: string;
}

export interface CameraFrameStream {
  drone_id: string;
  timestamp: string;
  frame_base64: string;
  detections: DetectionItem[];
  total_detected: number;
  inference_time_ms: number;
  image_id: number;
}

export interface Incidente {
  id: number;
  drone_id: string;
  tipo: 'poste_luz' | 'vegetacion_invasiva' | 'obstruccion_via' | 'otro';
  severidad: 'baja' | 'media' | 'alta' | 'critica';
  descripcion: string;
  pos_x: number;
  pos_y: number;
  pos_z: number;
  confidence: number;
  imagen_id?: number;
  estado: 'reportado' | 'en_revision' | 'atendido' | 'descartado';
  timestamp: string;
}

export interface CameraStatus {
  is_active: boolean;
  last_frame_timestamp?: string;
  resolution: string;
  fps: number;
  connected_drones: string[];
}
