"""Per-camera detection pipelines running concurrently."""

import asyncio
import threading
import time
from typing import Optional

import cv2
import numpy as np
from loguru import logger

import app.config as config
from app.motion_detector import MotionDetector
from app.inputs.base import InputReceiver
from app.recorder import VideoRecorder


# ---------------------------------------------------------------------------
# Factory helpers — create detector / input from a camera config dict
# ---------------------------------------------------------------------------

def create_detector_for(cfg: dict):
    """Instantiate a detector based on a camera config dict."""
    backend = cfg.get("detector_backend", "yolo")
    if backend == "yolo":
        from app.detector import Detector
        return Detector(
            model_name=cfg.get("yolo_model", "yolo11m.pt"),
            confidence=cfg.get("yolo_confidence", 0.5),
            person_only=cfg.get("yolo_person_only", True),
        )
    elif backend == "openvino":
        from app.detector_openvino import OpenVINODetector
        return OpenVINODetector(
            model_name=cfg.get("openvino_model", "person-detection-retail-0013"),
            confidence=cfg.get("openvino_confidence", 0.1),
            device=cfg.get("openvino_device", "CPU"),
        )
    else:
        raise ValueError(f"Unknown detector backend: {backend!r}")


def create_input_for(cfg: dict, on_frame) -> InputReceiver:
    """Instantiate an input receiver based on a camera config dict."""
    cam_type = cfg.get("type", "rpi")
    if cam_type == "rpi":
        from app.inputs.rpi_tls import RPiTLSReceiver
        return RPiTLSReceiver(
            on_frame=on_frame,
            host=cfg["host"],
            port=cfg["port"],
            use_tls=cfg.get("use_tls", False),
            ca_cert=cfg.get("ca_cert"),
            client_cert=cfg.get("client_cert"),
            client_key=cfg.get("client_key"),
        )
    elif cam_type == "recording":
        from app.inputs.recording_input import RecordingInput
        return RecordingInput(
            on_frame=on_frame,
            recording_id=cfg["recording_id"],
            playback_fps=cfg.get("playback_fps", 0),
            loop_playback=cfg.get("loop_playback", False),
        )
    else:
        raise ValueError(f"Unknown camera type: {cam_type!r}")


# ---------------------------------------------------------------------------
# Drawing helper
# ---------------------------------------------------------------------------

