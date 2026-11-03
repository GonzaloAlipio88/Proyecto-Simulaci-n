import type {
  Drone,
  TelemetryData,
  Incidente,
  IncidenteCreatePayload,
  IncidenteStats,
  CameraStatus,
  CameraFrameInfoResponse,
  DetectionStatus,
  RoadCategoriesConfig,
  ImageAnalysisResponse,
  HealthResponse,
  MissionWaypoint,
  ThresholdResponse
} from '../types';

const RAW_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '');
export const HEALTH_URL = RAW_BASE_URL;
export const API_BASE = `${RAW_BASE_URL}/api/v1`;

async function extractErrorDetail(res: Response, fallbackMessage: string): Promise<string> {
  try {
    const errJson = await res.json();
    if (errJson) {
      if (typeof errJson.detail === 'string') {
        return errJson.detail;
      }
      if (Array.isArray(errJson.detail)) {
        return errJson.detail
          .map((item: { msg?: string; loc?: (string | number)[] }) => item.msg || JSON.stringify(item))
          .join('; ');
      }
    }
  } catch {
    // Response is not JSON
  }
  return `${fallbackMessage} (HTTP ${res.status})`;
}

function normalizeNetworkError(err: unknown, fallbackMessage: string): Error {
  if (err instanceof TypeError && err.message.toLowerCase().includes('fetch')) {
    return new Error(
      `No se pudo conectar con el servidor backend (${RAW_BASE_URL}). Verifique que FastAPI esté activo y accesible.`
    );
  }
  if (err instanceof Error) {
    return err;
  }
  return new Error(fallbackMessage);
}

