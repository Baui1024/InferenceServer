"""OpenVINO person detector using Intel's optimized models."""

from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from loguru import logger

try:
    import openvino as ov
    OPENVINO_AVAILABLE = True
except ImportError:
    OPENVINO_AVAILABLE = False

# Available models with their download URLs (Open Model Zoo 2022.3)
AVAILABLE_MODELS = {
    "person-detection-retail-0013": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.3/models_bin/1/person-detection-retail-0013/FP16",
    "person-detection-0200": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.3/models_bin/1/person-detection-0200/FP16",
    "person-detection-0201": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.3/models_bin/1/person-detection-0201/FP16",
    "person-detection-0202": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.3/models_bin/1/person-detection-0202/FP16",
    "person-detection-0203": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.3/models_bin/1/person-detection-0203/FP16",
    "pedestrian-detection-adas-0002": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2022.3/models_bin/1/pedestrian-detection-adas-0002/FP16",
}


class OpenVINODetector:
    """Runs person detection using OpenVINO inference engine."""

    def __init__(
        self,
        model_name: str = "person-detection-0203",
        model_path: Optional[str] = None,
        confidence: float = 0.5,
        device: str = "CPU",  # CPU, GPU, AUTO
    ):
        """
        Initialize the OpenVINO detector.

        Args:
            model_name: Name of the model from AVAILABLE_MODELS
            model_path: Path to .xml model file (auto-downloads if None)
            confidence: Minimum confidence threshold
            device: OpenVINO device (CPU, GPU, AUTO)
        """
        if not OPENVINO_AVAILABLE:
            raise ImportError("OpenVINO not installed. Run: uv add openvino")

        self.model_name = model_name
        self.confidence = confidence
        self.device = device

        # Download model if not provided
        if model_path is None:
            model_path = self._download_model(model_name)

        logger.info(f"Loading OpenVINO model: {model_path}")

        # Initialize OpenVINO
        self.core = ov.Core()
        self.model = self.core.read_model(model_path)
        self.compiled_model = self.core.compile_model(self.model, device)

        # Get input/output info
        self.input_layer = self.compiled_model.input(0)
        self.output_layer = self.compiled_model.output(0)

        # Expected input shape: [1, 3, H, W]
        self.input_shape = self.input_layer.shape
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]

        logger.info(f"OpenVINO Detector ready (device={device}, input={self.input_width}x{self.input_height})")

    def _download_model(self, model_name: str) -> str:
        """Download the person detection model if not cached."""
        import urllib.request

        if model_name not in AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(AVAILABLE_MODELS.keys())}")

        base_url = AVAILABLE_MODELS[model_name]

        cache_dir = Path.home() / ".cache" / "openvino_models"
        cache_dir.mkdir(parents=True, exist_ok=True)

        xml_path = cache_dir / f"{model_name}.xml"
        bin_path = cache_dir / f"{model_name}.bin"

        if not xml_path.exists():
            logger.info(f"Downloading {model_name}...")
            xml_url = f"{base_url}/{model_name}.xml"
            bin_url = f"{base_url}/{model_name}.bin"

            urllib.request.urlretrieve(xml_url, xml_path)
            urllib.request.urlretrieve(bin_url, bin_path)
            logger.info(f"Model downloaded to {cache_dir}")

        return str(xml_path)

    def detect(self, frame: np.ndarray) -> np.ndarray:
        """
        Run detection on a frame and return annotated frame.

        Args:
            frame: BGR image as numpy array

        Returns:
            Annotated frame with bounding boxes drawn
        """
        orig_height, orig_width = frame.shape[:2]

        # Preprocess: resize and transpose to NCHW
        resized = cv2.resize(frame, (self.input_width, self.input_height))
        input_data = resized.transpose(2, 0, 1)  # HWC -> CHW
        input_data = input_data.reshape(1, 3, self.input_height, self.input_width)

        # Run inference
        results = self.compiled_model([input_data])[self.output_layer]

        # Parse results: [1, 1, N, 7] where 7 = [image_id, label, conf, x1, y1, x2, y2]
        annotated = frame.copy()

        for detection in results[0][0]:
            conf = detection[2]
            if conf < self.confidence:
                continue

            # Scale coordinates back to original image
            x1 = int(detection[3] * orig_width)
            y1 = int(detection[4] * orig_height)
            x2 = int(detection[5] * orig_width)
            y2 = int(detection[6] * orig_height)

            # Draw bounding box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw label
            label = f"person {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(annotated, (x1, y1 - label_size[1] - 10), (x1 + label_size[0], y1), (0, 255, 0), -1)
            cv2.putText(annotated, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        return annotated

    def detect_raw(self, frame: np.ndarray) -> list:
        """
        Run detection and return raw results.

        Args:
            frame: BGR image as numpy array

        Returns:
            List of detections
        """
        orig_height, orig_width = frame.shape[:2]

        # Preprocess
        resized = cv2.resize(frame, (self.input_width, self.input_height))
        input_data = resized.transpose(2, 0, 1).reshape(1, 3, self.input_height, self.input_width)

        # Run inference
        results = self.compiled_model([input_data])[self.output_layer]

        detections = []
        for detection in results[0][0]:
            conf = float(detection[2])
            if conf < self.confidence:
                continue

            x1 = int(detection[3] * orig_width)
            y1 = int(detection[4] * orig_height)
            x2 = int(detection[5] * orig_width)
            y2 = int(detection[6] * orig_height)

            detections.append({
                "bbox": [x1, y1, x2, y2],
                "class_id": 0,
                "class_name": "person",
                "confidence": conf,
            })

        return detections
