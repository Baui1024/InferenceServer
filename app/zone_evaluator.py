"""Zone evaluator — checks detection bounding boxes against polygon zones."""

import time
from dataclasses import dataclass, field

import cv2
import numpy as np
from loguru import logger


@dataclass
class ZoneState:
    """Per-zone state machine with attack/hold timing."""
    zone_id: str
    active: bool = False
    # Attack: count frames with detections within a rolling window
    _hit_timestamps: list[float] = field(default_factory=list)
    # Hold: time of last detection hit
    _last_hit_time: float = 0.0

    def update(self, has_detection: bool, attack_frames: int, hold_time_s: float, now: float | None = None) -> tuple[bool, str | None]:
        """Update state and return (is_active, transition).

        Args:
            has_detection: Whether any detection bbox matched the zone this frame.
            attack_frames: Number of detection frames per second required to trigger.
            hold_time_s: Seconds to hold active after last detection.
            now: Current timestamp (defaults to time.time()).

        Returns:
            (active, transition) where transition is "on", "off", or None.
        """
        if now is None:
            now = time.time()

        was_active = self.active

        if has_detection:
            self._last_hit_time = now
            self._hit_timestamps.append(now)

        # Prune hits older than 1 second
        cutoff = now - 1.0
        self._hit_timestamps = [t for t in self._hit_timestamps if t > cutoff]

        hits_per_sec = len(self._hit_timestamps)

        if not self.active:
            # Activate if we meet the attack threshold
            if hits_per_sec >= attack_frames:
                self.active = True
        else:
            # Deactivate if hold time expired since last hit
            if now - self._last_hit_time > hold_time_s:
                self.active = False

        transition = None
        if self.active and not was_active:
            transition = "on"
        elif not self.active and was_active:
            transition = "off"

        return self.active, transition


def _bbox_polygon(bbox: list[float]) -> np.ndarray:
    """Convert [x1, y1, x2, y2] to 4-corner polygon array."""
    x1, y1, x2, y2 = bbox
    return np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]], dtype=np.float32)


def _check_intersect(bbox: list[float], zone_poly: np.ndarray) -> bool:
    """Check if a detection bbox intersects with a zone polygon.

    Uses cv2.intersectConvexConvex for convex polygons, falls back to
    point-in-polygon test for concave zones.
    """
    bbox_poly = _bbox_polygon(bbox)

    # Try convex intersection first (works for convex zone polygons)
    try:
        ret, _ = cv2.intersectConvexConvex(bbox_poly, zone_poly)
        if ret > 0:
            return True
    except cv2.error:
        pass

    # Fallback: check if any bbox corner is inside zone, or any zone corner inside bbox
    for pt in bbox_poly:
        if cv2.pointPolygonTest(zone_poly, (float(pt[0]), float(pt[1])), False) >= 0:
            return True
    for pt in zone_poly:
        x, y = float(pt[0]), float(pt[1])
        x1, y1, x2, y2 = bbox
        if x1 <= x <= x2 and y1 <= y <= y2:
            return True

    return False


def _check_included(bbox: list[float], zone_poly: np.ndarray) -> bool:
    """Check if all 4 bbox corners are inside the zone polygon."""
    bbox_poly = _bbox_polygon(bbox)
    for pt in bbox_poly:
        if cv2.pointPolygonTest(zone_poly, (float(pt[0]), float(pt[1])), False) < 0:
            return False
    return True


class ZoneEvaluator:
    """Evaluates detections against configured zones for a single camera."""

    def __init__(self):
        self._states: dict[str, ZoneState] = {}

    def evaluate(
        self,
        zones: list[dict],
        detections: list[dict],
        frame_width: int,
        frame_height: int,
    ) -> list[dict]:
        """Evaluate all zones against current detections.

        Both zone polygons and detection bboxes are normalised to [0, 1]
        coordinate space so that the comparison is resolution-independent.
        Origin is top-left, x goes right, y goes down — matching both
        YOLO output conventions and the frontend SVG overlay.

        Args:
            zones: List of zone configs from camera settings.
            detections: List of detection dicts with "bbox" key ([x1,y1,x2,y2] in pixels).
            frame_width: Frame width in pixels (used to normalise bboxes).
            frame_height: Frame height in pixels (used to normalise bboxes).

        Returns:
            List of {zone_id, active, transition} dicts.
        """
        now = time.time()
        results = []

        # Remove states for zones that no longer exist
        active_ids = {z["id"] for z in zones if z.get("enabled", True)}
        for zid in list(self._states.keys()):
            if zid not in active_ids:
                del self._states[zid]

        # Normalise detection bboxes from pixels to 0-1
        norm_detections = []
        for det in detections:
            bbox = det.get("bbox")
            if not bbox:
                continue
            if det.get("below_threshold", False):
                continue
            x1, y1, x2, y2 = bbox
            norm_detections.append([
                x1 / frame_width,
                y1 / frame_height,
                x2 / frame_width,
                y2 / frame_height,
            ])

        for zone in zones:
            zone_id = zone["id"]
            if not zone.get("enabled", True):
                continue

            # Get or create state
            if zone_id not in self._states:
                self._states[zone_id] = ZoneState(zone_id=zone_id)
            state = self._states[zone_id]

            # Zone points are already normalised 0-1
            points = zone.get("points", [])
            if len(points) < 3:
                results.append({"zone_id": zone_id, "active": state.active, "transition": None})
                continue

            zone_poly = np.array(points, dtype=np.float32)

            mode = zone.get("mode", "intersect")
            check_fn = _check_included if mode == "included" else _check_intersect

            # Check if any detection matches this zone
            has_detection = False
            for norm_bbox in norm_detections:
                if check_fn(norm_bbox, zone_poly):
                    has_detection = True
                    break

            attack_frames = zone.get("attack_frames", 1)
            hold_time_s = zone.get("hold_time_s", 5.0)

            active, transition = state.update(has_detection, attack_frames, hold_time_s, now)
            if transition:
                logger.debug(f"Zone '{zone.get('name', zone_id)}' -> {transition}")
            results.append({"zone_id": zone_id, "active": active, "transition": transition})

        return results
