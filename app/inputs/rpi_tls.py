"""Raspberry Pi input — TLS-encrypted TCP, length-prefixed JPEG frames.

Protocol: same as ESP32 ([4-byte BE length][JPEG]) but wrapped in TLS.

The Pi runs a TLS *server* (PiCamStream); this receiver connects as a
TLS *client*, verifying the server certificate and optionally presenting
a client certificate (mTLS).
"""

import asyncio
import ssl
import struct
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from .base import InputReceiver


class RPiTLSReceiver(InputReceiver):
    """Connects to a Raspberry Pi camera TLS server and receives JPEG frames."""

    def __init__(
        self,
        on_frame: Callable[[bytes], None],
        host: str = "192.168.178.100",
        port: int = 8081,
        reconnect_delay: float = 2.0,
        # TLS settings
        use_tls: bool = True,
        ca_cert: Optional[str] = None,
        client_cert: Optional[str] = None,
        client_key: Optional[str] = None,
        verify_hostname: bool = False,
    ):
        """
        Args:
            on_frame: Callback receiving raw JPEG bytes per frame.
            host: Pi IP address.
            port: Pi stream port.
            reconnect_delay: Seconds between reconnect attempts.
            ca_cert: Path to CA cert (or the Pi's self-signed cert) for
                     server verification. If None, verification is disabled
                     (development only).
            client_cert: Path to client certificate PEM (for mTLS).
            client_key: Path to client private key PEM (for mTLS).
            verify_hostname: Whether to check the cert CN against *host*.
        """
        super().__init__(on_frame)
        self.host = host
        self.port = port
        self.reconnect_delay = reconnect_delay
        self.use_tls = use_tls
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.client_key = client_key
        self.verify_hostname = verify_hostname
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._receive_loop())
        mode = "TLS" if self.use_tls else "plain TCP"
        logger.info(f"RPiTLSReceiver connecting to {self.host}:{self.port} ({mode})")

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
        logger.info("RPiTLSReceiver stopped")

    # ------------------------------------------------------------------

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Build a client-side TLS context."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        if self.ca_cert and Path(self.ca_cert).exists():
            ctx.load_verify_locations(cafile=self.ca_cert)
            logger.info(f"TLS: loaded CA cert {self.ca_cert}")
        else:
            # Development: trust any server cert
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            logger.warning("TLS: server certificate verification DISABLED (dev mode)")

        if not self.verify_hostname:
            ctx.check_hostname = False

        # mTLS: present client certificate to the Pi
        if self.client_cert and self.client_key:
            ctx.load_cert_chain(
                certfile=self.client_cert,
                keyfile=self.client_key,
            )
            logger.info("TLS: mTLS enabled — presenting client certificate")

        return ctx

    async def _receive_loop(self) -> None:
        ssl_ctx = self._build_ssl_context() if self.use_tls else None

        while self._running:
            try:
                mode = "TLS" if self.use_tls else "plain TCP"
                logger.info(f"Connecting ({mode}) to RPi at {self.host}:{self.port}...")
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        self.host, self.port, ssl=ssl_ctx,
                    ),
                    timeout=10.0,
                )
                logger.info(f"{mode} session established with {self.host}:{self.port}")

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
                        logger.info(f"RPi frame #{frame_count}: {len(jpeg_data)} bytes")

                    self.on_frame(jpeg_data)

            except asyncio.TimeoutError:
                logger.warning(f"TLS connection timeout to {self.host}:{self.port}")
            except asyncio.IncompleteReadError as e:
                logger.warning(f"RPi disconnected (incomplete read: {len(e.partial)} bytes)")
            except ssl.SSLError as e:
                logger.error(f"TLS handshake failed: {e}")
            except ConnectionRefusedError:
                logger.warning(f"Connection refused by {self.host}:{self.port}")
            except OSError as e:
                logger.warning(f"Connection error: {e}")
            except Exception as e:
                logger.error(f"RPi TLS error: {type(e).__name__}: {e}")
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
