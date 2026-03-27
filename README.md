# Inference Server

Object detection inference server that receives JPEG frames from either an
**ESP32** (plain TCP) or a **Raspberry Pi** (TLS-encrypted TCP) and runs
YOLO / OpenVINO detection in real time.

## Project Layout

```
InferenceServer/
├── main.py                       # Entry point
├── pyproject.toml
└── app/
    ├── config.py                 # All settings (input source, detector, display)
    ├── detector.py               # YOLO (NVIDIA CUDA)
    ├── detector_openvino.py      # OpenVINO (Intel CPU/iGPU)
    ├── motion_detector.py        # Skip inference on static frames
    ├── stream_viewer.py          # OpenCV display window
    └── inputs/
        ├── base.py               # InputReceiver ABC
        ├── esp32_tcp.py          # Plain TCP client → ESP32
        └── rpi_tls.py            # TLS TCP client  → Raspberry Pi
```

## Setup

```bash
uv sync          # or: pip install .
```

Copy your YOLO model weights (e.g. `yolo11m.pt`) into the project root.

## Usage

1. Set `INPUT_SOURCE` in `app/config.py`:
   - `"esp32"` — connects to an ESP32 camera over plain TCP
   - `"rpi"` — connects to a Raspberry Pi running PiCamStream over TLS

2. Configure the matching host/port and (for RPi) TLS certificate paths.

3. Run:
   ```bash
   python main.py
   ```

## Input Sources

### ESP32 (plain TCP)
Connects as a TCP client to the ESP32's built-in TCP server. No encryption —
the ESP32-S3 lacks the resources for TLS at usable frame rates.

### Raspberry Pi (TLS)
Connects as a TLS client to the PiCamStream server running on a Pi Zero 2 W
(or similar). Supports:
- **Server cert verification** — set `RPI_CA_CERT` to the Pi's certificate
- **Mutual TLS (mTLS)** — set `RPI_CLIENT_CERT` and `RPI_CLIENT_KEY`
- **Dev mode** — leave `RPI_CA_CERT = None` to skip verification (insecure)

Both sources use the same wire protocol: `[4-byte BE length][JPEG data]`.
