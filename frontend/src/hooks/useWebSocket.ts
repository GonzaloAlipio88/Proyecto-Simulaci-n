import { useState, useEffect, useRef, useCallback } from 'react';
import type { TelemetryData, CameraFrameStream, Incidente } from '../types';

export function useWebSocket(url: string = 'ws://127.0.0.1:8000/ws') {
  const [isConnected, setIsConnected] = useState(false);
  const [latestTelemetry, setLatestTelemetry] = useState<TelemetryData | null>(null);
  const [latestStream, setLatestStream] = useState<CameraFrameStream | null>(null);
  const [latestIncident, setLatestIncident] = useState<Incidente | null>(null);
  const [lastMessageTime, setLastMessageTime] = useState<Date | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    try {
      const socket = new WebSocket(url);
      wsRef.current = socket;

      socket.onopen = () => {
        setIsConnected(true);
        console.log('[WebSocket] Conectado al servidor de telemetría y visión.');
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { type, data } = payload;
          setLastMessageTime(new Date());

          if (type === 'telemetry') {
            setLatestTelemetry(data);
          } else if (type === 'camera_stream') {
            setLatestStream(data);
          } else if (type === 'incident') {
            setLatestIncident(data);
          }
        } catch (err) {
          console.warn('[WebSocket] Error parseando mensaje entrante:', err);
        }
      };

      socket.onclose = () => {
        setIsConnected(false);
        console.log('[WebSocket] Conexión cerrada. Reintentando en 2.5s...');
        reconnectTimeoutRef.current = window.setTimeout(connect, 2500);
      };

      socket.onerror = (err) => {
        console.error('[WebSocket] Error en socket:', err);
        socket.close();
      };
    } catch (err) {
      console.error('[WebSocket] Fallo al inicializar conexión:', err);
      reconnectTimeoutRef.current = window.setTimeout(connect, 2500);
    }
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msg: Record<string, any>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return {
    isConnected,
    latestTelemetry,
    latestStream,
    latestIncident,
    lastMessageTime,
    sendMessage
  };
}
