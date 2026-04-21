"""Recording playback input — reads frames from a recorded MP4 file."""

import asyncio
from pathlib import Path
from typing import Callable, Optional

import cv2
from loguru import logger

from .base import InputReceiver
from app.config import RECORDINGS_DIR


class RecordingInput(InputReceiver):
    """Reads frames from a recorded video file and fires them via on_frame.

    The frames are JPEG-encoded before being passed to on_frame to match
    the interface of live camera inputs.

    Supports pause/resume, frame stepping, and seeking.
    """

    def __init__(
        self,
        on_frame: Callable[[bytes], None],
        recording_id: str,
        playback_fps: float = 0,
        loop_playback: bool = False,
    ):
        super().__init__(on_frame)
        self.recording_id = recording_id
        self.playback_fps = playback_fps  # 0 = use file's native fps
        self.loop_playback = loop_playback

        self._video_path = Path(RECORDINGS_DIR) / f"{recording_id}.mp4"
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # Playback state
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused initially
        self._step_event = asyncio.Event()
        self._seek_frame: Optional[int] = None

        # Metadata (populated on start)
        self.total_frames: int = 0
        self.native_fps: float = 15.0
        self.current_frame: int = 0
        self.duration_sec: float = 0.0

        # Range limits
        self.start_frame: int = 0
        self.end_frame: int = 0  # 0 = use total_frames

    async def start(self) -> None:
        if not self._video_path.exists():
            raise FileNotFoundError(f"Recording not found: {self._video_path}")

        # Read metadata
        cap = cv2.VideoCapture(str(self._video_path))
        if cap.isOpened():
            self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.native_fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
            self.duration_sec = self.total_frames / self.native_fps if self.native_fps > 0 else 0
            self.end_frame = self.total_frames
            cap.release()

        # Load persisted range from recording JSON
        self._load_persisted_range()

        self._running = True
        self._paused = False
        self._pause_event.set()
        self._task = asyncio.create_task(self._playback_loop())
        logger.info(f"RecordingInput started: {self.recording_id} ({self.total_frames} frames, {self.native_fps:.1f} fps)")

    async def stop(self) -> None:
        self._running = False
        self._pause_event.set()  # unblock if paused
        self._step_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"RecordingInput stopped: {self.recording_id}")

    def pause(self) -> None:
        """Pause playback."""
        self._paused = True
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume playback."""
        self._paused = False
        self._pause_event.set()

    def step_forward(self) -> None:
        """Advance one frame while paused."""
        if self._paused:
            self._step_event.set()

    def step_backward(self) -> None:
        """Go back one frame while paused.

        current_frame points to the *next* frame to read (last displayed + 1),
        so we seek to current_frame - 2 to display the previous frame.
        """
        if self._paused and self.current_frame > self.start_frame + 1:
            self._seek_frame = max(self.start_frame, self.current_frame - 2)
            self._step_event.set()

    def seek(self, frame_num: int) -> None:
        """Seek to a specific frame number."""
        self._seek_frame = max(self.start_frame, min(frame_num, self.end_frame - 1))
        # If paused, trigger a step so the seek frame gets displayed
        if self._paused:
            self._step_event.set()

    def set_range(self, start: Optional[int] = None, end: Optional[int] = None) -> None:
        """Set start/end frame range for playback and persist to recording JSON."""
        if start is not None:
            self.start_frame = max(0, min(start, self.total_frames - 1))
        if end is not None:
            self.end_frame = max(self.start_frame + 1, min(end, self.total_frames))
        self._persist_range()

    def _persist_range(self) -> None:
        """Save start/end frame to the recording's JSON metadata."""
        import json
        meta_path = Path(RECORDINGS_DIR) / f"{self.recording_id}.json"
        if not meta_path.exists():
            return
        try:
            meta = json.loads(meta_path.read_text())
            meta["playback_start_frame"] = self.start_frame
            meta["playback_end_frame"] = self.end_frame
            meta_path.write_text(json.dumps(meta, indent=2))
        except Exception as e:
            logger.warning(f"Failed to persist playback range: {e}")

    def _load_persisted_range(self) -> None:
        """Load start/end frame from the recording's JSON metadata."""
        import json
        meta_path = Path(RECORDINGS_DIR) / f"{self.recording_id}.json"
        if not meta_path.exists():
            return
        try:
            meta = json.loads(meta_path.read_text())
            if "playback_start_frame" in meta:
                self.start_frame = max(0, min(int(meta["playback_start_frame"]), self.total_frames - 1))
            if "playback_end_frame" in meta:
                self.end_frame = max(self.start_frame + 1, min(int(meta["playback_end_frame"]), self.total_frames))
        except Exception as e:
            logger.warning(f"Failed to load playback range: {e}")

    def get_playback_info(self) -> dict:
        """Return current playback state."""
        return {
            "current_frame": self.current_frame,
            "total_frames": self.total_frames,
            "duration_sec": round(self.duration_sec, 2),
            "native_fps": round(self.native_fps, 1),
            "paused": self._paused,
            "start_frame": self.start_frame,
            "end_frame": self.end_frame,
        }

    async def _playback_loop(self) -> None:
        loop = asyncio.get_event_loop()

        while self._running:
            cap = cv2.VideoCapture(str(self._video_path))
            if not cap.isOpened():
                logger.error(f"Cannot open recording: {self._video_path}")
                return

            fps = self.playback_fps if self.playback_fps > 0 else self.native_fps
            interval = 1.0 / fps

            # Seek to start_frame
            if self.start_frame > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, self.start_frame)

            self.current_frame = self.start_frame

            try:
                while self._running:
                    # Handle seek requests
                    if self._seek_frame is not None:
                        target = self._seek_frame
                        self._seek_frame = None
                        cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                        self.current_frame = target

                    # Check end boundary
                    if self.current_frame >= self.end_frame:
                        break

                    # Wait if paused (unless stepping)
                    if self._paused:
                        # Wait for either resume or step
                        while self._paused and self._running and self._seek_frame is None:
                            self._step_event.clear()
                            try:
                                await asyncio.wait_for(self._step_event.wait(), timeout=0.1)
                                break  # step triggered
                            except asyncio.TimeoutError:
                                continue
                        if not self._running:
                            break
                        # Handle seek that came in while waiting (e.g. step_backward)
                        if self._seek_frame is not None:
                            target = self._seek_frame
                            self._seek_frame = None
                            cap.set(cv2.CAP_PROP_POS_FRAMES, target)
                            self.current_frame = target

                    ret, frame = await loop.run_in_executor(None, cap.read)
                    if not ret:
                        break

                    def _encode_and_fire(f):
                        _, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 95])
                        self.on_frame(buf.tobytes())

                    await loop.run_in_executor(None, _encode_and_fire, frame)

                    self.current_frame += 1

                    if not self._paused:
                        await asyncio.sleep(interval)
            finally:
                cap.release()

            if not self.loop_playback:
                logger.info(f"Recording playback finished: {self.recording_id} ({self.current_frame} frames)")
                break

            # When looping, respect start_frame
            logger.info(f"Recording playback looping: {self.recording_id}")
