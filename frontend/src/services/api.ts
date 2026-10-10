import type { Drone, TelemetryData, Incidente, CameraStatus } from '../types';

const API_BASE = 'http://127.0.0.1:8000/api/v1';

export const api = {
  // Health
  checkHealth: async (): Promise<boolean> => {
    try {
      const res = await fetch('http://127.0.0.1:8000/health');
      const data = await res.json();
      return data.status === 'online';
    } catch {
      return false;
    }
  },

  // Drones
  getDrones: async (): Promise<Drone[]> => {
    const res = await fetch(`${API_BASE}/drones`);
    if (!res.ok) throw new Error('Error al consultar drones');
    return res.json();
  },

  sendDroneCommand: async (droneId: string, command: string, params?: Record<string, any>) => {
    const res = await fetch(`${API_BASE}/drones/${droneId}/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, params })
    });
    if (!res.ok) throw new Error('Error enviando comando al dron');
    return res.json();
  },

  // Telemetria
  getLatestTelemetry: async (droneId: string): Promise<TelemetryData | null> => {
    try {
      const res = await fetch(`${API_BASE}/telemetria/${droneId}/latest`);
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  },

  getTelemetryHistory: async (droneId: string, limit = 50): Promise<TelemetryData[]> => {
    const res = await fetch(`${API_BASE}/telemetria/${droneId}/history?limit=${limit}`);
    if (!res.ok) return [];
    return res.json();
  },

  // Camera
  getCameraStatus: async (): Promise<CameraStatus> => {
    const res = await fetch(`${API_BASE}/cameras/status`);
    if (!res.ok) throw new Error('Error consultando estado de cámara');
    return res.json();
  },

  getLatestFrame: async (droneId: string): Promise<string | null> => {
    try {
      const res = await fetch(`${API_BASE}/cameras/${droneId}/latest-frame?annotated=true`);
      if (!res.ok) return null;
      const data = await res.json();
      return data.frame_base64 || null;
    } catch {
      return null;
    }
  },

  // Incidentes
  getIncidentes: async (filters?: { tipo?: string; severidad?: string; estado?: string }): Promise<Incidente[]> => {
    const query = new URLSearchParams();
    if (filters?.tipo) query.append('tipo', filters.tipo);
    if (filters?.severidad) query.append('severidad', filters.severidad);
    if (filters?.estado) query.append('estado', filters.estado);

    const res = await fetch(`${API_BASE}/incidentes?${query.toString()}`);
    if (!res.ok) return [];
    return res.json();
  },

  updateIncidente: async (id: number, update: { estado?: string; severidad?: string; descripcion?: string }): Promise<Incidente> => {
    const res = await fetch(`${API_BASE}/incidentes/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(update)
    });
    if (!res.ok) throw new Error('Error actualizando incidente');
    return res.json();
  }
};
