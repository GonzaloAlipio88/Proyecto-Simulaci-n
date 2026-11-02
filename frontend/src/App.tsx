import { useState, useEffect, useCallback } from 'react';
import { WifiOff, RefreshCw, AlertTriangle } from 'lucide-react';
import { Header } from './components/Header';
import { DroneStatusCard } from './components/DroneStatusCard';
import { LiveCameraFeed } from './components/LiveCameraFeed';
import { TelemetryPanel } from './components/TelemetryPanel';
import { DetectionViewer } from './components/DetectionViewer';
import { IncidentLog } from './components/IncidentLog';
import { ImageAnalysisSection } from './components/ImageAnalysisSection';
import { useWebSocket } from './hooks/useWebSocket';
import { api, HEALTH_URL } from './services/api';
import type {
  DetectionStatus,
  RoadCategoriesConfig,
  CameraStatus,
  TelemetryData,
  CameraFrameStream,
  ImageAnalysisResponse,
  Incidente,
  Drone
} from './types';
import './App.css';

export function App() {
  const {
    isConnected: isWsConnected,
    wsState,
    reconnectAttempts,
    latestTelemetry: wsTelemetry,
    latestStream: wsStream,
    latestIncident: wsIncident,
    latestUpdatedIncident: wsUpdatedIncident,
    latestDeletedIncident: wsDeletedIncident,
    reconnectNow
  } = useWebSocket();

  const [isApiOnline, setIsApiOnline] = useState<boolean>(false);
  const [hasCheckedInitialHealth, setHasCheckedInitialHealth] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [isRefreshingSnapshot, setIsRefreshingSnapshot] = useState<boolean>(false);

  const [registeredDrone, setRegisteredDrone] = useState<Drone | null>(null);
  const [restTelemetry, setRestTelemetry] = useState<TelemetryData | null>(null);
  const [restSnapshot, setRestSnapshot] = useState<CameraFrameStream | null>(null);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus | null>(null);
  const [detectionStatus, setDetectionStatus] = useState<DetectionStatus | null>(null);
  const [categoriesConfig, setCategoriesConfig] = useState<RoadCategoriesConfig | null>(null);

  const [lastImageAnalysis, setLastImageAnalysis] = useState<ImageAnalysisResponse | null>(null);
  const [newlyCreatedIncident, setNewlyCreatedIncident] = useState<Incidente | null>(null);

  const activeTelemetry = wsTelemetry ?? restTelemetry;
  const activeStream = wsStream ?? restSnapshot;
  const activeDroneId =
    activeTelemetry?.drone_id ||
    activeStream?.drone_id ||
    registeredDrone?.id ||
    cameraStatus?.connected_drones?.[0] ||
    'drone-webots-01';

  const activeDroneName = registeredDrone?.name || `Dron (${activeDroneId})`;

  const handleRefreshSnapshot = useCallback(
    async (targetDroneId?: string) => {
      const idToFetch = targetDroneId || activeDroneId;
      setIsRefreshingSnapshot(true);
      try {
        const frameInfo = await api.getLatestFrameInfo(idToFetch, true);
        if (frameInfo && frameInfo.available && frameInfo.frame_base64) {
          setRestSnapshot({
            drone_id: frameInfo.drone_id,
            timestamp: frameInfo.captured_at || new Date().toISOString(),
            frame_base64: frameInfo.frame_base64,
            detections: [],
            total_detected: 0,
            inference_time_ms: 0,
            image_id: 0,
            width: frameInfo.width ?? 640,
            height: frameInfo.height ?? 480,
            is_fresh: frameInfo.is_fresh
          });
        }
      } finally {
        setIsRefreshingSnapshot(false);
      }
    },
    [activeDroneId]
  );

  const syncWithBackend = useCallback(async () => {
    setIsSyncing(true);
    try {
      const online = await api.checkHealth();
      setIsApiOnline(online);
      setHasCheckedInitialHealth(true);

      if (online) {
        const [detStatus, catConfig, camStatus, dronesList] = await Promise.all([
          api.getDetectionStatus(),
          api.getRoadCategories(),
          api.getCameraStatus(),
          api.getDrones().catch(() => [] as Drone[])
        ]);

        setDetectionStatus(detStatus);
        if (catConfig) setCategoriesConfig(catConfig);
        if (camStatus) setCameraStatus(camStatus);

        let targetId = 'drone-webots-01';
        if (dronesList.length > 0) {
          setRegisteredDrone(dronesList[0]);
          targetId = dronesList[0].id;
        } else if (camStatus?.connected_drones && camStatus.connected_drones.length > 0) {
          targetId = camStatus.connected_drones[0];
        }

        const latestTel = await api.getLatestTelemetry(targetId);
        if (latestTel) {
          setRestTelemetry(latestTel);
        }
      }
    } finally {
      setIsSyncing(false);
    }
  }, []);

  // Periodic health & vision status check
  useEffect(() => {
    const initTimer = window.setTimeout(() => {
      syncWithBackend();
    }, 0);
    const interval = setInterval(syncWithBackend, 5000);
    return () => {
      clearTimeout(initTimer);
      clearInterval(interval);
    };
  }, [syncWithBackend]);

  const handleManualRecovery = async () => {
    reconnectNow();
    await syncWithBackend();
  };

  // Determine which detections to show in DetectionViewer:
  // Prioritize live Webots stream if present; otherwise if an external image was analyzed, show its detections
  const hasStreamFrame = Boolean(activeStream?.frame_base64);
  const viewerDetections = hasStreamFrame
    ? activeStream?.detections || []
    : lastImageAnalysis?.detections || [];
  const hasActiveInspectionFrame = hasStreamFrame || Boolean(lastImageAnalysis);
  const viewerSourceLabel = hasStreamFrame
    ? `Stream (${activeStream?.drone_id || activeDroneId})`
    : lastImageAnalysis
    ? `Imagen: ${lastImageAnalysis.original_filename}`
    : 'En espera';

  return (
    <div className="app-container">
      {/* Top Navigation & Status Bar */}
      <Header
        isWsConnected={isWsConnected}
        wsState={wsState}
        reconnectAttempts={reconnectAttempts}
        isApiOnline={isApiOnline}
        droneStatus={activeTelemetry?.flight_mode || registeredDrone?.status || 'standby'}
        droneName={activeDroneName}
        hasTelemetry={activeTelemetry !== null}
        detectionStatus={detectionStatus}
        onManualSync={handleManualRecovery}
        isSyncing={isSyncing}
      />

      {/* Connection Loss & Recovery Banner (Task 7) */}
      {hasCheckedInitialHealth && (!isApiOnline || !isWsConnected) && (
        <div
          className={`connection-recovery-banner ${
            !isApiOnline ? 'recovery-banner-critical' : 'recovery-banner-warning'
          }`}
        >
          <div className="recovery-banner-left">
            {!isApiOnline ? (
              <WifiOff size={18} className="text-red flex-shrink-0" />
            ) : (
              <AlertTriangle size={18} className="text-amber flex-shrink-0" />
            )}
            <div>
              <strong>
                {!isApiOnline
                  ? 'Sin conexión con el servidor Backend (FastAPI)'
                  : 'Canal WebSocket en reconexión automática'}
              </strong>
              <p className="recovery-banner-sub">
                {!isApiOnline
                  ? `No se pudo contactar a ${HEALTH_URL}/health. Verifique que el backend esté ejecutándose. El dashboard reintentará automáticamente cada 5 segundos.`
                  : `El servidor REST está en línea, pero el flujo WebSocket se interrumpió (intento #${reconnectAttempts}). Reconectando automáticamente...`}
              </p>
            </div>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleManualRecovery}
            disabled={isSyncing}
          >
            <RefreshCw size={14} className={isSyncing ? 'spin-icon' : ''} />
            <span>{isSyncing ? 'Reconectando...' : 'Reconectar Ahora'}</span>
          </button>
        </div>
      )}

      {/* Main Mission Control Grid */}
      <main className="dashboard-grid">
        {/* Left Column: Vision & Detection */}
        <section className="dashboard-column vision-column">
          <LiveCameraFeed
            streamData={activeStream}
            cameraStatus={cameraStatus}
            droneId={activeDroneId}
            isApiOnline={isApiOnline}
            onRefreshSnapshot={() => handleRefreshSnapshot(activeDroneId)}
            isRefreshingSnapshot={isRefreshingSnapshot}
          />
          <DetectionViewer
            detections={viewerDetections}
            detectionStatus={detectionStatus}
            categoriesConfig={categoriesConfig}
            hasActiveFrame={hasActiveInspectionFrame}
            sourceLabel={viewerSourceLabel}
            isApiOnline={isApiOnline}
          />
        </section>

        {/* Right Column: Flight Telemetry & Drone Controls */}
        <section className="dashboard-column flight-column">
          <DroneStatusCard
            telemetry={activeTelemetry}
            droneId={activeDroneId}
            isApiOnline={isApiOnline}
          />
          <TelemetryPanel telemetry={activeTelemetry} />
        </section>
      </main>

      {/* Semana 7 & 9: Carga y Análisis de Imágenes Externas JPG/PNG */}
      <ImageAnalysisSection
        detectionStatus={detectionStatus}
        isApiOnline={isApiOnline}
        onAnalysisComplete={(res) => setLastImageAnalysis(res)}
        onIncidentCreated={(inc) => setNewlyCreatedIncident(inc)}
      />

      {/* Bottom Section: Historical & Live Incidents Log (SQLite - Semana 8 & 9) */}
      <section className="dashboard-incidents-section">
        <IncidentLog
          latestWsIncident={wsIncident}
          latestUpdatedIncident={wsUpdatedIncident}
          latestDeletedIncident={wsDeletedIncident}
          newlyCreatedIncident={newlyCreatedIncident}
          isApiOnline={isApiOnline}
        />
      </section>

      {/* System Footer */}
      <footer className="dashboard-footer">
        <div className="footer-left">
          <span>
            Arquitectura: Webots R2022b ↔ FastAPI REST/WebSocket ↔ OpenCV / YOLO Adapter ↔ SQLite ↔ React + TypeScript + Vite
          </span>
        </div>
        <div className="footer-right">
          <span>Semana 9: Dashboard Funcional e Integración en Tiempo Real con Backend y SQLite</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
