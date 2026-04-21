"""Server-level configuration constants.

Per-camera settings (detector, input, motion) are stored in cameras.json
and managed via the WebSocket API.
"""

import os

# =============================================================================
# Web Server
# =============================================================================

WEB_HOST = "0.0.0.0"
WEB_PORT = 8090

# =============================================================================
# Camera Database
# =============================================================================

CAMERAS_FILE = "cameras.json"

# =============================================================================
# Recording  (enable with --record flag or RECORDING_ENABLED=1 env var)
# =============================================================================

RECORDING_ENABLED = os.environ.get("RECORDING_ENABLED", "0") == "1"
RECORDINGS_DIR = os.environ.get("RECORDINGS_DIR", "recordings")

# =============================================================================
# Automation / KNX  (global defaults, overridden by automation_settings.json)
# =============================================================================

AUTOMATION_SETTINGS_FILE = "automation_settings.json"
KNX_GATEWAY_IP = os.environ.get("KNX_GATEWAY_IP", "192.168.178.5")
KNX_GATEWAY_PORT = int(os.environ.get("KNX_GATEWAY_PORT", "3671"))
KNX_CONNECTION_TYPE = os.environ.get("KNX_CONNECTION_TYPE", "tunneling")  # tunneling | routing
