"""Motion detection to skip inference on static frames."""

import cv2
import numpy as np


class MotionDetector:
    """Detects motion between frames using frame differencing."""

    def __init__(
        self,
        threshold: float = 4.0,
        min_area_percent: float = 0.5,
        scale: float = 0.25,
        blur_size: int = 5,
    ):
        """
        Initialize motion detector.

        Args:
            threshold: Pixel difference threshold as percentage (0-100). Higher = less sensitive.
            min_area_percent: Minimum % of pixels that must change to detect motion.
            scale: Downscale factor for faster comparison (0.25 = 1/4 resolution).
            blur_size: Gaussian blur kernel size for noise reduction.
        """
        # Convert percentage threshold to 0-255 scale for pixel comparison
        self.threshold = (threshold / 100.0) * 255.0
        self.min_area_percent = min_area_percent
        self.scale = scale
        self.blur_size = blur_size
        self._prev_gray: np.ndarray | None = None
        self._last_change_percent: float = 0.0

    def reset(self) -> None:
        """Reset state (e.g., after scene change or reconnect)."""
        self._prev_gray = None
        self._last_change_percent = 0.0

    def has_motion(self, frame: np.ndarray) -> bool:
        """
        Check if frame has significant motion compared to previous.

        Args:
            frame: BGR image as numpy array

        Returns:
            True if motion detected, False if static scene
        """
        # Downscale for faster comparison
        small = cv2.resize(frame, (0, 0), fx=self.scale, fy=self.scale)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return True  # First frame always triggers

        # Compute absolute difference
        diff = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray

        # Count pixels above threshold
        changed_pixels = np.sum(diff > self.threshold)
        total_pixels = diff.size
        self._last_change_percent = (changed_pixels / total_pixels) * 100

        return self._last_change_percent >= self.min_area_percent

    @property
    def last_change_percent(self) -> float:
        """Get the change percentage from the last comparison."""
        return self._last_change_percent

    def get_diff_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Get visualization of motion (for debugging).

        Args:
            frame: BGR image as numpy array

        Returns:
            Grayscale diff image (same size as input)
        """
        small = cv2.resize(frame, (0, 0), fx=self.scale, fy=self.scale)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (self.blur_size, self.blur_size), 0)

        if self._prev_gray is None:
            return np.zeros_like(frame[:, :, 0])

        diff = cv2.absdiff(self._prev_gray, gray)
        # Upscale back to original size
        return cv2.resize(diff, (frame.shape[1], frame.shape[0]))
