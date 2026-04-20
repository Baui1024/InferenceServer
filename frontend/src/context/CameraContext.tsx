import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';
import type { WSState } from '../hooks/useWebSocket';
import type { Camera, CameraStats, CameraHWSettings, Recording, ServerConfig, TRTEngine, EngineCompileProgress } from '../types/camera';

interface CameraContextValue {
  cameras: Camera[];
  selectedId: string | null;
  selectCamera: (id: string | null) => void;
  wsState: WSState;
  send: (type: string, data?: unknown) => void;
  hwSettings: Record<string, CameraHWSettings>;
  recordings: Recording[];
  serverConfig: ServerConfig;
  engines: TRTEngine[];
  compileProgress: EngineCompileProgress | null;
}

const CameraContext = createContext<CameraContextValue>(null!);

export const useCameras = () => useContext(CameraContext);

export function CameraProvider({ children }: { children: React.ReactNode }) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hwSettings, setHwSettings] = useState<Record<string, CameraHWSettings>>({});
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [serverConfig, setServerConfig] = useState<ServerConfig>({ recording_enabled: false, gpu: { name: null, capability: null }, compilable_models: [] });
  const [engines, setEngines] = useState<TRTEngine[]>([]);
  const [compileProgress, setCompileProgress] = useState<EngineCompileProgress | null>(null);

  // Use ref to avoid stale closures in the WS callback
  const camerasRef = useRef(cameras);
  camerasRef.current = cameras;
  const sendRef = useRef<(type: string, data?: unknown) => void>(() => {});

  const onMessage = useCallback((msg: { type: string; data: unknown }) => {
    switch (msg.type) {
      case 'server_config':
        setServerConfig(msg.data as ServerConfig);
        break;

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

      case 'recordings':
        setRecordings(msg.data as Recording[]);
        break;

      case 'engines':
        setEngines(msg.data as TRTEngine[]);
        break;

      case 'engine_compile_progress':
        setCompileProgress(msg.data as EngineCompileProgress);
        break;

      case 'engine_compiled':
        setCompileProgress(null);
        break;

      case 'engine_compile_error':
        setCompileProgress(null);
        console.error('Engine compile error:', msg.data);
        break;

      case 'recording_started':
      case 'recording_stopped':
        // Refresh recordings list
        sendRef.current('list_recordings');
        break;

      case 'playback_started': {
        const { camera_id } = msg.data as { camera_id: string };
        // The camera was added to the store, so list_cameras will include it.
        // Just select it — the cameras list update comes via the 'cameras' broadcast.
        setSelectedId(camera_id);
        break;
      }

      case 'error':
        console.error('Server error:', (msg.data as { message: string }).message);
        break;
    }
  }, []);

  const { state: wsState, send } = useWebSocket(onMessage);
  sendRef.current = send;

  return (
    <CameraContext.Provider value={{
      cameras, selectedId, selectCamera: setSelectedId,
      wsState, send, hwSettings, recordings, serverConfig,
      engines, compileProgress,
    }}>
      {children}
    </CameraContext.Provider>
  );
}
