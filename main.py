"""Multi-Camera Inference Server.

Manages multiple Raspberry Pi camera streams, runs per-camera
object detection pipelines, and serves a React dashboard + MJPEG streams.
"""

import asyncio
import signal
import sys

from loguru import logger

from app.config import WEB_HOST, WEB_PORT, CAMERAS_FILE, RECORDINGS_DIR
import app.config as config
from app.camera_store import CameraStore
from app.pipeline_manager import PipelineManager
from app.web_server import WebStreamServer

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="DEBUG",
)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    # --record CLI flag overrides config/env
    if "--record" in sys.argv:
        config.RECORDING_ENABLED = True

    if config.RECORDING_ENABLED:
        from pathlib import Path
        Path(RECORDINGS_DIR).mkdir(exist_ok=True)
        logger.info(f"Recording enabled — saving to {RECORDINGS_DIR}/")

    store = CameraStore(path=CAMERAS_FILE)
    manager = PipelineManager()
    server = WebStreamServer(store=store, manager=manager, host=WEB_HOST, port=WEB_PORT)

    # Start web server first (so clients can connect while pipelines init)
    await server.start()

    # Start all enabled camera pipelines
    cameras = store.all()
    logger.info(f"Starting {len(cameras)} camera pipeline(s)...")
    await manager.start_all(cameras)

    # Wire zone transition callbacks now that pipelines exist
    server.ws_api._wire_zone_callbacks()

    logger.info(f"Open http://localhost:{WEB_PORT} in your browser — Ctrl+C to quit")

    stop = asyncio.Event()

    loop = asyncio.get_event_loop()
    for sig_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig_name, stop.set)
        except NotImplementedError:
            pass  # Windows — handled via KeyboardInterrupt below

    try:
        await stop.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    logger.info("Shutting down...")
    # Stop pipelines first (kills frame-processing threads that block server cleanup)
    try:
        await asyncio.wait_for(manager.stop_all(), timeout=5.0)
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Manager stop timed out or failed: {e}")
    try:
        await asyncio.wait_for(server.stop(), timeout=5.0)
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Server stop timed out or failed: {e}")
    logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted — bye")
