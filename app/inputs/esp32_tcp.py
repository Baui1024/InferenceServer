"""ESP32 input — plain TCP, length-prefixed JPEG frames.

Protocol: [4-byte big-endian uint32 length][JPEG payload]

The ESP32 runs a TCP *server*; this receiver connects as a *client*.
No encryption — the ESP32-S3 lacks the resources to handle TLS at
usable frame rates.
"""

import asyncio
import struct
from typing import Callable, Optional

from loguru import logger

from .base import InputReceiver


class ESP32TCPReceiver(InputReceiver):
    """Connects to an ESP32 camera TCP server and receives JPEG frames."""

    def __init__(
        self,
        on_frame: Callable[[bytes], None],
        host: str = "192.168.178.245",
        port: int = 8081,
        reconnect_delay: float = 2.0,
    ):
        super().__init__(on_frame)
        self.host = host
        self.port = port
        self.reconnect_delay = reconnect_delay
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._receive_loop())
        logger.info(f"ESP32TCPReceiver connecting to {self.host}:{self.port}")

    async def stop(self) -> None:
        self._running = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("ESP32TCPReceiver stopped")

    async def _receive_loop(self) -> None:
        while self._running:
            try:
                logger.info(f"Connecting to ESP32 at {self.host}:{self.port}...")
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=10.0,
                )
                logger.info(f"Connected to ESP32 at {self.host}:{self.port}")

                frame_count = 0
                while self._running:
                    header = await self._reader.readexactly(4)
                    frame_len = struct.unpack(">I", header)[0]

                    if frame_len > 5 * 1024 * 1024:
                        logger.error(f"Invalid frame length: {frame_len}")
                        break

                    jpeg_data = await self._reader.readexactly(frame_len)
                    frame_count += 1
                    if frame_count <= 5 or frame_count % 100 == 0:
                        logger.info(f"ESP32 frame #{frame_count}: {len(jpeg_data)} bytes")

                    self.on_frame(jpeg_data)

            except asyncio.TimeoutError:
                logger.warning(f"Connection timeout to {self.host}:{self.port}")
            except asyncio.IncompleteReadError as e:
                logger.warning(f"ESP32 disconnected (incomplete read: {len(e.partial)} bytes)")
            except ConnectionRefusedError:
                logger.warning(f"Connection refused by {self.host}:{self.port}")
            except OSError as e:
                logger.warning(f"Connection error: {e}")
            except Exception as e:
                logger.error(f"ESP32 TCP error: {type(e).__name__}: {e}")
            finally:
                if self._writer:
                    try:
                        self._writer.close()
                    except Exception:
                        pass
                    self._writer = None
                    self._reader = None

            if self._running:
                logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
