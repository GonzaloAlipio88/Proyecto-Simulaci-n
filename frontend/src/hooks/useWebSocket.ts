import { useState, useEffect, useRef, useCallback } from 'react';
import type { TelemetryData, CameraFrameStream, Incidente } from '../types';

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:8000/ws';

// Exponential backoff limits (ms)
const MIN_RECONNECT_MS = 1500;
const MAX_RECONNECT_MS = 20000;

export function useWebSocket(url: string = WS_URL) {
  const [isConnected, setIsConnected] = useState(false);
  const [latestTelemetry, setLatestTelemetry] = useState<TelemetryData | null>(null);
  const [latestStream, setLatestStream] = useState<CameraFrameStream | null>(null);
  const [latestIncident, setLatestIncident] = useState<Incidente | null>(null);
  const [lastMessageTime, setLastMessageTime] = useState<Date | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectDelayRef = useRef<number>(MIN_RECONNECT_MS);
  const mountedRef = useRef(true);

  const clearReconnectTimer = () => {
    if (reconnectTimeoutRef.current !== null) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  };

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.onclose = null;
      wsRef.current.close();
    }

    try {
      const socket = new WebSocket(url);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        reconnectDelayRef.current = MIN_RECONNECT_MS;
        console.info('[WebSocket] Conectado al servidor de telemetría y visión.', url);
        const pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
          } else {
            clearInterval(pingInterval);
          }
        }, 20000);
        (socket as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> })._pingInterval = pingInterval;
      };

      socket.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const payload = JSON.parse(event.data);
          const { type, data } = payload;
          if (type === 'pong' || type === 'connection_ack') return;
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

      socket.onclose = (ev) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        const s = socket as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> };
        if (s._pingInterval) clearInterval(s._pingInterval);
        const delay = reconnectDelayRef.current;
        console.warn(`[WebSocket] Conexión cerrada (code ${ev.code}). Reintentando en ${delay}ms...`);
        reconnectDelayRef.current = Math.min(delay * 1.5, MAX_RECONNECT_MS);
        reconnectTimeoutRef.current = window.setTimeout(connect, delay);
      };

      socket.onerror = () => {
        console.error('[WebSocket] Error de socket. Cerrando para reconectar...');
        socket.close();
      };
    } catch (err) {
      console.error('[WebSocket] Fallo al inicializar conexión:', err);
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(delay * 1.5, MAX_RECONNECT_MS);
      reconnectTimeoutRef.current = window.setTimeout(connect, delay);
    }
  }, [url]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      clearReconnectTimer();
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((msg: Record<string, unknown>) => {
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
    sendMessage,
  };
}

