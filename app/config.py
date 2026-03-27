"""Server-level configuration constants.

Per-camera settings (detector, input, motion) are stored in cameras.json
and managed via the WebSocket API.
"""

# =============================================================================
# Web Server
# =============================================================================

WEB_HOST = "0.0.0.0"
WEB_PORT = 8090

# =============================================================================
# Camera Database
# =============================================================================

CAMERAS_FILE = "cameras.json"
