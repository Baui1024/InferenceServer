"""JSON-file backed camera configuration store."""

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

# Default values for a new camera entry
_DEFAULTS = {
    "name": "New Camera",
    "type": "rpi",
    "host": "192.168.178.30",
    "port": 8081,
    "enabled": True,
    # RPi connection
    "use_tls": False,
    "ca_cert": None,
    "client_cert": None,
    "client_key": None,
    # Detection
    "detector_backend": "yolo",
    "yolo_model": "yolo11m.pt",
    "yolo_confidence": 0.5,
    "yolo_person_only": True,
    "openvino_model": "person-detection-retail-0013",
    "openvino_device": "CPU",
    "openvino_confidence": 0.1,
    # Pipeline
    "max_fps": 30,
    "motion_detection_enabled": False,
    "motion_threshold": 2.0,
    "motion_min_area_percent": 0.15,
    # Camera hardware WS (RPi only)
    "camera_ws_port": 8082,
}

# Fields that require a pipeline restart when changed
PIPELINE_FIELDS = {
    "type", "host", "port", "enabled",
    "use_tls", "ca_cert", "client_cert", "client_key",
    "detector_backend", "yolo_model", "yolo_confidence", "yolo_person_only",
    "openvino_model", "openvino_device", "openvino_confidence",
    "max_fps", "motion_detection_enabled", "motion_threshold", "motion_min_area_percent",
    "recording_id", "loop_playback", "playback_fps",
}


class CameraStore:
    """Thread-safe JSON-file camera storage."""

    def __init__(self, path: str = "cameras.json"):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._cameras: list[dict] = []
        self.load()

    def load(self) -> list[dict]:
        """Load cameras from disk. Returns empty list if file doesn't exist."""
        with self._lock:
            if self._path.exists():
                try:
                    data = json.loads(self._path.read_text(encoding="utf-8"))
                    self._cameras = data if isinstance(data, list) else []
                    logger.info(f"Loaded {len(self._cameras)} camera(s) from {self._path}")
                except (json.JSONDecodeError, OSError) as e:
                    logger.error(f"Failed to load {self._path}: {e}")
                    self._cameras = []
            else:
                self._cameras = []
            return [c.copy() for c in self._cameras]

    def _save(self) -> None:
        """Write cameras to disk atomically (tmp + rename). Must hold _lock."""
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._cameras, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(self._path))

    def all(self) -> list[dict]:
        """Return a copy of all cameras."""
        with self._lock:
            return [c.copy() for c in self._cameras]

    def get(self, camera_id: str) -> Optional[dict]:
        """Return a single camera by ID, or None."""
        with self._lock:
            for c in self._cameras:
                if c["id"] == camera_id:
                    return c.copy()
        return None

    def add(self, data: dict) -> dict:
        """Add a new camera. Fills in defaults for missing fields."""
        camera = {**_DEFAULTS, **data, "id": uuid.uuid4().hex}
        with self._lock:
            self._cameras.append(camera)
            self._save()
        logger.info(f"Added camera '{camera['name']}' ({camera['id'][:8]})")
        return camera.copy()

    def update(self, camera_id: str, data: dict) -> Optional[dict]:
        """Update fields on a camera. Returns updated camera or None."""
        data.pop("id", None)  # prevent ID overwrite
        with self._lock:
            for i, c in enumerate(self._cameras):
                if c["id"] == camera_id:
                    c.update(data)
                    self._save()
                    logger.info(f"Updated camera {camera_id[:8]}: {list(data.keys())}")
                    return c.copy()
        return None

    def remove(self, camera_id: str) -> bool:
        """Remove a camera by ID. Returns True if found."""
        with self._lock:
            before = len(self._cameras)
            self._cameras = [c for c in self._cameras if c["id"] != camera_id]
            if len(self._cameras) < before:
                self._save()
                logger.info(f"Removed camera {camera_id[:8]}")
                return True
        return False

    @staticmethod
    def needs_pipeline_restart(changes: dict) -> bool:
        """Check if any changed fields require a pipeline restart."""
        return bool(set(changes.keys()) & PIPELINE_FIELDS)
