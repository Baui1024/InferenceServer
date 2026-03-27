"""Camera Stream Inference Server.

Receives JPEG frames from either an ESP32 (plain TCP) or a Raspberry Pi
(TLS-encrypted TCP), runs object detection, and displays the annotated
output in an OpenCV window.
"""

import asyncio
import signal
import sys
import time

import cv2
import numpy as np
from loguru import logger

from app.config import (
    INPUT_SOURCE,
    # ESP32
    ESP32_HOST,
    ESP32_PORT,
    # RPi
    RPI_HOST,
    RPI_PORT,
    RPI_USE_TLS,
    RPI_CA_CERT,
    RPI_CLIENT_CERT,
    RPI_CLIENT_KEY,
    # Detector
    DETECTOR_BACKEND,
    YOLO_MODEL,
    YOLO_CONFIDENCE,
    YOLO_PERSON_ONLY,
    OPENVINO_MODEL,
    OPENVINO_DEVICE,
    OPENVINO_CONFIDENCE,
    # Display
    WINDOW_NAME,
    SHOW_FPS,
    # Web
    WEB_HOST,
    WEB_PORT,
    WEB_JPEG_QUALITY,
    # Motion
    MOTION_DETECTION_ENABLED,
    MOTION_THRESHOLD,
    MOTION_MIN_AREA_PERCENT,
)
from app.inputs.base import InputReceiver
from app.web_server import WebStreamServer
from app.motion_detector import MotionDetector

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO",
)

# ---------------------------------------------------------------------------
# Input factory
# ---------------------------------------------------------------------------


def create_input(on_frame) -> InputReceiver:
    """Instantiate the configured input receiver."""
    if INPUT_SOURCE == "esp32":
        from app.inputs.esp32_tcp import ESP32TCPReceiver

        return ESP32TCPReceiver(
            on_frame=on_frame,
            host=ESP32_HOST,
            port=ESP32_PORT,
        )
    elif INPUT_SOURCE == "rpi":
        from app.inputs.rpi_tls import RPiTLSReceiver

        return RPiTLSReceiver(
            on_frame=on_frame,
            host=RPI_HOST,
            port=RPI_PORT,
            use_tls=RPI_USE_TLS,
            ca_cert=RPI_CA_CERT,
            client_cert=RPI_CLIENT_CERT,
            client_key=RPI_CLIENT_KEY,
        )
    else:
        raise ValueError(f"Unknown INPUT_SOURCE: {INPUT_SOURCE!r}  (use 'esp32' or 'rpi')")


# ---------------------------------------------------------------------------
# Detector factory
# ---------------------------------------------------------------------------


def create_detector():
    """Instantiate the configured detector backend."""
    if DETECTOR_BACKEND == "yolo":
        from app.detector import Detector

        logger.info(f"Initializing YOLO detector (model={YOLO_MODEL})...")
        return Detector(
            model_name=YOLO_MODEL,
            confidence=YOLO_CONFIDENCE,
            person_only=YOLO_PERSON_ONLY,
        )
    elif DETECTOR_BACKEND == "openvino":
        from app.detector_openvino import OpenVINODetector

        logger.info(
            f"Initializing OpenVINO detector (model={OPENVINO_MODEL}, "
            f"device={OPENVINO_DEVICE})..."
        )
        return OpenVINODetector(
            model_name=OPENVINO_MODEL,
            confidence=OPENVINO_CONFIDENCE,
            device=OPENVINO_DEVICE,
        )
    else:
        raise ValueError(f"Unknown DETECTOR_BACKEND: {DETECTOR_BACKEND!r}")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class InferencePipeline:
    """Decode JPEG → motion check → detection → display."""

    def __init__(self, detector, viewer: WebStreamServer):
        self.detector = detector
        self.viewer = viewer
        self._inference_times: list[float] = []
        self._skipped_count = 0
        self._total_count = 0
        self._motion_detector = MotionDetector(
            threshold=MOTION_THRESHOLD,
            min_area_percent=MOTION_MIN_AREA_PERCENT,
        )
        self._last_annotated: np.ndarray | None = None

    @staticmethod
    def _draw_detections(frame: np.ndarray, detections: list) -> np.ndarray:
        """Draw bounding boxes from raw detections onto the frame."""
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
            conf = det["confidence"]
            label = f'{det["class_name"]} {conf:.2f}'

            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(
                annotated,
                (x1, y1 - label_size[1] - 10),
                (x1 + label_size[0], y1),
                (0, 255, 0),
                -1,
            )
            cv2.putText(
                annotated, label, (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2,
            )
        return annotated

    def process_frame(self, jpeg_data: bytes) -> None:
        if len(jpeg_data) < 4 or jpeg_data[:2] != b"\xff\xd8" or jpeg_data[-2:] != b"\xff\xd9":
            return

        arr = np.frombuffer(jpeg_data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return

        self._total_count += 1

        if MOTION_DETECTION_ENABLED and not self._motion_detector.has_motion(frame):
            self._skipped_count += 1
            self.viewer.push_array(frame, self._motion_detector.last_change_percent)
            return

        start = time.perf_counter()
        detections = self.detector.detect_raw(frame)
        inference_ms = (time.perf_counter() - start) * 1000

        annotated = self._draw_detections(frame, detections)
        self._last_annotated = annotated
        self._inference_times.append(inference_ms)
        if len(self._inference_times) >= 50:
            avg = sum(self._inference_times) / len(self._inference_times)
            skip_rate = (self._skipped_count / max(1, self._total_count)) * 100
            logger.info(f"Inference: {avg:.1f}ms avg | Skipped: {skip_rate:.0f}% (motion filter)")
            self._inference_times.clear()
            self._skipped_count = 0
            self._total_count = 0

        change = self._motion_detector.last_change_percent if MOTION_DETECTION_ENABLED else 0.0
        self.viewer.push_array(annotated, change)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    logger.info(f"Input: {INPUT_SOURCE.upper()} | Detector: {DETECTOR_BACKEND.upper()}")

    detector = create_detector()
    viewer = WebStreamServer(host=WEB_HOST, port=WEB_PORT, jpeg_quality=WEB_JPEG_QUALITY)
    pipeline = InferencePipeline(detector, viewer)

    receiver = create_input(on_frame=pipeline.process_frame)

    await viewer.start()
    await receiver.start()

    logger.info(f"Open http://localhost:{WEB_PORT} in your browser — Ctrl+C to quit")

    loop = asyncio.get_event_loop()
    stop = asyncio.Event()

    def _signal():
        logger.info("Shutdown signal received")
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal)
        except NotImplementedError:
            pass

    try:
        await stop.wait()
    except KeyboardInterrupt:
        pass

    await receiver.stop()
    await viewer.stop()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
