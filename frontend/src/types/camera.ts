export interface Camera {
  id: string;
  name: string;
  type: 'esp32' | 'rpi';
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
  openvino_model: string;
  openvino_device: string;
  openvino_confidence: number;
  // Pipeline
  max_fps: number;
  motion_detection_enabled: boolean;
  motion_threshold: number;
  motion_min_area_percent: number;
  // Camera HW (RPi only)
  camera_ws_port: number;
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
}

export interface CameraHWSettings {
  ir_mode?: string;
  clahe_enabled?: boolean;
  ae_enable?: boolean;
  exposure_time?: number;
  analogue_gain?: number;
  jpeg_quality?: number;
}

export interface WSMessage {
  type: string;
  data: unknown;
}
