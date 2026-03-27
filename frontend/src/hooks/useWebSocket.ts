import { useEffect, useRef, useCallback, useState } from 'react';

type MessageHandler = (msg: { type: string; data: unknown }) => void;

export type WSState = 'connected' | 'disconnected' | 'reconnecting';

export function useWebSocket(onMessage: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null);
  const [state, setState] = useState<WSState>('disconnected');
  const delayRef = useRef(1000);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${window.location.host}/ws`;

    setState('reconnecting');
    const ws = new WebSocket(url);

    ws.onopen = () => {
      setState('connected');
      delayRef.current = 1000;
      ws.send(JSON.stringify({ type: 'list_cameras' }));
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        onMessage(msg);
      } catch { /* ignore */ }
    };

    ws.onclose = () => {
      setState('disconnected');
      if (mountedRef.current) {
        setTimeout(() => {
          delayRef.current = Math.min(delayRef.current * 2, 16000);
          connect();
        }, delayRef.current);
      }
    };

    ws.onerror = () => { /* onclose will fire */ };

    wsRef.current = ws;
  }, [onMessage]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((type: string, data?: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type, data: data ?? {} }));
    }
  }, []);

  return { state, send };
}
