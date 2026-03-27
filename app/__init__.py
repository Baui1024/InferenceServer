"""Inference Server — camera stream processing with object detection."""

from .detector import Detector
from .stream_viewer import StreamViewer

__all__ = ["Detector", "StreamViewer"]
