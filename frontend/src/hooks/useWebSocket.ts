import { useState, useEffect, useRef, useCallback } from 'react';
import type { TelemetryData, CameraFrameStream, Incidente } from '../types';

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:8000/ws';

const MIN_RECONNECT_MS = 1500;
const MAX_RECONNECT_MS = 20000;

type WebSocketWithPing = WebSocket & {
  _pingInterval?: ReturnType<typeof setInterval>;
};

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
  const connectRef = useRef<() => void>(() => {});

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;

    clearReconnectTimer();

    const delay = reconnectDelayRef.current;
    reconnectDelayRef.current = Math.min(delay * 1.5, MAX_RECONNECT_MS);

    reconnectTimeoutRef.current = window.setTimeout(() => {
      reconnectTimeoutRef.current = null;
      connectRef.current();
    }, delay);
  }, [clearReconnectTimer]);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    if (
      wsRef.current &&
      wsRef.current.readyState !== WebSocket.CLOSED
    ) {
      const previousSocket = wsRef.current as WebSocketWithPing;

      previousSocket.onclose = null;

      if (previousSocket._pingInterval !== undefined) {
        clearInterval(previousSocket._pingInterval);
        previousSocket._pingInterval = undefined;
      }

      previousSocket.close();
    }

    try {
      const socket = new WebSocket(url);
      wsRef.current = socket;

      socket.onopen = () => {
        if (!mountedRef.current || wsRef.current !== socket) return;

        setIsConnected(true);
        reconnectDelayRef.current = MIN_RECONNECT_MS;

        console.info(
          '[WebSocket] Conectado al servidor de telemetría y visión.',
          url
        );

        const pingInterval = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
          } else {
            clearInterval(pingInterval);
          }
        }, 20000);

        (socket as WebSocketWithPing)._pingInterval = pingInterval;
      };

      socket.onmessage = (event) => {
        if (!mountedRef.current || wsRef.current !== socket) return;

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
          console.warn(
            '[WebSocket] Error parseando mensaje entrante:',
            err
          );
        }
      };

      socket.onclose = (ev) => {
        if (!mountedRef.current || wsRef.current !== socket) return;

        setIsConnected(false);

        const socketWithPing = socket as WebSocketWithPing;

        if (socketWithPing._pingInterval !== undefined) {
          clearInterval(socketWithPing._pingInterval);
          socketWithPing._pingInterval = undefined;
        }

        console.warn(
          `[WebSocket] Conexión cerrada (code ${ev.code}). Se programará una reconexión.`
        );

        scheduleReconnect();
      };

      socket.onerror = () => {
        if (wsRef.current !== socket) return;

        console.error(
          '[WebSocket] Error de socket. Cerrando para reconectar...'
        );

        socket.close();
      };
    } catch (err) {
      console.error(
        '[WebSocket] Fallo al inicializar conexión:',
        err
      );

      setIsConnected(false);
      scheduleReconnect();
    }
  }, [url, scheduleReconnect]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      clearReconnectTimer();

      if (wsRef.current) {
        const socket = wsRef.current as WebSocketWithPing;

        socket.onclose = null;
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;

        if (socket._pingInterval !== undefined) {
          clearInterval(socket._pingInterval);
          socket._pingInterval = undefined;
        }

        socket.close();
        wsRef.current = null;
      }
    };
  }, [connect, clearReconnectTimer]);

  const sendMessage = useCallback((msg: Record<string, unknown>) => {
    if (
      wsRef.current &&
      wsRef.current.readyState === WebSocket.OPEN
    ) {
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