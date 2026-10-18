import { useState, useEffect, type FC } from 'react';
import { Activity, Wifi, Radio, Shield, Plane, Cpu } from 'lucide-react';
import type { DetectionStatus } from '../types';

interface HeaderProps {
  isWsConnected: boolean;
  isApiOnline: boolean;
  droneStatus?: string;
  droneName?: string;
  detectionStatus?: DetectionStatus | null;
}

export const Header: FC<HeaderProps> = ({
  isWsConnected,
  isApiOnline,
  droneStatus = 'idle',
  droneName = 'Mavic 2 Pro - Webots',
  detectionStatus = null
}) => {
  const [time, setTime] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="header-container">
      <div className="header-left">
        <div className="logo-shield">
          <Shield className="logo-icon text-cyan" />
        </div>
        <div>
          <h1 className="header-title">SISTEMA DE VIGILANCIA Y ESCANEO CON DRON</h1>
          <p className="header-subtitle">
            Monitoreo en Vías Ferroviarias y Carreteras · Detección de Postes, Vegetación y Obstrucciones
          </p>
        </div>
      </div>

      <div className="header-center">
        <div className="drone-pill">
          <Plane className="drone-pill-icon" />
          <span className="drone-name">{droneName}</span>
          <span className={`status-badge status-${droneStatus}`}>
            {droneStatus.toUpperCase()}
          </span>
        </div>
      </div>

      <div className="header-right">
        {/* API Status */}
        <div className="indicator-chip" title="REST API Endpoint Status">
          <Activity size={14} className={isApiOnline ? 'text-green' : 'text-red'} />
          <span className="indicator-label">REST API</span>
          <span className={`dot ${isApiOnline ? 'dot-active' : 'dot-inactive'}`}></span>
        </div>

        {/* WebSocket Status */}
        <div className="indicator-chip" title="WebSocket Real-Time Feed">
          <Wifi size={14} className={isWsConnected ? 'text-cyan' : 'text-yellow'} />
          <span className="indicator-label">TELEMETRÍA WS</span>
          <span className={`dot ${isWsConnected ? 'dot-active' : 'dot-inactive'}`}></span>
        </div>

        {/* Vision IA Model / Detector Status */}
        <div
          className="indicator-chip"
          title={
            detectionStatus?.yolo_ready
              ? `YOLO Real Activo (${detectionStatus.active_model}) en ${detectionStatus.device.toUpperCase()} - Modo: ${detectionStatus.model_mode}`
              : detectionStatus?.is_fallback
              ? `Fallback Heurístico Activo (OpenCV). Causa: ${detectionStatus.load_error || 'Pesos no disponibles'}`
              : 'Motor de visión IA'
          }
        >
          <Cpu
            size={14}
            className={
              detectionStatus?.yolo_ready
                ? 'text-cyan'
                : detectionStatus?.is_fallback
                ? 'text-yellow'
                : 'text-red'
            }
          />
          <span className="indicator-label">
            {detectionStatus?.yolo_ready
              ? `YOLO (${detectionStatus.device.toUpperCase()})`
              : detectionStatus?.is_fallback
              ? 'FALLBACK OPENCV'
              : 'IA STANDBY'}
          </span>
          <span
            className={`dot ${
              detectionStatus?.is_available ? 'dot-active' : 'dot-inactive'
            }`}
          ></span>
        </div>

        {/* Clock */}
        <div className="time-badge">
          <Radio size={14} className="text-cyan animate-pulse" />
          <span>{time}</span>
        </div>
      </div>
    </header>
  );
};
