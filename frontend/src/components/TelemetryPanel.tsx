import type { FC } from 'react';
import { Navigation, Compass } from 'lucide-react';
import type { TelemetryData } from '../types';

interface TelemetryPanelProps {
  telemetry: TelemetryData | null;
}

export const TelemetryPanel: FC<TelemetryPanelProps> = ({ telemetry }) => {

  const posX = telemetry ? telemetry.pos_x : 0.0;
  const posY = telemetry ? telemetry.pos_y : 0.0;
  const posZ = telemetry ? telemetry.pos_z : 0.0;
  const roll = telemetry ? telemetry.roll : 0.0;
  const pitch = telemetry ? telemetry.pitch : 0.0;
  const yaw = telemetry ? telemetry.yaw : 0.0;

  // Convert radians to degrees for readability
  const rollDeg = (roll * (180 / Math.PI)).toFixed(1);
  const pitchDeg = (pitch * (180 / Math.PI)).toFixed(1);
  const yawDeg = (((yaw * (180 / Math.PI)) % 360 + 360) % 360).toFixed(0);

  return (
    <div className="card telemetry-panel-card">
      <div className="card-header">
        <div className="card-title-group">
          <Navigation className="card-icon text-cyan" />
          <h2 className="card-title">POSICIONAMIENTO ESPACIAL Y NAVEGACIÓN</h2>
        </div>
      </div>

      <div className="telemetry-grid">
        {/* Coordinates 3D */}
        <div className="coords-container">
          <div className="coord-item">
            <span className="coord-axis text-red">X (Este)</span>
            <span className="coord-value">{posX.toFixed(2)} m</span>
          </div>
          <div className="coord-item">
            <span className="coord-axis text-green">Y (Norte)</span>
            <span className="coord-value">{posY.toFixed(2)} m</span>
          </div>
          <div className="coord-item">
            <span className="coord-axis text-cyan">Z (Altitud)</span>
            <span className="coord-value">{posZ.toFixed(2)} m</span>
          </div>
        </div>

        {/* Orientation / Attitude */}
        <div className="attitude-container">
          <div className="attitude-box">
            <span className="attitude-label">ROLL (Alabeo)</span>
            <span className="attitude-value">{rollDeg}°</span>
            <div className="meter-bar">
              <div
                className="meter-indicator"
                style={{ left: `${Math.min(Math.max((Number(rollDeg) + 45) / 90 * 100, 0), 100)}%` }}
              ></div>
            </div>
          </div>

          <div className="attitude-box">
            <span className="attitude-label">PITCH (Cabeceo)</span>
            <span className="attitude-value">{pitchDeg}°</span>
            <div className="meter-bar">
              <div
                className="meter-indicator"
                style={{ left: `${Math.min(Math.max((Number(pitchDeg) + 45) / 90 * 100, 0), 100)}%` }}
              ></div>
            </div>
          </div>

          <div className="attitude-box">
            <span className="attitude-label">RUMBO (Yaw / Brújula)</span>
            <div className="compass-heading">
              <Compass size={18} className="text-cyan inline mr-1" />
              <span className="attitude-value">{yawDeg}°</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
