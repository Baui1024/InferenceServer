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
