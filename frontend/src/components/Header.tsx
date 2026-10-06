import { useState, useEffect, type FC } from 'react';
import { Activity, Wifi, Radio, Shield, Plane } from 'lucide-react';

interface HeaderProps {
  isWsConnected: boolean;
  isApiOnline: boolean;
  droneStatus?: string;
  droneName?: string;
}

export const Header: FC<HeaderProps> = ({

  isWsConnected,
  isApiOnline,
  droneStatus = 'idle',
  droneName = 'Mavic 2 Pro - Webots'
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

        {/* Clock */}
        <div className="time-badge">
          <Radio size={14} className="text-cyan animate-pulse" />
          <span>{time}</span>
        </div>
      </div>
    </header>
  );
};
