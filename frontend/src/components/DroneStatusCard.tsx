import { useState, type FC } from 'react';
import {
  Battery,
  BatteryCharging,
  Gauge,
  Compass,
  Play,
  Square,
  Pause,
  Home,
  CheckCircle2,
  AlertTriangle,
  WifiOff
} from 'lucide-react';
import type { TelemetryData } from '../types';
import { api } from '../services/api';

interface DroneStatusCardProps {
  telemetry: TelemetryData | null;
  droneId: string;
  isApiOnline?: boolean;
}

export const DroneStatusCard: FC<DroneStatusCardProps> = ({
  telemetry,
  droneId,
  isApiOnline = true
}) => {
  const [actionResult, setActionResult] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [loadingCmd, setLoadingCmd] = useState(false);

  const hasTelemetry = telemetry !== null;
  const battery = telemetry?.battery ?? null;
  const speed = telemetry?.speed ?? null;
  const altitude = telemetry?.pos_z ?? null;
  const mode = telemetry?.flight_mode ?? null;

  const handleCommand = async (command: string) => {
    setLoadingCmd(true);
    setActionResult(null);
    try {
      const res = await api.sendDroneCommand(droneId, command);
      setActionResult({ type: 'success', text: res.message || `Comando '${command}' enviado` });
      setTimeout(() => setActionResult(null), 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al enviar comando al dron';
      setActionResult({ type: 'error', text: msg });
    } finally {
      setLoadingCmd(false);
    }
  };

  const getBatteryColor = (level: number | null) => {
    if (level === null) return '#64748b';
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
        <span className="drone-tag">{telemetry?.drone_id || droneId}</span>
      </div>

      {!hasTelemetry && (
        <div className="telemetry-empty-banner">
          <WifiOff size={14} className="text-amber flex-shrink-0" />
          <span>
            Sin telemetría activa para <strong>{droneId}</strong>. Los indicadores se actualizarán al recibir datos reales del backend.
          </span>
        </div>
      )}

      <div className="telemetry-metrics-grid">
        {/* Battery Indicator */}
        <div className="metric-box">
          <div className="metric-header">
            <span className="metric-label">BATERÍA</span>
            {battery !== null && battery < 20 ? (
              <Battery className="text-red animate-pulse" size={18} />
            ) : (
              <BatteryCharging className={battery !== null ? 'text-green' : 'text-muted'} size={18} />
            )}
          </div>
          <div className="metric-value" style={{ color: getBatteryColor(battery) }}>
            {battery !== null ? `${battery.toFixed(1)}%` : '--%'}
          </div>
          <div className="battery-bar-bg">
            <div
              className="battery-bar-fill"
              style={{
                width: `${battery !== null ? Math.min(100, Math.max(0, battery)) : 0}%`,
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
            {altitude !== null ? altitude.toFixed(2) : '--'}{' '}
            <span className="metric-unit">m</span>
          </div>
          <span className="metric-footer">Marco local Webots</span>
        </div>

        {/* Speed Indicator */}
        <div className="metric-box">
          <div className="metric-header">
            <span className="metric-label">VELOCIDAD</span>
            <Gauge className="text-amber" size={18} />
          </div>
          <div className="metric-value text-amber">
            {speed !== null ? speed.toFixed(1) : '--'}{' '}
            <span className="metric-unit">m/s</span>
          </div>
          <span className="metric-footer">
            {speed !== null ? `${(speed * 3.6).toFixed(1)} km/h` : 'Sin lectura'}
          </span>
        </div>

        {/* Flight Mode & Mission State */}
        <div className="metric-box">
          <div className="metric-header">
            <span className="metric-label">ESTADO MISIÓN</span>
            <CheckCircle2 className={mode ? 'text-green' : 'text-muted'} size={18} />
          </div>
          <div className="metric-value text-emerald mode-title">
            {mode ? mode.toUpperCase() : 'SIN SEÑAL'}
          </div>
          <span className="metric-footer">
            {telemetry?.current_waypoint != null
              ? `Waypoint #${telemetry.current_waypoint}`
              : telemetry?.current_mission || 'En espera de misión'}
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
            type="button"
            className="btn btn-primary"
            disabled={loadingCmd || !isApiOnline}
            onClick={() => handleCommand('takeoff')}
          >
            <Play size={15} /> Despegar
          </button>
          <button
            type="button"
            className="btn btn-warning"
            disabled={loadingCmd || !isApiOnline}
            onClick={() => handleCommand('hover')}
          >
            <Pause size={15} /> Mantener
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={loadingCmd || !isApiOnline}
            onClick={() => handleCommand('resume_patrol')}
          >
            <Play size={15} /> Patrullar Vía
          </button>
          <button
            type="button"
            className="btn btn-danger"
            disabled={loadingCmd || !isApiOnline}
            onClick={() => handleCommand('land')}
          >
            <Square size={15} /> Aterrizar
          </button>
          <button
            type="button"
            className="btn btn-info"
            disabled={loadingCmd || !isApiOnline}
            onClick={() => handleCommand('return_to_home')}
          >
            <Home size={15} /> Regreso (RTH)
          </button>
        </div>

        {actionResult && (
          <div
            className={`action-notification ${
              actionResult.type === 'error' ? 'action-notification-error' : ''
            }`}
          >
            {actionResult.type === 'error' ? (
              <AlertTriangle size={14} className="text-red flex-shrink-0" />
            ) : (
              <CheckCircle2 size={14} className="text-cyan flex-shrink-0" />
            )}
            <span>{actionResult.text}</span>
          </div>
        )}
      </div>
    </div>
  );
};
