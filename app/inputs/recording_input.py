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

    async def start(self) -> None:
        if not self._video_path.exists():
            raise FileNotFoundError(f"Recording not found: {self._video_path}")
        self._running = True
        self._task = asyncio.create_task(self._playback_loop())
        logger.info(f"RecordingInput started: {self.recording_id}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info(f"RecordingInput stopped: {self.recording_id}")

    async def _playback_loop(self) -> None:
        loop = asyncio.get_event_loop()

        while self._running:
            cap = cv2.VideoCapture(str(self._video_path))
            if not cap.isOpened():
                logger.error(f"Cannot open recording: {self._video_path}")
                return

            native_fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
            fps = self.playback_fps if self.playback_fps > 0 else native_fps
            interval = 1.0 / fps

            frame_num = 0
            try:
                while self._running:
                    ret, frame = await loop.run_in_executor(None, cap.read)
                    if not ret:
                        break  # end of file

                    # Encode to JPEG to match live-camera interface
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    jpeg_data = buf.tobytes()
                    self.on_frame(jpeg_data)

                    frame_num += 1
                    await asyncio.sleep(interval)
            finally:
                cap.release()

            if not self.loop_playback:
                logger.info(f"Recording playback finished: {self.recording_id} ({frame_num} frames)")
                break

            logger.info(f"Recording playback looping: {self.recording_id}")
