import { useMemo, type FC } from 'react';
import { Video, Scan, AlertTriangle, Cpu, Layers, Clock, WifiOff, RefreshCw } from 'lucide-react';
import type { CameraFrameStream, CameraStatus } from '../types';

interface LiveCameraFeedProps {
  streamData: CameraFrameStream | null;
  cameraStatus?: CameraStatus | null;
  droneId: string;
  isApiOnline?: boolean;
  onRefreshSnapshot?: () => void;
  isRefreshingSnapshot?: boolean;
}

export const LiveCameraFeed: FC<LiveCameraFeedProps> = ({
  streamData,
  cameraStatus = null,
  droneId,
  isApiOnline = true,
  onRefreshSnapshot,
  isRefreshingSnapshot = false
}) => {
  const frameBase64 = streamData?.frame_base64;
  const latency = streamData?.inference_time_ms;
  const count = streamData?.total_detected ?? 0;
  const width = streamData?.width;
  const height = streamData?.height;
  const isFresh = streamData?.is_fresh !== false;
  const streamTimestamp = streamData?.timestamp;

  const captureLabel = useMemo(() => {
    if (!streamTimestamp) return null;
    try {
      return new Date(streamTimestamp).toLocaleTimeString('es-CO', { hour12: false });
    } catch {
      return null;
    }
  }, [streamTimestamp]);

  const resolutionLabel =
    width && height ? `${width}×${height}` : cameraStatus?.resolution || 'Sin resolución';

  return (
    <div className="card camera-feed-card">
      <div className="card-header">
        <div className="card-title-group">
          <Video className="card-icon text-cyan" />
          <h2 className="card-title">CÁMARA DE ESCANEO EN TIEMPO REAL (WEBOTS)</h2>
        </div>
        <div className="camera-badges">
          {latency !== undefined && (
            <span className="badge badge-fps" title="Tiempo de inferencia del fotograma">
              <Cpu size={12} className="inline mr-1" /> {latency.toFixed(1)} ms
            </span>
          )}
          <span className="badge badge-res">{resolutionLabel}</span>
          {frameBase64 ? (
            <span className={`badge ${isFresh ? 'badge-live' : 'badge-stale'}`}>
              {isFresh ? (
                <>
                  <span className="live-dot"></span>EN VIVO
                </>
              ) : (
                <>
                  <WifiOff size={12} className="inline mr-1" />
                  FOTOGRAMA EN CACHÉ
                </>
              )}
            </span>
          ) : (
            <span className="badge badge-standby">
              <WifiOff size={12} className="inline mr-1" />
              SIN SEÑAL
            </span>
          )}
          {onRefreshSnapshot && isApiOnline && (
            <button
              type="button"
              className="btn-icon-mini"
              onClick={onRefreshSnapshot}
              disabled={isRefreshingSnapshot}
              title="Consultar último fotograma disponible en el backend"
            >
              <RefreshCw size={12} className={isRefreshingSnapshot ? 'spin-icon' : ''} />
            </button>
          )}
        </div>
      </div>

      {/* Target Monitored Classes Legend */}
      <div className="detection-legend">
        <div className="legend-item">
          <span className="legend-indicator legend-pole"></span>
          <span className="legend-label">1. Postes de Luz (poste_luz)</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator legend-veg"></span>
          <span className="legend-label">2. Vegetación Invasiva (vegetacion_invasiva)</span>
        </div>
        <div className="legend-item">
          <span className="legend-indicator legend-obs"></span>
          <span className="legend-label">3. Obstrucción en Vías (obstruccion_via)</span>
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
                  Última captura almacenada · Sin transmisión continua activa
                </div>
              )}

              {/* In-view alerts */}
              {count > 0 && (
                <div className="in-view-alert">
                  <AlertTriangle size={15} className="text-amber" />
                  <span>{count} DETECCIÓN(ES) EN CUADRO</span>
                </div>
              )}
            </div>
          </div>
        ) : !isApiOnline ? (
          <div className="camera-standby">
            <WifiOff size={44} className="text-red opacity-80" />
            <p className="standby-text">Servidor Backend sin conexión</p>
            <span className="standby-subtext">
              Esperando reconexión con FastAPI para recibir fotogramas de cámara y telemetría.
            </span>
          </div>
        ) : (
          <div className="camera-standby">
            <Scan size={48} className="text-cyan animate-pulse" />
            <p className="standby-text">Sin transmisión de video activa desde Webots</p>
            <span className="standby-subtext">
              Inicie el controlador en Webots o utilice la sección inferior para analizar fotografías JPG/PNG manualmente.
            </span>
          </div>
        )}
      </div>

      {/* Detection Counter Bar */}
      <div className="camera-footer">
        <div className="detection-summary">
          <Layers size={14} className="text-cyan mr-1 inline" />
          <span>
            Objetos detectados en cuadro actual:{' '}
            <strong>{frameBase64 ? count : 'Sin fotograma'}</strong>
          </span>
        </div>
        <div className="drone-subinfo">
          <span>
            Fuente: <strong>{streamData?.drone_id || droneId}</strong>
            {streamData?.image_id ? ` · Imagen #${streamData.image_id}` : ''}
          </span>
        </div>
      </div>
    </div>
  );
};
