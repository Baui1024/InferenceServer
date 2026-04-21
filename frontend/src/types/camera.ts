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
  // Automation zones
  zones?: ZoneConfig[];
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
  playback?: PlaybackInfo;
  zone_states?: ZoneStateInfo[];
}

export interface PlaybackInfo {
  current_frame: number;
  total_frames: number;
  duration_sec: number;
  native_fps: number;
  paused: boolean;
  start_frame: number;
  end_frame: number;
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

// -- Automation / Zones --

export interface TriggerConfig {
  id: string;
  type: 'knx' | 'webhook';
  // KNX
  group_address?: string;
  dpt?: 'boolean' | '1byte';
  on_value?: number;
  off_value?: number;
  // Webhook
  url?: string;      // legacy — use on_url/off_url instead
  on_url?: string;
  off_url?: string;
}

export interface ZoneConfig {
  id: string;
  name: string;
  points: [number, number][];  // normalized 0-1 [x, y] pairs
  mode: 'intersect' | 'included';
  attack_frames: number;
  hold_time_s: number;
  triggers: TriggerConfig[];
  enabled: boolean;
}

export interface ZoneStateInfo {
  zone_id: string;
  active: boolean;
  transition: 'on' | 'off' | null;
}

export interface AutomationSettings {
  knx_gateway_ip: string;
  knx_gateway_port: number;
  knx_connection_type: 'tunneling' | 'routing';
  knx_enabled: boolean;
  knx?: {
    status: string;
    error: string | null;
    available: boolean;
  };
}
