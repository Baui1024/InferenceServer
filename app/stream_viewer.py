"""OpenCV window viewer for displaying JPEG frames."""

import threading
import time
from typing import Optional

import cv2
import numpy as np
from loguru import logger


class StreamViewer:
    """Displays frames in an OpenCV window with thread-safe frame pushing."""

    def __init__(self, window_name: str = "ESP32 Camera Stream", show_fps: bool = True):
        """
        Initialize the viewer.

        Args:
            window_name: Title of the OpenCV window
            show_fps: Whether to overlay FPS counter on frames
        """
        self.window_name = window_name
        self.show_fps = show_fps
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._frame_count = 0
        self._fps = 0.0
        self._last_fps_time = time.time()
        self._fps_frame_count = 0
        self._motion_change = 0.0

    def push_frame(self, jpeg_data: bytes) -> None:
        """
        Push a new JPEG frame to display.

        Args:
            jpeg_data: Raw JPEG bytes from the camera
        """
        # Decode JPEG to numpy array
        arr = np.frombuffer(jpeg_data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        if frame is None:
            logger.warning(f"Failed to decode JPEG frame ({len(jpeg_data)} bytes)")
            return

        self.push_array(frame)

    def push_array(self, frame: np.ndarray, motion_change: float = 0.0) -> None:
        """
        Push a numpy array frame to display.

        Args:
            frame: BGR image as numpy array
            motion_change: Motion change percentage (0-100)
        """
        with self._lock:
            self._frame = frame
            self._motion_change = motion_change
            self._frame_count += 1
            self._fps_frame_count += 1
            
            # Calculate FPS every second
            now = time.time()
            elapsed = now - self._last_fps_time
            if elapsed >= 1.0:
                self._fps = self._fps_frame_count / elapsed
                self._fps_frame_count = 0
                self._last_fps_time = now

    def start(self) -> None:
        """Start the viewer in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._display_loop, daemon=True)
        self._thread.start()
        logger.info(f"StreamViewer started: '{self.window_name}'")

    def stop(self) -> None:
        """Stop the viewer and close the window."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        cv2.destroyWindow(self.window_name)
        logger.info("StreamViewer stopped")

    def _display_loop(self) -> None:
        """Background thread loop for updating the OpenCV window."""
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.window_name, 1280, 720)
        last_count = 0

        while self._running:
            with self._lock:
                frame = self._frame.copy() if self._frame is not None else None
                count = self._frame_count
                fps = self._fps
                motion = self._motion_change

            if frame is not None and count != last_count:
                # Overlay FPS and motion counters
                if self.show_fps:
                    text = f"FPS: {fps:.1f}  Motion: {motion:.1f}%"
                    cv2.putText(
                        frame, text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2
                    )
                
                cv2.imshow(self.window_name, frame)
                last_count = count

            # Process GUI events, check for 'q' key to quit
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                logger.info("Quit key pressed")
                self._running = False
                break

        cv2.destroyAllWindows()
