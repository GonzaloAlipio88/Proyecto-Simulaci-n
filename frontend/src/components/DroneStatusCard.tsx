import { useState, type FC } from 'react';
import { Battery, BatteryCharging, Gauge, Compass, Play, Square, Pause, Home, CheckCircle2 } from 'lucide-react';
import type { TelemetryData } from '../types';
import { api } from '../services/api';

interface DroneStatusCardProps {
  telemetry: TelemetryData | null;
  droneId: string;
}

export const DroneStatusCard: FC<DroneStatusCardProps> = ({ telemetry, droneId }) => {

  const [lastAction, setLastAction] = useState<string | null>(null);
  const [loadingCmd, setLoadingCmd] = useState(false);

  const battery = telemetry ? telemetry.battery : 100.0;
  const speed = telemetry ? telemetry.speed : 0.0;
  const altitude = telemetry ? telemetry.pos_z : 0.0;
  const mode = telemetry ? telemetry.flight_mode : 'STANDBY';

  const handleCommand = async (command: string) => {
    setLoadingCmd(true);
    try {
      const res = await api.sendDroneCommand(droneId, command);
      setLastAction(res.message);
      setTimeout(() => setLastAction(null), 3500);
    } catch (err: any) {
      setLastAction(`Error: ${err.message}`);
    } finally {
      setLoadingCmd(false);
    }
  };

  const getBatteryColor = (level: number) => {
    if (level > 50) return '#10b981'; // Green
    if (level > 20) return '#f59e0b'; // Amber
    return '#ef4444'; // Red
  };

  return (
    <div className="card drone-status-card">
      <div className="card-header">
        <div className="card-title-group">
          <Gauge className="card-icon text-cyan" />
          <h2 className="card-title">ESTADO DE OPERACIÓN Y VUELO</h2>
        </div>
        <span className="drone-tag">{droneId}</span>
      </div>

      <div className="telemetry-metrics-grid">
        {/* Battery Indicator */}
        <div className="metric-box">
          <div className="metric-header">
            <span className="metric-label">BATERÍA</span>
            {battery < 20 ? (
              <Battery className="text-red animate-pulse" size={18} />
            ) : (
              <BatteryCharging className="text-green" size={18} />
            )}
          </div>
          <div className="metric-value" style={{ color: getBatteryColor(battery) }}>
            {battery.toFixed(1)}%
          </div>
          <div className="battery-bar-bg">
            <div
              className="battery-bar-fill"
              style={{
                width: `${battery}%`,
                backgroundColor: getBatteryColor(battery)
              }}
            ></div>
          </div>
        </div>

        {/* Altitude Indicator */}
        <div className="metric-box">
          <div className="metric-header">
            <span className="metric-label">ALTITUD AGL</span>
            <Compass className="text-cyan" size={18} />
          </div>
          <div className="metric-value text-cyan">
            {altitude.toFixed(2)} <span className="metric-unit">m</span>
          </div>
          <span className="metric-footer">Techo máx: 25.0 m</span>
        </div>

        {/* Speed Indicator */}
        <div className="metric-box">
          <div className="metric-header">
            <span className="metric-label">VELOCIDAD</span>
            <Gauge className="text-amber" size={18} />
          </div>
          <div className="metric-value text-amber">
            {speed.toFixed(1)} <span className="metric-unit">m/s</span>
          </div>
          <span className="metric-footer">{(speed * 3.6).toFixed(1)} km/h</span>
        </div>

        {/* Flight Mode & Mission State */}
        <div className="metric-box">
          <div className="metric-header">
            <span className="metric-label">ESTADO MISIÓN</span>
            <CheckCircle2 className="text-green" size={18} />
          </div>
          <div className="metric-value text-emerald mode-title">
            {mode.toUpperCase()}
          </div>
          <span className="metric-footer">
            {telemetry?.current_waypoint ? `Waypoint #${telemetry.current_waypoint} / 3` : 'Base / Lanzamiento'}
          </span>
        </div>
      </div>

      {/* Real-time Flight Phase & Status Description Banner */}
      {telemetry?.state_description && (
        <div className="mission-state-banner">
          <span className="mission-banner-label">FASE ACTUAL:</span>
          <span className="mission-banner-text">{telemetry.state_description}</span>
        </div>
      )}


      {/* Flight Control Actions */}
      <div className="controls-section">
        <h3 className="section-subtitle">COMANDOS REMOTOS DE MISIÓN</h3>
        <div className="button-group">
          <button
            className="btn btn-primary"
            disabled={loadingCmd}
            onClick={() => handleCommand('takeoff')}
          >
            <Play size={15} /> Despegar
          </button>
          <button
            className="btn btn-warning"
            disabled={loadingCmd}
            onClick={() => handleCommand('hover')}
          >
            <Pause size={15} /> Mantener
          </button>
          <button
            className="btn btn-secondary"
            disabled={loadingCmd}
            onClick={() => handleCommand('resume_patrol')}
          >
            <Play size={15} /> Patrullar Vía
          </button>
          <button
            className="btn btn-danger"
            disabled={loadingCmd}
            onClick={() => handleCommand('land')}
          >
            <Square size={15} /> Aterrizar
          </button>
          <button
            className="btn btn-info"
            disabled={loadingCmd}
            onClick={() => handleCommand('return_to_home')}
          >
            <Home size={15} /> Regreso (RTH)
          </button>
        </div>

        {lastAction && (
          <div className="action-notification">
            <CheckCircle2 size={14} className="text-cyan" />
            <span>{lastAction}</span>
          </div>
        )}
      </div>
    </div>
  );
};
