import { useMemo, type FC } from 'react';
import { Video, Scan, AlertTriangle, Cpu, Layers, Clock, WifiOff } from 'lucide-react';
import type { CameraFrameStream } from '../types';

interface LiveCameraFeedProps {
  streamData: CameraFrameStream | null;
  droneId: string;
}

export const LiveCameraFeed: FC<LiveCameraFeedProps> = ({ streamData, droneId }) => {
  const frameBase64 = streamData?.frame_base64;
  const latency = streamData?.inference_time_ms || 0;
  const count = streamData?.total_detected || 0;
  const width = streamData?.width ?? 640;
  const height = streamData?.height ?? 480;
  const isFresh = streamData?.is_fresh !== false; // treat undefined as fresh

  const captureLabel = useMemo(() => {
    if (!streamData?.timestamp) return null;
    try {
      return new Date(streamData.timestamp).toLocaleTimeString('es-CO', { hour12: false });
    } catch {
      return null;
    }
  }, [streamData?.timestamp]);

  return (
    <div className="card camera-feed-card">
      <div className="card-header">
        <div className="card-title-group">
          <Video className="card-icon text-cyan" />
          <h2 className="card-title">CÁMARA DE ESCANEO EN TIEMPO REAL (WEBOTS)</h2>
        </div>
        <div className="camera-badges">
          <span className="badge badge-fps">
            <Cpu size={12} className="inline mr-1" /> {latency.toFixed(1)} ms
          </span>
          <span className="badge badge-res">{width}×{height}</span>
          {frameBase64 && (
            <span className={`badge ${isFresh ? 'badge-live' : 'badge-stale'}`}>
              {isFresh ? (
                <><span className="live-dot"></span>EN VIVO</>
              ) : (
                <><WifiOff size={12} className="inline mr-1" />DATO ANTIGUO</>
              )}
            </span>
          )}
          {!frameBase64 && (
            <span className="badge badge-live">
              <span className="live-dot"></span> EN VIVO
            </span>
          )}
        </div>
      </div>

      {/* Target Monitored Classes Legend */}
      <div className="detection-legend">
        <div className="legend-item">
          <span className="legend-indicator legend-pole"></span>
          <span className="legend-label">1. Postes de Luz</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator legend-veg"></span>
          <span className="legend-label">2. Vegetación Invasiva</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator legend-obs"></span>
          <span className="legend-label">3. Obstrucción en Vías</span>
        </div>
      </div>

      {/* Video / Snapshot Display Frame */}
      <div className="video-viewport">
        {frameBase64 ? (
          <div className="image-wrapper">
            <img
              src={`data:image/jpeg;base64,${frameBase64}`}
              alt="Transmisión del Dron"
              className="camera-image"
            />
            {/* Viewport Crosshair & Reticle HUD */}
            <div className="hud-overlay">
              <div className="reticle-corner top-left"></div>
              <div className="reticle-corner top-right"></div>
              <div className="reticle-corner bottom-left"></div>
              <div className="reticle-corner bottom-right"></div>
              <div className="reticle-center"></div>

              {/* Capture timestamp */}
              {captureLabel && (
                <div className="capture-timestamp">
                  <Clock size={11} className="inline mr-1" />
                  {captureLabel}
                </div>
              )}

              {/* Stale-data warning */}
              {!isFresh && (
                <div className="stale-warning">
                  <WifiOff size={13} className="inline mr-1" />
                  Imagen podría estar desactualizada
                </div>
              )}

              {/* In-view alerts */}
              {count > 0 && (
                <div className="in-view-alert">
                  <AlertTriangle size={15} className="text-amber" />
                  <span>{count} ANOMALÍA(S) DETECTADA(S)</span>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="camera-standby">
            <Scan size={48} className="text-cyan animate-pulse" />
            <p className="standby-text">Esperando flujo de video desde Webots...</p>
            <span className="standby-subtext">
              Inicie el simulador Webots o ejecute `python simulation/mock_webots_runner.py`
            </span>
          </div>
        )}
      </div>

      {/* Detection Counter Bar */}
      <div className="camera-footer">
        <div className="detection-summary">
          <Layers size={14} className="text-cyan mr-1" />
          <span>Objetos detectados en cuadro actual: <strong>{count}</strong></span>
        </div>
        <div className="drone-subinfo">
          <span>Fuente: {droneId}</span>
        </div>
      </div>
    </div>
  );
};


