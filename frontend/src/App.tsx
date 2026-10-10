import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { DroneStatusCard } from './components/DroneStatusCard';
import { LiveCameraFeed } from './components/LiveCameraFeed';
import { TelemetryPanel } from './components/TelemetryPanel';
import { DetectionViewer } from './components/DetectionViewer';
import { IncidentLog } from './components/IncidentLog';
import { useWebSocket } from './hooks/useWebSocket';
import { api } from './services/api';
import './App.css';

export function App() {
  const { isConnected: isWsConnected, latestTelemetry, latestStream, latestIncident } = useWebSocket();
  const [isApiOnline, setIsApiOnline] = useState(false);
  const [droneId, setDroneId] = useState('drone-webots-01');

  // Periodic health check
  useEffect(() => {
    const checkStatus = async () => {
      const online = await api.checkHealth();
      setIsApiOnline(online);
    };
    checkStatus();
    const interval = setInterval(checkStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Update drone id from incoming telemetry if present
  useEffect(() => {
    if (latestTelemetry?.drone_id) {
      setDroneId(latestTelemetry.drone_id);
    }
  }, [latestTelemetry]);

  return (
    <div className="app-container">
      {/* Top Navigation & Status Bar */}
      <Header
        isWsConnected={isWsConnected}
        isApiOnline={isApiOnline}
        droneStatus={latestTelemetry?.flight_mode || 'idle'}
        droneName="DJI Mavic 2 Pro (Webots Sim)"
      />

      {/* Main Mission Control Grid */}
      <main className="dashboard-grid">
        {/* Left Column: Vision & Detection */}
        <section className="dashboard-column vision-column">
          <LiveCameraFeed streamData={latestStream} droneId={droneId} />
          <DetectionViewer detections={latestStream?.detections || []} />
        </section>

        {/* Right Column: Flight Telemetry & Drone Controls */}
        <section className="dashboard-column flight-column">
          <DroneStatusCard telemetry={latestTelemetry} droneId={droneId} />
          <TelemetryPanel telemetry={latestTelemetry} />
        </section>
      </main>

      {/* Bottom Section: Historical & Live Incidents Log (SQLite) */}
      <section className="dashboard-incidents-section">
        <IncidentLog latestWsIncident={latestIncident} />
      </section>

      {/* System Footer */}
      <footer className="dashboard-footer">
        <div className="footer-left">
          <span>Arquitectura: Webots R2022b ↔ FastAPI REST/WebSocket ↔ OpenCV / YOLO Adapter ↔ React + Vite</span>
        </div>
        <div className="footer-right">
          <span>Entrega 1: Base de Arquitectura Modular & Comunicación en Tiempo Real</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