def draw_detections(frame: np.ndarray, detections: list) -> np.ndarray:
    """Draw bounding boxes from raw detections onto a frame."""
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        conf = det["confidence"]
        label = f'{det["class_name"]} {conf:.2f}'
        below = det.get("below_threshold", False)
        color = (0, 0, 255) if below else (0, 255, 0)  # red for below, green for above

        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(
            annotated,
            (x1, y1 - label_size[1] - 10),
            (x1 + label_size[0], y1),
            color,
            -1,
        )
        text_color = (255, 255, 255) if below else (0, 0, 0)
        cv2.putText(
            annotated, label, (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, text_color, 2,
        )
    return annotated


# ---------------------------------------------------------------------------
# Single camera pipeline
# ---------------------------------------------------------------------------

class CameraPipeline:
    """Receives frames for one camera, runs detection, stores latest JPEG."""

    def __init__(self, camera_id: str, cfg: dict, loop: asyncio.AbstractEventLoop):
        self.camera_id = camera_id
        self.cfg = cfg
        self._loop = loop

        self._lock = threading.Lock()
        self._latest_jpeg: Optional[bytes] = None
        self._frame_count = 0
        self._fps = 0.0
        self._fps_frame_count = 0
        self._last_fps_time = time.time()
        self._inference_times: list[float] = []
        self._avg_inference_ms = 0.0
        self._detection_count = 0
        self._status = "starting"  # starting | running | stopped | error

        self._receiver: Optional[InputReceiver] = None
        self._detector = None
        self._motion_detector: Optional[MotionDetector] = None

        # Frame rate limiter
        self._max_fps = cfg.get("max_fps", 30)
        self._min_interval = 1.0 / self._max_fps if self._max_fps > 0 else 0
        self._last_process_time = 0.0

        # Recording (pre-detection raw frames)
        self._recorder: Optional[VideoRecorder] = None

    # -- Lifecycle --

    async def start(self) -> None:
        """Initialize detector + receiver and start streaming."""
        name = self.cfg.get("name", self.camera_id[:8])
        try:
            logger.info(f"[{name}] Starting pipeline...")
            self._detector = create_detector_for(self.cfg)

            if self.cfg.get("motion_detection_enabled"):
                self._motion_detector = MotionDetector(
                    threshold=self.cfg.get("motion_threshold", 2.0),
                    min_area_percent=self.cfg.get("motion_min_area_percent", 0.15),
                )

            self._receiver = create_input_for(self.cfg, self._process_frame)
            await self._receiver.start()
            self._status = "running"
            logger.info(f"[{name}] Pipeline running")
        except Exception as e:
            self._status = "error"
            logger.error(f"[{name}] Failed to start pipeline: {e}")
            raise

    async def stop(self) -> None:
        """Stop the receiver and release resources."""
        self._status = "stopped"
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop()
            self._recorder = None
        if self._receiver:
            try:
                await self._receiver.stop()
            except Exception:
                pass
            self._receiver = None
        self._detector = None
        self._motion_detector = None
        logger.info(f"[{self.cfg.get('name', self.camera_id[:8])}] Pipeline stopped")

    # -- Recording controls --

    def start_recording(self) -> Optional[str]:
        """Start recording raw frames. Returns recording id or None."""
        if not config.RECORDING_ENABLED:
            return None
        if self._recorder and self._recorder.is_recording:
            return self._recorder.recording_id
        self._recorder = VideoRecorder(
            camera_id=self.camera_id,
            camera_name=self.cfg.get("name", self.camera_id[:8]),
            fps=self._max_fps or 15.0,
        )
        return self._recorder.start()

    def stop_recording(self) -> Optional[dict]:
        """Stop recording. Returns recording metadata or None."""
        if self._recorder and self._recorder.is_recording:
            meta = self._recorder.stop()
            self._recorder = None
            return meta
        return None

    @property
    def is_recording(self) -> bool:
        return self._recorder is not None and self._recorder.is_recording

    # -- Frame processing (called from receiver thread) --

    def _process_frame(self, frame_data) -> None:
        """Callback from input receiver — runs in receiver's thread.
        
        Args:
            frame_data: Either raw JPEG bytes or a decoded numpy array (BGR).
        """
        # Handle both JPEG bytes and pre-decoded numpy arrays
        if isinstance(frame_data, np.ndarray):
            frame = frame_data
        else:
            # JPEG bytes — validate and decode
            jpeg_data = frame_data
            if len(jpeg_data) < 4 or jpeg_data[:2] != b"\xff\xd8" or jpeg_data[-2:] != b"\xff\xd9":
                return

            arr = np.frombuffer(jpeg_data, dtype=np.uint8)
            frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if frame is None:
                return

        # Frame rate limiter
        now = time.time()
        if now - self._last_process_time < self._min_interval:
            return
        self._last_process_time = now

        # Record raw frame (pre-detection)
        if self._recorder and self._recorder.is_recording:
            self._recorder.write_frame(frame)

        # Motion detection skip
        if self._motion_detector and not self._motion_detector.has_motion(frame):
            if self.cfg.get("show_motion_debug"):
                frame = self._overlay_motion(frame)
            self._encode_and_store(frame)
            return

        # Inference
        if self._detector is None:
            return
        start = time.perf_counter()
        low_conf = self.cfg.get("show_below_confidence", False)
        detections = self._detector.detect_raw(frame, low_confidence=low_conf)
        inference_ms = (time.perf_counter() - start) * 1000

        annotated = draw_detections(frame, detections) if detections else frame

        if self._motion_detector and self.cfg.get("show_motion_debug"):
            annotated = self._overlay_motion(annotated)

        # Update stats
        with self._lock:
            self._detection_count += len(detections)
            self._inference_times.append(inference_ms)
            if len(self._inference_times) >= 30:
                self._avg_inference_ms = sum(self._inference_times) / len(self._inference_times)
                self._inference_times.clear()

        self._encode_and_store(annotated)

    def _overlay_motion(self, frame: np.ndarray) -> np.ndarray:
        """Overlay a motion heatmap + stats text onto the frame."""
        if not self._motion_detector:
            return frame
        diff = self._motion_detector.get_diff_frame(frame)
        # Colorize the diff as a heatmap
        heatmap = cv2.applyColorMap(diff, cv2.COLORMAP_JET)
        # Blend onto frame (30% heatmap)
        blended = cv2.addWeighted(frame, 0.7, heatmap, 0.3, 0)
        # Draw motion % text
        pct = self._motion_detector.last_change_percent
        triggered = pct >= self.cfg.get("motion_min_area_percent", 0.15)
        color = (0, 255, 0) if triggered else (0, 0, 255)
        text = f"Motion: {pct:.2f}%"
        cv2.putText(blended, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        return blended

    def _encode_and_store(self, frame: np.ndarray) -> None:
        """JPEG-encode the frame and store it for streaming."""
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        jpeg = buf.tobytes()

        with self._lock:
            self._latest_jpeg = jpeg
            self._frame_count += 1
            self._fps_frame_count += 1

            now = time.time()
            elapsed = now - self._last_fps_time
            if elapsed >= 1.0:
                self._fps = self._fps_frame_count / elapsed
                self._fps_frame_count = 0
                self._last_fps_time = now

    # -- Public data access --

    def get_latest_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def get_recording_input(self):
        """Return the RecordingInput if this is a recording pipeline, else None."""
        from app.inputs.recording_input import RecordingInput
        if isinstance(self._receiver, RecordingInput):
            return self._receiver
        return None

    def get_stats(self) -> dict:
        with self._lock:
            motion_pct = 0.0
            if self._motion_detector:
                motion_pct = round(self._motion_detector.last_change_percent, 2)
            stats = {
                "id": self.camera_id,
                "status": self._status,
                "fps": round(self._fps, 1),
                "inference_ms": round(self._avg_inference_ms, 1),
                "detection_count": self._detection_count,
                "frame_count": self._frame_count,
                "motion_pct": motion_pct,
            }
            # Add playback info if this is a recording pipeline
            if self._receiver and hasattr(self._receiver, 'get_playback_info'):
                stats["playback"] = self._receiver.get_playback_info()
            return stats


# ---------------------------------------------------------------------------
# Pipeline manager — manages all camera pipelines
# ---------------------------------------------------------------------------

class PipelineManager:
    """Manages concurrent CameraPipeline instances."""

    def __init__(self):
        self._pipelines: dict[str, CameraPipeline] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start_all(self, cameras: list[dict]) -> None:
        """Start a pipeline for each enabled camera."""
        self._loop = asyncio.get_event_loop()
        for cam in cameras:
            if cam.get("enabled", True):
                await self.start_camera(cam)

    async def start_camera(self, cfg: dict) -> None:
        """Start (or restart) a single camera pipeline."""
        camera_id = cfg["id"]
        if camera_id in self._pipelines:
            await self.stop_camera(camera_id)

        loop = self._loop or asyncio.get_event_loop()
        pipeline = CameraPipeline(camera_id, cfg, loop)
        self._pipelines[camera_id] = pipeline
        try:
            await pipeline.start()
        except Exception:
            self._pipelines.pop(camera_id, None)

    async def stop_camera(self, camera_id: str) -> None:
        """Stop a single camera pipeline."""
        pipeline = self._pipelines.pop(camera_id, None)
        if pipeline:
            await pipeline.stop()

    async def stop_all(self) -> None:
        """Stop all pipelines."""
        ids = list(self._pipelines.keys())
        for cid in ids:
            await self.stop_camera(cid)

    def get_pipeline(self, camera_id: str) -> Optional[CameraPipeline]:
        return self._pipelines.get(camera_id)

    def get_latest_jpeg(self, camera_id: str) -> Optional[bytes]:
        p = self._pipelines.get(camera_id)
        return p.get_latest_jpeg() if p else None

    def get_stats(self, camera_id: str) -> Optional[dict]:
        p = self._pipelines.get(camera_id)
        return p.get_stats() if p else None

    def get_all_stats(self) -> list[dict]:
        return [p.get_stats() for p in self._pipelines.values()]
