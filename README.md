# InferenceServer

Multi-camera AI object detection server with a React web UI. Receives JPEG
streams from Raspberry Pi cameras running [PiCamStream](https://github.com/Baui1024/PiCamStream),
runs real-time YOLO or OpenVINO inference, and serves annotated video via MJPEG.

Features:
- **Multi-camera** — manage multiple RPi cameras from a single dashboard
- **YOLO + TensorRT** — YOLOv8, v11, v26 with optional TensorRT engine compilation for NVIDIA GPUs
- **OpenVINO** — Intel CPU/GPU person detection as an alternative backend
- **Motion detection** — skip inference on static scenes to save GPU cycles
- **Zone automation** — define detection zones with KNX or webhook triggers
- **Recording** — record raw video with frame-accurate playback controls
- **TLS** — encrypted camera streams and settings channels
- **KNX integration** — trigger KNX group addresses on zone activity

## Requirements

- Python 3.12+
- NVIDIA GPU with CUDA (recommended) or Intel CPU/iGPU for OpenVINO
- [uv](https://docs.astral.sh/uv/) package manager (recommended) or pip
- Node.js 18+ (for frontend development only)

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/Baui1024/InferenceServer.git
cd InferenceServer
uv sync
```

### 2. Add a YOLO model

Place model weights in the project root (e.g. `yolo11m.pt`). Supported models:

| Family | Models |
|--------|--------|
| YOLO v11 | `yolo11m.pt`, `yolo11l.pt`, `yolo11x.pt` |
| YOLO v26 | `yolo26m.pt`, `yolo26l.pt`, `yolo26x.pt` |

TensorRT engines can be compiled from the web UI for faster inference on NVIDIA GPUs.

### 3. Run the server

```bash
uv run main.py
```

The web UI is available at **http://localhost:8090**.

### 3b. Install as a systemd service (optional)

To run the server on boot as a system service:

```bash
sudo ./install.sh
```

This will:
- Create a Python virtual environment and install dependencies (if needed)
- Build the React frontend
- Install and enable an `inference-server` systemd service

Useful commands after installation:

```bash
journalctl -u inference-server -f        # follow logs
sudo systemctl restart inference-server   # restart
sudo systemctl stop inference-server      # stop
sudo systemctl disable inference-server   # disable on boot
```

### 4. Set up a camera

On a Raspberry Pi, install [PiCamStream](https://github.com/Baui1024/PiCamStream):

```bash
git clone https://github.com/Baui1024/PiCamStream.git
cd PiCamStream
chmod +x install.sh
./install.sh
```

This installs camera drivers, dependencies, and a systemd service. The Pi
starts streaming automatically on boot.

### 5. Add the camera in the web UI

1. Open **http://localhost:8090**
2. Click **Add Camera**
3. Enter a name and the Pi's IP address
4. Set the stream port (default **8081**) and settings port (default **8082**)
5. Choose a detection backend (YOLO or OpenVINO) and model
6. If TLS is enabled on the Pi, check **Use TLS**
7. Click **Add** — the live stream appears in the camera grid

## Architecture

```
[RPi + PiCamStream]                    [InferenceServer]
  Camera → JPEG frames                   RPiTLSReceiver
       ──TCP/TLS:8081──────────────────►  │
                                          ▼
  Settings WebSocket                    CameraPipeline
       ◄──ws(s):8082──────────────────►   ├─ MotionDetector (skip static)
                                          ├─ Detector (YOLO/OpenVINO)
                                          ├─ ZoneEvaluator → Triggers
                                          └─ VideoRecorder
                                          │
                                          ▼
                                        WebStreamServer
                                          ├─ /ws (WebSocket API)
                                          ├─ /stream/{id} (MJPEG)
                                          ├─ /snapshot/{id} (JPEG)
                                          └─ / (React SPA)
                                          │
                                          ▼
                                        [Browser / React Frontend]
```

## Detection Pipeline

```
Incoming JPEG frame
  → Decode
  → Frame rate limiting (max_fps)
  → Record raw frame (if recording)
  → Motion detection (skip inference if static)
  → YOLO / OpenVINO inference
  → Annotate detections on frame
  → Zone evaluation → fire triggers (KNX / webhook)
  → Encode to JPEG → MJPEG stream + stats broadcast
```

## HTTP Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/ws` | WebSocket API (all control messages) |
| GET | `/stream/{camera_id}` | MJPEG multipart live stream |
| GET | `/snapshot/{camera_id}` | Single JPEG frame |
| GET | `/recordings/{filename}` | Download MP4 recording |
| GET | `/` | React frontend |

## WebSocket API

All camera control and configuration is done over the WebSocket at `/ws`.

### Camera Management
| Message | Description |
|---------|-------------|
| `list_cameras` | List all cameras with live stats |
| `add_camera` | Add a new camera |
| `update_camera` | Update camera settings |
| `remove_camera` | Remove camera and stop pipeline |

### Hardware Control (RPi)
| Message | Description |
|---------|-------------|
| `camera_hw_get` | Get current ISP settings from the Pi |
| `camera_hw_set` | Update ISP settings (exposure, gain, etc.) |
| `camera_hw_reset` | Reset ISP to defaults |

### Recording
| Message | Description |
|---------|-------------|
| `start_recording` / `stop_recording` | Control recording |
| `list_recordings` / `delete_recording` | Manage saved recordings |
| `play_recording` | Play back a recording as a virtual camera |
| `playback_pause` / `resume` / `seek` / `step` | Playback controls |

### TensorRT Engine Compilation
| Message | Description |
|---------|-------------|
| `list_engines` | List compiled `.engine` files |
| `compile_engine` | Compile a `.pt` model to TensorRT (async with progress) |
| `delete_engine` | Remove an engine file |

### Automation
| Message | Description |
|---------|-------------|
| `get_automation_settings` | Get KNX gateway configuration |
| `update_automation_settings` | Update KNX settings |

## Detection Backends

### YOLO (NVIDIA CUDA / TensorRT)

Default backend. Auto-detects CUDA. Place `.pt` weight files in the project root.
For best performance, compile to TensorRT engines via the web UI — the compiled
`.engine` files are stored in `engines/`.

### OpenVINO (Intel CPU/GPU)

Alternative backend for Intel hardware. Models are auto-downloaded from Open Model Zoo:

- `person-detection-retail-0013` (default)
- `person-detection-0200` / `0201` / `0202` / `0203`
- `pedestrian-detection-adas-0002`

## Zone Automation

Detection zones are polygons drawn on the camera view. When a person is detected
inside a zone, triggers fire automatically.

**Zone settings:**
- **Mode** — `intersect` (bounding box overlaps zone) or `included` (fully inside)
- **Attack frames** — detections per second required to activate
- **Hold time** — seconds to stay active after last detection

**Trigger types:**
- **KNX** — send a value to a KNX group address (boolean or 1-byte)
- **Webhook** — HTTP GET to configurable on/off URLs

### KNX Setup

1. Open the Automation panel in the web UI
2. Enter your KNX gateway IP (default `192.168.178.5`) and port (`3671`)
3. Select connection type: `tunneling` (point-to-point) or `routing` (multicast)
4. Enable KNX
5. Configure triggers on individual zones with group addresses

## Recording

Enable recording via the environment variable:

```bash
RECORDING_ENABLED=1 uv run main.py
```

Recordings are saved to `recordings/` as MP4 files with JSON metadata.
The web UI provides playback with frame-stepping, seeking, and range selection.

## TLS / Encryption

Both the frame stream (port 8081) and the settings WebSocket (port 8082) support
TLS encryption. When adding a camera, enable **Use TLS** if the Pi was set up
with TLS during installation.

The InferenceServer connects as a TLS client. In development mode (no CA cert
configured), server certificate verification is disabled. For production, set
`ca_cert` in the camera config to pin the Pi's self-signed certificate.

## Configuration

### Server (`app/config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `WEB_HOST` | `"0.0.0.0"` | Bind address |
| `WEB_PORT` | `8090` | HTTP port |
| `CAMERAS_FILE` | `"cameras.json"` | Camera config persistence |
| `RECORDINGS_DIR` | `"recordings"` | Recording output directory |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RECORDING_ENABLED` | `"0"` | Enable recording (`"1"` to enable) |
| `RECORDINGS_DIR` | `"recordings"` | Override recording directory |
| `KNX_GATEWAY_IP` | `"192.168.178.5"` | KNX gateway IP |
| `KNX_GATEWAY_PORT` | `"3671"` | KNX gateway port |

### Camera Settings (via web UI / `cameras.json`)

| Field | Default | Description |
|-------|---------|-------------|
| `host` | `"192.168.178.30"` | Pi IP address |
| `port` | `8081` | Frame stream port |
| `camera_ws_port` | `8082` | Settings WebSocket port |
| `use_tls` | `false` | Enable TLS for this camera |
| `detector_backend` | `"yolo"` | `"yolo"` or `"openvino"` |
| `yolo_model` | `"yolo11m.pt"` | YOLO weight file or `.engine` |
| `yolo_confidence` | `0.5` | Detection confidence threshold |
| `yolo_person_only` | `true` | Detect only persons |
| `max_fps` | `30` | Pipeline frame rate cap |
| `motion_detection_enabled` | `false` | Skip inference on static frames |
| `zones` | `[]` | Automation zone definitions |

## Frontend Development

The React frontend is in `frontend/`. For development with hot reload:

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies API requests to the backend on port 8090.

For production, build and let the backend serve the static files:

```bash
npm run build
```

## Project Structure

```
InferenceServer/
├── main.py                     # Entry point
├── pyproject.toml              # Dependencies (uv/pip)
├── cameras.json                # Camera config (auto-generated)
├── automation_settings.json    # KNX config (auto-generated)
├── engines/                    # Compiled TensorRT engines
├── recordings/                 # Recorded MP4 + JSON metadata
├── app/
│   ├── config.py               # Server configuration
│   ├── web_server.py           # aiohttp routes + static serving
│   ├── ws_api.py               # WebSocket API handler
│   ├── pipeline_manager.py     # Per-camera detection pipelines
│   ├── camera_store.py         # Camera config persistence
│   ├── camera_hw_proxy.py      # WebSocket tunnel to RPi settings
│   ├── detector.py             # YOLO detection (CUDA/TensorRT)
│   ├── detector_openvino.py    # OpenVINO detection (Intel)
│   ├── motion_detector.py      # Frame-diff motion detection
│   ├── zone_evaluator.py       # Detection zone evaluation
│   ├── trigger_executor.py     # KNX + webhook trigger execution
│   ├── knx_manager.py          # KNX gateway connection
│   ├── automation_settings.py  # Automation config store
│   ├── engine_manager.py       # TensorRT engine compilation
│   ├── recorder.py             # MP4 video recording
│   ├── stream_viewer.py        # MJPEG multipart streaming
│   └── inputs/
│       ├── base.py             # InputReceiver base class
│       ├── rpi_tls.py          # TCP/TLS receiver for RPi cameras
│       └── recording_input.py  # MP4 playback as virtual camera
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx
        ├── context/CameraContext.tsx
        ├── hooks/useWebSocket.ts
        ├── types/camera.ts
        └── components/
            ├── CameraGrid.tsx
            ├── CameraView.tsx
            ├── CameraSettings.tsx
            ├── CameraHWSettings.tsx
            ├── AddCameraModal.tsx
            ├── RecordingsPanel.tsx
            ├── AutomationPanel.tsx
            ├── EngineManager.tsx
            ├── ZoneOverlay.tsx
            ├── Sidebar.tsx
            └── ConnectionStatus.tsx
```

### Raspberry Pi (TLS)
Connects as a TLS client to the PiCamStream server running on a Pi Zero 2 W
(or similar). Supports:
- **Server cert verification** — set `RPI_CA_CERT` to the Pi's certificate
- **Mutual TLS (mTLS)** — set `RPI_CLIENT_CERT` and `RPI_CLIENT_KEY`
- **Dev mode** — leave `RPI_CA_CERT = None` to skip verification (insecure)

Both sources use the same wire protocol: `[4-byte BE length][JPEG data]`.
