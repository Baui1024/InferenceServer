"""Configuration constants for the inference server."""

# =============================================================================
# Input Source — pick ONE: "esp32" or "rpi"
# =============================================================================

INPUT_SOURCE = "rpi"

# =============================================================================
# ESP32 Connection (plain TCP — no encryption)
# =============================================================================

ESP32_HOST = "192.168.178.245"
ESP32_PORT = 8081

# =============================================================================
# Raspberry Pi Connection (TLS-encrypted TCP)
# =============================================================================

RPI_HOST = "192.168.178.30"
RPI_PORT = 8081

# Set to False if the Pi streams plain TCP (no TLS).
RPI_USE_TLS = False

# TLS certificate of the Pi (or CA that signed it). Set to None to skip
# verification during development (insecure).
RPI_CA_CERT = None  # e.g. "certs/picam_cert.pem"

# Client certificate + key for mutual TLS (optional).
RPI_CLIENT_CERT = None  # e.g. "certs/client_cert.pem"
RPI_CLIENT_KEY = None   # e.g. "certs/client_key.pem"

# =============================================================================
# Detector Configuration
# =============================================================================

# Backend: "yolo" (NVIDIA CUDA) or "openvino" (Intel CPU/iGPU)
DETECTOR_BACKEND = "yolo"

# YOLO settings (used when DETECTOR_BACKEND = "yolo")
YOLO_MODEL = "yolo11m.pt"
YOLO_CONFIDENCE = 0.5
YOLO_PERSON_ONLY = True

# OpenVINO settings (used when DETECTOR_BACKEND = "openvino")
OPENVINO_DEVICE = "CPU"
OPENVINO_CONFIDENCE = 0.1
OPENVINO_MODEL = "person-detection-retail-0013"

# =============================================================================
# Display
# =============================================================================

WINDOW_NAME = "Camera + Detection"
SHOW_FPS = True

# =============================================================================
# Web Stream Server
# =============================================================================

WEB_HOST = "0.0.0.0"
WEB_PORT = 8090
WEB_JPEG_QUALITY = 80

# =============================================================================
# Motion Detection (skip inference on static frames)
# =============================================================================

MOTION_DETECTION_ENABLED = False
MOTION_THRESHOLD = 2.0
MOTION_MIN_AREA_PERCENT = 0.15
