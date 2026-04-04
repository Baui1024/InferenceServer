"""Web server — MJPEG streams, WebSocket API, and React SPA serving."""

import asyncio
from pathlib import Path
from typing import Optional

from aiohttp import web
from loguru import logger

from app.config import RECORDINGS_DIR
from app.camera_store import CameraStore
from app.pipeline_manager import PipelineManager
from app.ws_api import WebSocketAPI

_DIST_DIR = Path(__file__).parent / "static" / "dist"
_BOUNDARY = b"--frame\r\n"
_RECORDINGS_PATH = Path(RECORDINGS_DIR)


class WebStreamServer:
    """aiohttp-based server: MJPEG per camera, WebSocket API, SPA frontend."""

    def __init__(
        self,
        store: CameraStore,
        manager: PipelineManager,
        host: str = "0.0.0.0",
        port: int = 8090,
    ):
        self.host = host
        self.port = port
        self.store = store
        self.manager = manager
        self.ws_api = WebSocketAPI(store, manager)
        self._runner: Optional[web.AppRunner] = None

    # -- HTTP handlers --

    async def _handle_stream(self, request: web.Request) -> web.StreamResponse:
        """MJPEG stream for a single camera: GET /stream/{camera_id}"""
        camera_id = request.match_info["camera_id"]

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "multipart/x-mixed-replace; boundary=frame",
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Access-Control-Allow-Origin": "*",
            },
        )
        await response.prepare(request)

        last_jpeg = None
        try:
            while not response.task.done():
                jpeg = self.manager.get_latest_jpeg(camera_id)
                if jpeg is not None and jpeg is not last_jpeg:
                    last_jpeg = jpeg
                    try:
                        await response.write(
                            _BOUNDARY
                            + b"Content-Type: image/jpeg\r\n"
                            + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                            + jpeg
                            + b"\r\n"
                        )
                    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                        break
                await asyncio.sleep(0.033)
        except (ConnectionResetError, ConnectionAbortedError, asyncio.CancelledError):
            pass

        return response

    async def _handle_snapshot(self, request: web.Request) -> web.Response:
        """Single JPEG snapshot for a camera: GET /snapshot/{camera_id}"""
        camera_id = request.match_info["camera_id"]
        jpeg = self.manager.get_latest_jpeg(camera_id)
        if jpeg is None:
            return web.Response(status=204)
        return web.Response(
            body=jpeg,
            content_type="image/jpeg",
            headers={"Cache-Control": "no-cache"},
        )

    async def _handle_spa_fallback(self, request: web.Request) -> web.Response:
        """Serve index.html for all non-API/non-asset routes (SPA routing)."""
        index = _DIST_DIR / "index.html"
        if index.exists():
            return web.FileResponse(index)
        return web.Response(text="Frontend not built. Run: cd frontend && npm run build", status=503)

    async def _handle_recording_download(self, request: web.Request) -> web.Response:
        """Serve a recording MP4 file for download: GET /recordings/{filename}"""
        filename = request.match_info["filename"]
        # Sanitize: only allow alphanumeric, dash, underscore, dot
        if not all(c.isalnum() or c in "-_." for c in filename):
            return web.Response(text="Invalid filename", status=400)
        filepath = _RECORDINGS_PATH / filename
        if not filepath.exists() or not filepath.suffix == ".mp4":
            return web.Response(text="Not found", status=404)
        # Ensure path doesn't escape recordings directory
        try:
            filepath.resolve().relative_to(_RECORDINGS_PATH.resolve())
        except ValueError:
            return web.Response(text="Forbidden", status=403)
        return web.FileResponse(
            filepath,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # -- Lifecycle --

    async def start(self) -> None:
        app = web.Application()

        # WebSocket
        app.router.add_get("/ws", self.ws_api.handle)

        # Per-camera MJPEG stream
        app.router.add_get("/stream/{camera_id}", self._handle_stream)

        # Single JPEG snapshot (used by grid thumbnails)
        app.router.add_get("/snapshot/{camera_id}", self._handle_snapshot)

        # Recording downloads
        app.router.add_get("/recordings/{filename}", self._handle_recording_download)

        # React SPA static assets
        if _DIST_DIR.exists():
            # Serve built assets (JS, CSS, images)
            assets_dir = _DIST_DIR / "assets"
            if assets_dir.exists():
                app.router.add_static("/assets/", assets_dir)
            # Serve any other static files at root of dist (favicon, etc.)
            app.router.add_get("/", self._handle_spa_fallback)
            # Catch-all for SPA client-side routing
            app.router.add_get("/{path:.*}", self._handle_spa_fallback)
        else:
            app.router.add_get("/", self._handle_spa_fallback)
            app.router.add_get("/{path:.*}", self._handle_spa_fallback)
            logger.warning(f"Frontend dist not found at {_DIST_DIR}. Run: cd frontend && npm run build")

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()

        await self.ws_api.start()
        logger.info(f"Web server at http://{self.host}:{self.port}")

    async def stop(self) -> None:
        await self.ws_api.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("Web server stopped")
