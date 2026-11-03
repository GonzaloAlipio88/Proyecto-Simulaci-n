import { useState, useEffect, useRef, useCallback } from 'react';
import type { TelemetryData, CameraFrameStream, Incidente } from '../types';

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:8000/ws';

// Exponential backoff parameters (milliseconds)
const MIN_RECONNECT_MS = 1500;
const MAX_RECONNECT_MS = 15000;
const BACKOFF_MULTIPLIER = 1.5;

export type WsConnectionState = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';

export interface UseWebSocketReturn {
  isConnected: boolean;
  wsState: WsConnectionState;
  reconnectAttempts: number;
  nextReconnectDelayMs: number;
  latestTelemetry: TelemetryData | null;
  latestStream: CameraFrameStream | null;
  latestIncident: Incidente | null;
  latestUpdatedIncident: Incidente | null;
  latestDeletedIncident: { id: number; ts: number } | null;
  lastMessageTime: Date | null;
  sendMessage: (msg: Record<string, unknown>) => void;
  reconnectNow: () => void;
}

export function useWebSocket(url: string = WS_URL): UseWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [wsState, setWsState] = useState<WsConnectionState>('connecting');
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  const [nextReconnectDelayMs, setNextReconnectDelayMs] = useState(MIN_RECONNECT_MS);
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
  const isConnectingRef = useRef(false);
  const connectFnRef = useRef<() => void>(() => {});

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const cleanupSocket = useCallback((socket: WebSocket | null) => {
    if (!socket) return;
    try {
      const s = socket as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> };
      if (s._pingInterval) {
        clearInterval(s._pingInterval);
        s._pingInterval = undefined;
      }
      // Detach handlers before closing to prevent duplicate events or race conditions
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        socket.close();
      }
    } catch {
      // Safe ignore during teardown
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    clearReconnectTimer();

    // Prevent duplicate overlapping connection attempts
    if (wsRef.current) {
      cleanupSocket(wsRef.current);
      wsRef.current = null;
    }

    try {
      isConnectingRef.current = true;
      setWsState((prev) => (prev === 'connected' ? 'reconnecting' : prev));

      const socket = new WebSocket(url);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!mountedRef.current) {
          cleanupSocket(socket);
          return;
        }
        isConnectingRef.current = false;
        setIsConnected(true);
        setWsState('connected');
        setReconnectAttempts(0);
        reconnectDelayRef.current = MIN_RECONNECT_MS;
        setNextReconnectDelayMs(MIN_RECONNECT_MS);
        console.info('[WebSocket] Conectado exitosamente al canal en tiempo real:', url);

        // Send subscription request to ensure event routing
        try {
          socket.send(JSON.stringify({
            type: 'subscribe',
            client: 'dashboard_react',
            timestamp: new Date().toISOString()
          }));
        } catch {
          // ignore
        }

        // Heartbeat ping every 15 seconds to keep connection alive
        const pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
          } else {
            clearInterval(pingInterval);
          }
        }, 15000);
        (socket as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> })._pingInterval = pingInterval;
      };

      socket.onmessage = (event) => {
        if (!mountedRef.current) return;
        try {
          const payload = JSON.parse(event.data);
          const { type, data } = payload;
          setLastMessageTime(new Date());

          if (type === 'pong' || type === 'connection_ack' || type === 'message_ack' || type === 'subscription_ack') {
            return;
          }
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
        isConnectingRef.current = false;
        setIsConnected(false);
        setWsState('reconnecting');
        setReconnectAttempts((prev) => prev + 1);

        const s = socket as WebSocket & { _pingInterval?: ReturnType<typeof setInterval> };
        if (s._pingInterval) clearInterval(s._pingInterval);

        // Exponential backoff with small random jitter (50-200ms) to avoid thundering herd
        const baseDelay = reconnectDelayRef.current;
        const jitter = Math.floor(Math.random() * 150) + 50;
        const currentDelayWithJitter = Math.min(baseDelay + jitter, MAX_RECONNECT_MS);

        console.warn(`[WebSocket] Conexión cerrada (code ${ev.code}). Reintentando en ${currentDelayWithJitter}ms...`);

        // Compute next delay for upcoming cycle
        const nextDelay = Math.min(Math.round(baseDelay * BACKOFF_MULTIPLIER), MAX_RECONNECT_MS);
        reconnectDelayRef.current = nextDelay;
        setNextReconnectDelayMs(nextDelay);

        reconnectTimeoutRef.current = window.setTimeout(() => {
          if (mountedRef.current) {
            connectFnRef.current();
          }
        }, currentDelayWithJitter);
      };

      socket.onerror = () => {
        // Just log; onclose will handle the reconnection
        console.warn('[WebSocket] Evento de error en socket. Iniciando reconexión...');
      };
    } catch (err) {
      console.error('[WebSocket] Error al instanciar socket:', err);
      isConnectingRef.current = false;
      setIsConnected(false);
      setWsState('reconnecting');
      setReconnectAttempts((prev) => prev + 1);

      const delay = reconnectDelayRef.current;
      const nextDelay = Math.min(Math.round(delay * BACKOFF_MULTIPLIER), MAX_RECONNECT_MS);
      reconnectDelayRef.current = nextDelay;
      setNextReconnectDelayMs(nextDelay);

      reconnectTimeoutRef.current = window.setTimeout(() => {
        if (mountedRef.current) {
          connectFnRef.current();
        }
      }, delay);
    }
  }, [url, clearReconnectTimer, cleanupSocket]);

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
      window.clearTimeout(initTimer);
      clearReconnectTimer();
      cleanupSocket(wsRef.current);
      wsRef.current = null;
    };
  }, [connect, clearReconnectTimer, cleanupSocket]);

  const reconnectNow = useCallback(() => {
    console.info('[WebSocket] Reconexión manual solicitada por el usuario.');
    clearReconnectTimer();
    reconnectDelayRef.current = MIN_RECONNECT_MS;
    setNextReconnectDelayMs(MIN_RECONNECT_MS);
    connect();
  }, [connect, clearReconnectTimer]);

  const sendMessage = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    } else {
      console.warn('[WebSocket] Intento de envío en socket no abierto:', msg);
    }
  }, []);

  return {
    isConnected,
    wsState,
    reconnectAttempts,
    nextReconnectDelayMs,
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
