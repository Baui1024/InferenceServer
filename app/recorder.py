"""Video recorder — writes raw (pre-detection) frames to MP4 files."""

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from loguru import logger

from app.config import RECORDINGS_DIR

_RECORDINGS_PATH = Path(RECORDINGS_DIR)


class VideoRecorder:
    """Records raw decoded frames to an MP4 file.

    Thread-safe: ``write_frame`` is called from the pipeline's receiver thread.
    """

    def __init__(self, camera_id: str, camera_name: str, fps: float = 15.0):
        self._camera_id = camera_id
        self._camera_name = camera_name
        self._fps = fps

        self._lock = threading.Lock()
        self._writer: Optional[cv2.VideoWriter] = None
        self._meta_path: Optional[Path] = None
        self._video_path: Optional[Path] = None
        self._frame_count = 0
        self._start_time: Optional[float] = None
        self._resolution: Optional[tuple[int, int]] = None
        self._recording_id: Optional[str] = None

    @property
    def is_recording(self) -> bool:
        with self._lock:
            return self._start_time is not None

    @property
    def recording_id(self) -> Optional[str]:
        return self._recording_id

    def start(self) -> str:
        """Begin recording. Returns the recording id (timestamp-based filename stem)."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in self._camera_name)
        self._recording_id = f"{safe_name}_{ts}"

        _RECORDINGS_PATH.mkdir(parents=True, exist_ok=True)
        self._video_path = _RECORDINGS_PATH / f"{self._recording_id}.mp4"
        self._meta_path = _RECORDINGS_PATH / f"{self._recording_id}.json"
        self._frame_count = 0
        self._start_time = time.time()
        self._resolution = None

        logger.info(f"Recording started: {self._recording_id}")
        return self._recording_id

    def write_frame(self, frame: np.ndarray) -> None:
        """Write a single raw frame. Called from the receiver thread."""
        with self._lock:
            if self._writer is None and self._video_path is not None and self._start_time is not None:
                h, w = frame.shape[:2]
                self._resolution = (w, h)
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                self._writer = cv2.VideoWriter(
                    str(self._video_path), fourcc, self._fps, (w, h)
                )
                if not self._writer.isOpened():
                    logger.error("Failed to open VideoWriter")
                    self._writer = None
                    return

            if self._writer is not None:
                self._writer.write(frame)
                self._frame_count += 1

    def stop(self) -> Optional[dict]:
        """Stop recording and write metadata. Returns recording info dict."""
        with self._lock:
            if self._writer is not None:
                self._writer.release()
                self._writer = None

        if self._start_time is None or self._video_path is None:
            return None

        duration = time.time() - self._start_time
        actual_fps = self._frame_count / duration if duration > 0 else 0

        meta = {
            "id": self._recording_id,
            "camera_id": self._camera_id,
            "camera_name": self._camera_name,
            "filename": self._video_path.name,
            "start_time": datetime.fromtimestamp(self._start_time, tz=timezone.utc).isoformat(),
            "duration_s": round(duration, 1),
            "frame_count": self._frame_count,
            "fps": round(actual_fps, 1),
            "resolution": list(self._resolution) if self._resolution else None,
        }

        if self._meta_path:
            self._meta_path.write_text(json.dumps(meta, indent=2))

        logger.info(
            f"Recording stopped: {self._recording_id} "
            f"({self._frame_count} frames, {duration:.1f}s)"
        )

        self._start_time = None
        self._recording_id = None
        return meta


def list_recordings() -> list[dict]:
    """Return metadata for all recordings on disk."""
    recordings = []
    if not _RECORDINGS_PATH.exists():
        return recordings
    for meta_file in sorted(_RECORDINGS_PATH.glob("*.json")):
        try:
            meta = json.loads(meta_file.read_text())
            video_file = _RECORDINGS_PATH / meta.get("filename", "")
            if video_file.exists():
                meta["size_mb"] = round(video_file.stat().st_size / (1024 * 1024), 1)
                recordings.append(meta)
        except Exception:
            continue
    return recordings


def get_recording(recording_id: str) -> Optional[dict]:
    """Get metadata for a single recording."""
    meta_path = _RECORDINGS_PATH / f"{recording_id}.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text())
        video_file = _RECORDINGS_PATH / meta.get("filename", "")
        if video_file.exists():
            meta["size_mb"] = round(video_file.stat().st_size / (1024 * 1024), 1)
        return meta
    except Exception:
        return None


def delete_recording(recording_id: str) -> bool:
    """Delete a recording's video + metadata files."""
    meta_path = _RECORDINGS_PATH / f"{recording_id}.json"
    video_path = _RECORDINGS_PATH / f"{recording_id}.mp4"
    deleted = False
    for p in (meta_path, video_path):
        if p.exists():
            p.unlink()
            deleted = True
    return deleted
