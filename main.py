"""Multi-Camera Inference Server.

Manages multiple camera streams (ESP32 / Raspberry Pi), runs per-camera
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
    level="INFO",
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

    logger.info(f"Open http://localhost:{WEB_PORT} in your browser — Ctrl+C to quit")

    stop = asyncio.Event()

    loop = asyncio.get_event_loop()
    for sig_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig_name, stop.set)
        except NotImplementedError:
            pass  # Windows

    try:
        await stop.wait()
    except KeyboardInterrupt:
        pass

    logger.info("Shutting down...")
    await manager.stop_all()
    await server.stop()
    logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
