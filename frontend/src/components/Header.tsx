import { useState, useEffect, type FC } from 'react';
import { Activity, Wifi, Radio, Shield, Plane, Cpu, RefreshCw } from 'lucide-react';
import type { DetectionStatus } from '../types';
import type { WsConnectionState } from '../hooks/useWebSocket';

interface HeaderProps {
  isWsConnected: boolean;
  wsState?: WsConnectionState;
  reconnectAttempts?: number;
  isApiOnline: boolean;
  droneStatus?: string;
  droneName?: string;
  hasTelemetry?: boolean;
  detectionStatus?: DetectionStatus | null;
  onManualSync?: () => void;
  isSyncing?: boolean;
}

export const Header: FC<HeaderProps> = ({
  isWsConnected,
  wsState = 'connecting',
  reconnectAttempts = 0,
  isApiOnline,
  droneStatus = 'sin_senal',
  droneName = 'Dron en Espera',
  hasTelemetry = false,
  detectionStatus = null,
  onManualSync,
  isSyncing = false
}) => {
  const [time, setTime] = useState<string>('--:--:--');

  useEffect(() => {
    const updateClock = () => setTime(new Date().toLocaleTimeString());
    const initTimer = setTimeout(updateClock, 0);
    const timer = setInterval(updateClock, 1000);
    return () => {
      clearTimeout(initTimer);
      clearInterval(timer);
    };
  }, []);

  const getWsLabel = () => {
    if (isWsConnected) return 'WS EN LÍNEA';
    if (wsState === 'reconnecting' && reconnectAttempts > 0) {
      return `WS RECONECTANDO (${reconnectAttempts})`;
    }
    if (wsState === 'connecting') return 'WS CONECTANDO...';
    return 'WS DESCONECTADO';
  };

  return (
    <header className="header-container">
      <div className="header-left">
        <div className="logo-shield">
          <Shield className="logo-icon text-cyan" />
        </div>
        <div>
          <h1 className="header-title">SISTEMA DE VIGILANCIA Y ESCANEO CON DRON</h1>
          <p className="header-subtitle">
            Monitoreo en Vías de Ciénaga · Detección de Postes, Vegetación Invasiva y Obstrucciones
          </p>
        </div>
      </div>

      <div className="header-center">
        <div className="drone-pill" title={hasTelemetry ? 'Telemetría del dron activa' : 'Sin telemetría en tiempo real recibida'}>
          <Plane className="drone-pill-icon" />
          <span className="drone-name">{droneName}</span>
          <span className={`status-badge status-${hasTelemetry ? droneStatus : 'standby'}`}>
            {hasTelemetry ? droneStatus.toUpperCase() : 'SIN TELEMETRÍA'}
          </span>
        </div>
      </div>

      <div className="header-right">
        {/* API Status */}
        <div
          className="indicator-chip"
          title={isApiOnline ? 'Servidor FastAPI REST conectado (/health OK)' : 'Servidor FastAPI REST sin conexión'}
        >
          <Activity size={14} className={isApiOnline ? 'text-green' : 'text-red'} />
          <span className="indicator-label">{isApiOnline ? 'API ONLINE' : 'API OFFLINE'}</span>
          <span className={`dot ${isApiOnline ? 'dot-active' : 'dot-inactive'}`}></span>
        </div>

        {/* WebSocket Status */}
        <div
          className="indicator-chip"
          title={
            isWsConnected
              ? 'Canal WebSocket conectado en tiempo real'
              : 'Canal WebSocket en reconexión automática'
          }
        >
          <Wifi size={14} className={isWsConnected ? 'text-cyan' : 'text-amber'} />
          <span className="indicator-label">{getWsLabel()}</span>
          <span className={`dot ${isWsConnected ? 'dot-active' : 'dot-inactive'}`}></span>
        </div>

        {/* Vision IA Model / Detector Status */}
        <div
          className="indicator-chip"
          title={
            !isApiOnline
              ? 'Sin conexión con el motor de visión del backend'
              : detectionStatus?.yolo_ready
              ? `YOLO Real Activo (${detectionStatus.active_model}) en ${detectionStatus.device.toUpperCase()} - Modo: ${detectionStatus.model_mode}`
              : detectionStatus?.is_fallback
              ? `Fallback Heurístico Activo (OpenCV). Causa: ${detectionStatus.load_error || 'Pesos no disponibles'}`
              : detectionStatus?.is_diagnostic
              ? 'Modo Diagnóstico Activo'
              : 'Motor de visión IA'
          }
        >
          <Cpu
            size={14}
            className={
              !isApiOnline
                ? 'text-red'
                : detectionStatus?.yolo_ready
                ? 'text-cyan'
                : detectionStatus?.is_fallback
                ? 'text-amber'
                : 'text-red'
            }
          />
          <span className="indicator-label">
            {!isApiOnline
              ? 'IA SIN CONEXIÓN'
              : detectionStatus?.yolo_ready
              ? `YOLO (${detectionStatus.device.toUpperCase()})`
              : detectionStatus?.is_fallback
              ? 'FALLBACK OPENCV'
              : detectionStatus?.is_diagnostic
              ? 'IA DIAGNÓSTICO'
              : 'IA STANDBY'}
          </span>
          <span
            className={`dot ${
              isApiOnline && detectionStatus?.is_available ? 'dot-active' : 'dot-inactive'
            }`}
          ></span>
        </div>

        {/* Manual Sync / Reconnect Button */}
        {onManualSync && (
          <button
            type="button"
            className="btn-sync-header"
            onClick={onManualSync}
            disabled={isSyncing}
            title="Sincronizar estado con el backend y reconectar canales"
          >
            <RefreshCw size={14} className={isSyncing ? 'spin-icon' : ''} />
            <span>{isSyncing ? 'Sincronizando...' : 'Sincronizar'}</span>
          </button>
        )}

        {/* Clock */}
        <div className="time-badge">
          <Radio size={14} className="text-cyan animate-pulse" />
          <span>{time}</span>
        </div>
      </div>
    </header>
  );
};
