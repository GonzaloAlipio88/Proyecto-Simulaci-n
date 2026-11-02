import { useState, useEffect, useRef, useCallback } from 'react';
import type { TelemetryData, CameraFrameStream, Incidente } from '../types';

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:8000/ws';

// Exponential backoff limits (ms)
const MIN_RECONNECT_MS = 1500;
const MAX_RECONNECT_MS = 15000;

export type WsConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export function useWebSocket(url: string = WS_URL) {
  const [isConnected, setIsConnected] = useState(false);
  const [wsState, setWsState] = useState<WsConnectionState>('connecting');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [latestTelemetry, setLatestTelemetry] = useState<TelemetryData | null>(null);
  const [latestStream, setLatestStream] = useState<CameraFrameStream | null>(null);
  const [latestIncident, setLatestIncident] = useState<Incidente | null>(null);
  const [latestUpdatedIncident, setLatestUpdatedIncident] = useState<Incidente | null>(null);
  const [latestDeletedIncident, setLatestDeletedIncident] = useState<{ id: number; ts: number } | null>(null);
  const [lastMessageTime, setLastMessageTime] = useState<Date | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectDelayRef = useRef<number>(MIN_RECONNECT_MS);
  const mountedRef = useRef(true);
  const connectFnRef = useRef<() => void>(() => {});

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    clearReconnectTimer();

    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.onclose = null;
      wsRef.current.close();
    }

    try {
      setWsState((prev) => (prev === 'reconnecting' ? 'reconnecting' : 'connecting'));
      const socket = new WebSocket(url);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!mountedRef.current) return;
        setIsConnected(true);
        setWsState('connected');
        setReconnectAttempts(0);
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
          if (type === 'pong' || type === 'connection_ack' || type === 'message_ack') {
            setLastMessageTime(new Date());
            return;
          }
          setLastMessageTime(new Date());
          if (type === 'telemetry' && data) {
            setLatestTelemetry(data as TelemetryData);
          } else if (type === 'camera_stream' && data) {
            setLatestStream(data as CameraFrameStream);
          } else if (type === 'incident' && data) {
            setLatestIncident(data as Incidente);
          } else if (type === 'incident_updated' && data) {
            setLatestUpdatedIncident(data as Incidente);
            setLatestIncident(data as Incidente);
          } else if (type === 'incident_deleted' && data && typeof data.id === 'number') {
            setLatestDeletedIncident({ id: data.id, ts: Date.now() });
          }
        } catch (err) {
          console.warn('[WebSocket] Error parseando mensaje entrante:', err);
        }
      };

      socket.onclose = (ev) => {
        if (!mountedRef.current) return;
        setIsConnected(false);
        setWsState('reconnecting');
        setReconnectAttempts((prev) => prev + 1);
        const s = socket as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> };
        if (s._pingInterval) clearInterval(s._pingInterval);

        const delay = reconnectDelayRef.current;
        console.warn(`[WebSocket] Conexión cerrada (code ${ev.code}). Reintentando en ${delay}ms...`);
        reconnectDelayRef.current = Math.min(Math.round(delay * 1.5), MAX_RECONNECT_MS);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connectFnRef.current();
        }, delay);
      };

      socket.onerror = () => {
        console.error('[WebSocket] Error de socket. Cerrando para reconectar...');
        socket.close();
      };
    } catch (err) {
      console.error('[WebSocket] Fallo al inicializar conexión:', err);
      setIsConnected(false);
      setWsState('reconnecting');
      setReconnectAttempts((prev) => prev + 1);
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(Math.round(delay * 1.5), MAX_RECONNECT_MS);
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connectFnRef.current();
      }, delay);
    }
  }, [url, clearReconnectTimer]);

  useEffect(() => {
    connectFnRef.current = connect;
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    const initTimer = window.setTimeout(() => {
      connect();
    }, 0);
    return () => {
      mountedRef.current = false;
      clearTimeout(initTimer);
      clearReconnectTimer();
      if (wsRef.current) {
        const s = wsRef.current as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> };
        if (s._pingInterval) clearInterval(s._pingInterval);
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [connect, clearReconnectTimer]);

  const reconnectNow = useCallback(() => {
    reconnectDelayRef.current = MIN_RECONNECT_MS;
    connect();
  }, [connect]);

  const sendMessage = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return {
    isConnected,
    wsState,
    reconnectAttempts,
    latestTelemetry,
    latestStream,
    latestIncident,
    latestUpdatedIncident,
    latestDeletedIncident,
    lastMessageTime,
    sendMessage,
    reconnectNow,
  };
}
