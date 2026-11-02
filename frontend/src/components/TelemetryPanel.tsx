import type { FC } from 'react';
import { Navigation, Compass, MapPin } from 'lucide-react';
import type { TelemetryData } from '../types';

interface TelemetryPanelProps {
  telemetry: TelemetryData | null;
}

export const TelemetryPanel: FC<TelemetryPanelProps> = ({ telemetry }) => {
  const hasTelemetry = telemetry !== null;
  const posX = telemetry?.pos_x ?? null;
  const posY = telemetry?.pos_y ?? null;
  const posZ = telemetry?.pos_z ?? null;
  const roll = telemetry?.roll ?? 0.0;
  const pitch = telemetry?.pitch ?? 0.0;
  const yaw = telemetry?.yaw ?? 0.0;

  // Convert radians to degrees for readability
  const rollDeg = hasTelemetry ? (roll * (180 / Math.PI)).toFixed(1) : null;
  const pitchDeg = hasTelemetry ? (pitch * (180 / Math.PI)).toFixed(1) : null;
  const yawDeg = hasTelemetry ? (((yaw * (180 / Math.PI)) % 360 + 360) % 360).toFixed(0) : null;

  return (
    <div className="card telemetry-panel-card">
      <div className="card-header">
        <div className="card-title-group">
          <Navigation className="card-icon text-cyan" />
          <h2 className="card-title">POSICIONAMIENTO ESPACIAL Y NAVEGACIÓN</h2>
        </div>
        <span className="coord-system-badge" title="Entorno de simulación Webots (coordenadas cartesianas locales en metros, no GPS)">
          <MapPin size={11} className="inline mr-1" />
          Simulación 3D (m)
        </span>
      </div>

      <div className="telemetry-grid">
        {/* Coordinates 3D */}
        <div className="coords-container">
          <div className="coord-item">
            <span className="coord-axis text-red">X (Este)</span>
            <span className="coord-value">{posX !== null ? `${posX.toFixed(2)} m` : '-- m'}</span>
          </div>
          <div className="coord-item">
            <span className="coord-axis text-green">Y (Norte)</span>
            <span className="coord-value">{posY !== null ? `${posY.toFixed(2)} m` : '-- m'}</span>
          </div>
          <div className="coord-item">
            <span className="coord-axis text-cyan">Z (Altitud)</span>
            <span className="coord-value">{posZ !== null ? `${posZ.toFixed(2)} m` : '-- m'}</span>
          </div>
        </div>

        {/* Orientation / Attitude */}
        <div className="attitude-container">
          <div className="attitude-box">
            <span className="attitude-label">ROLL (Alabeo)</span>
            <span className="attitude-value">{rollDeg !== null ? `${rollDeg}°` : '--°'}</span>
            <div className="meter-bar">
              <div
                className="meter-indicator"
                style={{
                  left: `${
                    rollDeg !== null
                      ? Math.min(Math.max(((Number(rollDeg) + 45) / 90) * 100, 0), 100)
                      : 50
                  }%`
                }}
              ></div>
            </div>
          </div>

          <div className="attitude-box">
            <span className="attitude-label">PITCH (Cabeceo)</span>
            <span className="attitude-value">{pitchDeg !== null ? `${pitchDeg}°` : '--°'}</span>
            <div className="meter-bar">
              <div
                className="meter-indicator"
                style={{
                  left: `${
                    pitchDeg !== null
                      ? Math.min(Math.max(((Number(pitchDeg) + 45) / 90) * 100, 0), 100)
                      : 50
                  }%`
                }}
              ></div>
            </div>
          </div>

          <div className="attitude-box">
            <span className="attitude-label">RUMBO (Yaw / Brújula)</span>
            <div className="compass-heading">
              <Compass size={18} className="text-cyan inline mr-1" />
              <span className="attitude-value">{yawDeg !== null ? `${yawDeg}°` : '--°'}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
