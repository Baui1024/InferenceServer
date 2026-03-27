"""MJPEG-over-HTTP server for streaming annotated frames to web browsers."""

import asyncio
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from aiohttp import web
from loguru import logger

_STATIC_DIR = Path(__file__).parent / "static"
_BOUNDARY = b"--frame\r\n"


class WebStreamServer:
    """Serves an MJPEG stream and static frontend over HTTP."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8090, jpeg_quality: int = 80):
        self.host = host
        self.port = port
        self.jpeg_quality = jpeg_quality

        self._frame: Optional[np.ndarray] = None
        self._jpeg: Optional[bytes] = None
        self._lock = threading.Lock()
        self._event = asyncio.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._frame_count = 0
        self._fps = 0.0
        self._fps_frame_count = 0
        self._last_fps_time = time.time()
        self._motion_change = 0.0
        self._running = False

        self._runner: Optional[web.AppRunner] = None

    # -- Public API (called from pipeline thread) --

    def push_array(self, frame: np.ndarray, motion_change: float = 0.0) -> None:
        """Push a BGR frame for streaming. Thread-safe."""
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality])
        jpeg = buf.tobytes()

        with self._lock:
            self._frame = frame
            self._jpeg = jpeg
            self._motion_change = motion_change
            self._frame_count += 1
            self._fps_frame_count += 1

            now = time.time()
            elapsed = now - self._last_fps_time
            if elapsed >= 1.0:
                self._fps = self._fps_frame_count / elapsed
                self._fps_frame_count = 0
                self._last_fps_time = now

        # Signal waiting stream handlers
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._event.set)

    @property
    def fps(self) -> float:
        with self._lock:
            return self._fps

    # -- HTTP handlers --

    async def _handle_index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(_STATIC_DIR / "index.html")

    async def _handle_stream(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "multipart/x-mixed-replace; boundary=frame",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Access-Control-Allow-Origin": "*",
            },
        )
        await response.prepare(request)

        last_count = 0
        try:
            while True:
                self._event.clear()
                with self._lock:
                    jpeg = self._jpeg
                    count = self._frame_count

                if jpeg is not None and count != last_count:
                    last_count = count
                    await response.write(
                        _BOUNDARY
                        + b"Content-Type: image/jpeg\r\n"
                        + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                        + jpeg
                        + b"\r\n"
                    )

                try:
                    await asyncio.wait_for(self._event.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
        except (ConnectionResetError, ConnectionAbortedError, asyncio.CancelledError):
            pass

        return response

    # -- Lifecycle --

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._running = True

        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/stream", self._handle_stream)
        app.router.add_static("/static/", _STATIC_DIR)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"Web stream server at http://{self.host}:{self.port}")

    async def stop(self) -> None:
        self._running = False
        if self._runner:
            await self._runner.cleanup()
        logger.info("Web stream server stopped")
