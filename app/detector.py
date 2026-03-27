"""YOLO object detector for real-time inference."""

from typing import Optional

import cv2
import numpy as np
from loguru import logger
from ultralytics import YOLO


class Detector:
    """Runs YOLO inference on frames and draws bounding boxes."""

    # COCO class indices for filtering (0 = person)
    PERSON_CLASS = 0

    def __init__(
        self,
        model_name: str = "yolov8n.pt",  # nano model for speed
        confidence: float = 0.5,
        device: Optional[str] = None,  # None = auto-select (CUDA if available)
        person_only: bool = True,  # Only detect people
    ):
        """
        Initialize the detector.

        Args:
            model_name: YOLO model to use (yolov8n/s/m/l/x.pt)
            confidence: Minimum confidence threshold for detections
            device: Device to run on ('cuda', 'cpu', or None for auto)
            person_only: If True, only detect people (class 0)
        """
        self.confidence = confidence
        self.classes = [self.PERSON_CLASS] if person_only else None
        
        logger.info(f"Loading YOLO model: {model_name}")
        self.model = YOLO(model_name)
        
        # Move to GPU if available
        if device:
            self.model.to(device)
        
        # Warm up the model
        logger.info("Warming up model...")
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        self.model(dummy, verbose=False)
        
        mode = "person-only" if person_only else "all classes"
        logger.info(f"Detector ready (device={self.model.device}, mode={mode})")

    def detect(self, frame: np.ndarray) -> np.ndarray:
        """
        Run detection on a frame and return annotated frame.

        Args:
            frame: BGR image as numpy array

        Returns:
            Annotated frame with bounding boxes drawn
        """
        # Run inference
        results = self.model(
            frame,
            conf=self.confidence,
            classes=self.classes,
            verbose=False,
        )
        
        # Draw results on frame
        annotated = results[0].plot()
        
        return annotated

    def detect_raw(self, frame: np.ndarray) -> list:
        """
        Run detection and return raw results (boxes, classes, confidences).

        Args:
            frame: BGR image as numpy array

        Returns:
            List of detections, each with (bbox, class_id, class_name, confidence)
        """
        results = self.model(
            frame,
            conf=self.confidence,
            classes=self.classes,
            verbose=False,
        )
        
        detections = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy()  # x1, y1, x2, y2
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = self.model.names[cls_id]
                
                detections.append({
                    "bbox": xyxy.tolist(),
                    "class_id": cls_id,
                    "class_name": cls_name,
                    "confidence": conf,
                })
        
        return detections
