export interface Camera {
  id: string;
  name: string;
  type: 'rpi' | 'recording';
  host: string;
  port: number;
  enabled: boolean;
  // RPi connection
  use_tls: boolean;
  ca_cert: string | null;
  client_cert: string | null;
  client_key: string | null;
  // Detection
  detector_backend: 'yolo' | 'openvino';
  yolo_model: string;
  yolo_confidence: number;
  yolo_person_only: boolean;
  show_below_confidence: boolean;
  openvino_model: string;
  openvino_device: string;
  openvino_confidence: number;
  // Pipeline
  max_fps: number;
  motion_detection_enabled: boolean;
  motion_threshold: number;
  motion_min_area_percent: number;
  show_motion_debug: boolean;
  // Camera HW (RPi only)
  camera_ws_port: number;
  // Recording playback
  recording_id?: string;
  // Runtime (attached by server)
  stats?: CameraStats;
}

export interface CameraStats {
  id: string;
  status: 'starting' | 'running' | 'stopped' | 'error';
  fps: number;
  inference_ms: number;
  detection_count: number;
  frame_count: number;
  recording?: boolean;
  motion_pct?: number;
}

export interface CameraHWSettings {
  jpeg_quality?: number;
  // ISP parameters (VEYE I2C)
  daynightmode?: string;
  mshutter?: string;
  agc?: string;
  denoise?: string;
  brightness?: string;
  contrast?: string;
  saturation?: string;
  sharppen?: string;
  wdrmode?: string;
  lowlight?: string;
  wbmode?: string;
  // Extended ISP params
  videoformat?: string;
  mirrormode?: string;
  ircutdir?: string;
  irtrigger?: string;
  cameramode?: string;
  nodf?: string;
  wdrtargetbr?: string;
  wdrbtargetbr?: string;
  aespeed_agc?: string;
  aespeed_shutter?: string;
  mwbgain_rgain?: string;
  mwbgain_bgain?: string;
  // Read-only
  awbgain_rgain?: string;
  awbgain_bgain?: string;
}

export interface Recording {
  id: string;
  camera_id: string;
  camera_name: string;
  filename: string;
  start_time: string;
  duration_s: number;
  frame_count: number;
  fps: number;
  resolution: [number, number] | null;
  size_mb?: number;
}

export interface ServerConfig {
  recording_enabled: boolean;
  gpu: {
    name: string | null;
    capability: string | null;
  };
  compilable_models: string[];
}

export interface TRTEngine {
  filename: string;
  source_model: string;
  size_mb: number;
}

export interface EngineCompileProgress {
  model: string;
  status: string;
  percent: number;
}

export interface WSMessage {
  type: string;
  data: unknown;
}
