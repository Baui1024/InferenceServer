import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import type { WSState } from '../hooks/useWebSocket';
import type { Camera, CameraStats, CameraHWSettings } from '../types/camera';

interface CameraContextValue {
  cameras: Camera[];
  selectedId: string | null;
  selectCamera: (id: string | null) => void;
  wsState: WSState;
  send: (type: string, data?: unknown) => void;
  hwSettings: Record<string, CameraHWSettings>;
}

const CameraContext = createContext<CameraContextValue>(null!);

export const useCameras = () => useContext(CameraContext);

export function CameraProvider({ children }: { children: React.ReactNode }) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hwSettings, setHwSettings] = useState<Record<string, CameraHWSettings>>({});

  // Use ref to avoid stale closures in the WS callback
  const camerasRef = useRef(cameras);
  camerasRef.current = cameras;

  const onMessage = useCallback((msg: { type: string; data: unknown }) => {
    switch (msg.type) {
      case 'cameras':
        setCameras(msg.data as Camera[]);
        break;

      case 'camera': {
        const cam = msg.data as Camera;
        setCameras(prev => prev.map(c => c.id === cam.id ? cam : c));
        break;
      }

      case 'camera_removed': {
        const { id } = msg.data as { id: string };
        setCameras(prev => prev.filter(c => c.id !== id));
        setSelectedId(prev => prev === id ? null : prev);
        break;
      }

      case 'camera_stats': {
        const statsList = msg.data as CameraStats[];
        const statsMap: Record<string, CameraStats> = {};
        for (const s of statsList) statsMap[s.id] = s;
        setCameras(prev =>
          prev.map(c => ({
            ...c,
            stats: statsMap[c.id] ?? c.stats,
          }))
        );
        break;
      }

      case 'camera_hw_settings': {
        const { id, settings } = msg.data as { id: string; settings: CameraHWSettings };
        setHwSettings(prev => ({ ...prev, [id]: settings }));
        break;
      }

      case 'error':
        console.error('Server error:', (msg.data as { message: string }).message);
        break;
    }
  }, []);

  const { state: wsState, send } = useWebSocket(onMessage);

  return (
    <CameraContext.Provider value={{ cameras, selectedId, selectCamera: setSelectedId, wsState, send, hwSettings }}>
      {children}
    </CameraContext.Provider>
  );
}