export const api = {
  // Salud del backend
  checkHealth: async (): Promise<boolean> => {
    try {
      const res = await fetch(`${HEALTH_URL}/health`);
      if (!res.ok) return false;
      const data: HealthResponse = await res.json();
      return data.status === 'online';
    } catch {
      return false;
    }
  },

  // Drones
  getDrones: async (): Promise<Drone[]> => {
    try {
      const res = await fetch(`${API_BASE}/drones`);
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, 'Error al consultar drones registrados'));
      }
      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, 'Error al consultar drones registrados');
    }
  },

  sendDroneCommand: async (
    droneId: string,
    command: string,
    params?: Record<string, unknown>
  ): Promise<{ success: boolean; drone_id: string; command: string; new_status: string; message: string }> => {
    try {
      const res = await fetch(`${API_BASE}/drones/${encodeURIComponent(droneId)}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, params })
      });
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, 'Error enviando comando al dron'));
      }
      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, 'Error enviando comando al dron');
    }
  },

  getMissionWaypoints: async (): Promise<MissionWaypoint[]> => {
    try {
      const res = await fetch(`${API_BASE}/drones/mission/waypoints`);
      if (!res.ok) return [];
      return res.json();
    } catch {
      return [];
    }
  },

  // Telemetría
  getLatestTelemetry: async (droneId: string): Promise<TelemetryData | null> => {
    try {
      const res = await fetch(`${API_BASE}/telemetria/${encodeURIComponent(droneId)}/latest`);
      if (res.status === 404) return null;
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  getTelemetryHistory: async (droneId: string, limit = 50): Promise<TelemetryData[]> => {
    try {
      const res = await fetch(`${API_BASE}/telemetria/${encodeURIComponent(droneId)}/history?limit=${limit}`);
      if (!res.ok) return [];
      return res.json();
    } catch {
      return [];
    }
  },

  // Cámara
  getCameraStatus: async (): Promise<CameraStatus | null> => {
    try {
      const res = await fetch(`${API_BASE}/cameras/status`);
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  getLatestFrame: async (droneId: string): Promise<string | null> => {
    try {
      const res = await fetch(`${API_BASE}/cameras/${encodeURIComponent(droneId)}/latest-frame?annotated=true`);
      if (!res.ok) return null;
      const data: CameraFrameInfoResponse = await res.json();
      return data.frame_base64 || null;
    } catch {
      return null;
    }
  },

  getLatestFrameInfo: async (droneId: string, annotated = true): Promise<CameraFrameInfoResponse | null> => {
    try {
      const res = await fetch(
        `${API_BASE}/cameras/${encodeURIComponent(droneId)}/latest-frame?annotated=${annotated}`
      );
      if (res.status === 404 || !res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  // Incidentes (Semana 8 & 9 - SQLite)
  getIncidentes: async (filters?: {
    tipo?: string;
    severidad?: string;
    estado?: string;
    drone_id?: string;
    min_confidence?: number;
    search?: string;
    has_image?: boolean;
    order_by?: 'asc' | 'desc';
    skip?: number;
    limit?: number;
  }): Promise<Incidente[]> => {
    const query = new URLSearchParams();
    if (filters?.tipo) query.append('tipo', filters.tipo);
    if (filters?.severidad) query.append('severidad', filters.severidad);
    if (filters?.estado) query.append('estado', filters.estado);
    if (filters?.drone_id) query.append('drone_id', filters.drone_id);
    if (filters?.min_confidence !== undefined) query.append('min_confidence', filters.min_confidence.toString());
    if (filters?.search) query.append('search', filters.search);
    if (filters?.has_image !== undefined) query.append('has_image', filters.has_image.toString());
    if (filters?.order_by) query.append('order_by', filters.order_by);
    if (filters?.skip !== undefined) query.append('skip', filters.skip.toString());
    if (filters?.limit) query.append('limit', filters.limit.toString());

    const queryString = query.toString() ? `?${query.toString()}` : '';
    try {
      const res = await fetch(`${API_BASE}/incidentes${queryString}`);
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, 'No se pudieron recuperar los incidentes desde SQLite'));
      }
      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, 'Error de red al consultar incidentes en SQLite');
    }
  },

  getIncidentStats: async (): Promise<IncidenteStats | null> => {
    try {
      const res = await fetch(`${API_BASE}/incidentes/stats`);
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  createIncidente: async (
    payload: IncidenteCreatePayload,
    allowDuplicate = false
  ): Promise<Incidente> => {
    try {
      const query = allowDuplicate ? '?allow_duplicate=true' : '';
      const res = await fetch(`${API_BASE}/incidentes${query}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, 'Error registrando el incidente en SQLite'));
      }
      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, 'Error registrando el incidente en SQLite');
    }
  },

  updateIncidente: async (
    id: number,
    update: { estado?: string; severidad?: string; descripcion?: string }
  ): Promise<Incidente> => {
    try {
      const res = await fetch(`${API_BASE}/incidentes/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(update)
      });
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, `Error actualizando el incidente #${id}`));
      }
      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, `Error actualizando el incidente #${id}`);
    }
  },

  deleteIncidente: async (id: number): Promise<{ success: boolean; message: string; id: number }> => {
    try {
      const res = await fetch(`${API_BASE}/incidentes/${id}`, {
        method: 'DELETE'
      });
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, `Error eliminando el incidente #${id}`));
      }
      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, `Error eliminando el incidente #${id}`);
    }
  },

  getIncidentImageUrl: (incidenteId: number, download = true): string => {
    return `${API_BASE}/incidentes/${incidenteId}/imagen?download=${download}`;
  },

  resolveBackendUrl: (relativeOrAbsoluteUrl?: string | null): string | null => {
    if (!relativeOrAbsoluteUrl) return null;
    if (relativeOrAbsoluteUrl.startsWith('http://') || relativeOrAbsoluteUrl.startsWith('https://')) {
      return relativeOrAbsoluteUrl;
    }
    return `${RAW_BASE_URL}${relativeOrAbsoluteUrl.startsWith('/') ? '' : '/'}${relativeOrAbsoluteUrl}`;
  },

  // Detección / Visión IA Status (Semana 5 & 6)
  getDetectionStatus: async (): Promise<DetectionStatus | null> => {
    try {
      const res = await fetch(`${API_BASE}/deteccion/status`);
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  getDetectionThreshold: async (): Promise<ThresholdResponse | null> => {
    try {
      const res = await fetch(`${API_BASE}/deteccion/threshold`);
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  updateDetectionThreshold: async (threshold: number): Promise<ThresholdResponse> => {
    try {
      const res = await fetch(`${API_BASE}/deteccion/threshold`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold })
      });
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, 'Error actualizando el umbral de confianza'));
      }
      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, 'Error actualizando el umbral de confianza');
    }
  },

  getRoadCategories: async (): Promise<RoadCategoriesConfig | null> => {
    try {
      const res = await fetch(`${API_BASE}/deteccion/categories`);
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  classifyDetections: async (payload: Record<string, unknown>): Promise<unknown> => {
    try {
      const res = await fetch(`${API_BASE}/deteccion/classify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, 'Error ejecutando clasificación de detecciones'));
      }
      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, 'Error ejecutando clasificación de detecciones');
    }
  },

  // Semana 7: Carga y análisis de imágenes JPG/PNG externas
  analyzeImage: async (
    file: File,
    confidenceThreshold?: number,
    saveToStorage = true
  ): Promise<ImageAnalysisResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams();
    if (confidenceThreshold !== undefined) {
      params.append('confidence_threshold', confidenceThreshold.toString());
    }
    params.append('save_to_storage', saveToStorage.toString());

    const queryString = params.toString() ? `?${params.toString()}` : '';
    try {
      const res = await fetch(`${API_BASE}/imagenes/analyze${queryString}`, {
        method: 'POST',
        body: formData
      });

      if (!res.ok) {
        throw new Error(await extractErrorDetail(res, 'Error al analizar la imagen en el servidor'));
      }

      return res.json();
    } catch (err) {
      throw normalizeNetworkError(err, 'Error al enviar la imagen para análisis');
    }
  }
};
