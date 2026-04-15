"""Raspberry Pi input — TLS-encrypted TCP, length-prefixed H264/MJPEG frames.

Protocol: [4-byte BE length][H264 NAL unit(s) or JPEG data] wrapped in TLS.

The Pi runs a TLS *server* (PiCamStream); this receiver connects as a
TLS *client*, verifying the server certificate and optionally presenting
a client certificate (mTLS).
"""

import asyncio
import ssl
import struct
from pathlib import Path
from typing import Callable, Optional

import av
import cv2
import numpy as np
from loguru import logger

from .base import InputReceiver


class RPiTLSReceiver(InputReceiver):
    """Connects to a Raspberry Pi camera TLS server and receives H264/MJPEG frames."""

    def __init__(
        self,
        on_frame: Callable[[np.ndarray], None],
        host: str = "192.168.178.100",
        port: int = 8081,
        reconnect_delay: float = 2.0,
        # TLS settings
        use_tls: bool = True,
        ca_cert: Optional[str] = None,
        client_cert: Optional[str] = None,
        client_key: Optional[str] = None,
        verify_hostname: bool = False,
        # Encoding format
        encode_format: str = "mjpeg",  # "h264" or "mjpeg"
    ):
        """
        Args:
            on_frame: Callback receiving decoded BGR numpy array per frame.
            host: Pi IP address.
            port: Pi stream port.
            reconnect_delay: Seconds between reconnect attempts.
            ca_cert: Path to CA cert (or the Pi's self-signed cert) for
                     server verification. If None, verification is disabled
                     (development only).
            client_cert: Path to client certificate PEM (for mTLS).
            client_key: Path to client private key PEM (for mTLS).
            verify_hostname: Whether to check the cert CN against *host*.
            encode_format: Stream encoding - "h264" or "mjpeg".
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
        self.encode_format = encode_format.lower()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._codec: Optional[av.CodecContext] = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._receive_loop())
        mode = "TLS" if self.use_tls else "plain TCP"
        logger.info(f"RPiTLSReceiver connecting to {self.host}:{self.port} ({mode}, {self.encode_format})")

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

                # Create codec context for H.264 (not needed for MJPEG)
                if self.encode_format == "h264":
                    self._codec = av.CodecContext.create('h264', 'r')
                    logger.info("H264 codec context initialized")
                    waiting_for_keyframe = True  # Wait for IDR before decoding
                else:
                    logger.info("MJPEG mode - using cv2.imdecode")
                    waiting_for_keyframe = False

                frame_count = 0
                decode_errors = 0
                while self._running:
                    header = await self._reader.readexactly(4)
                    frame_len = struct.unpack(">I", header)[0]

                    if frame_len > 5 * 1024 * 1024:
                        logger.error(f"Invalid frame length: {frame_len}")
                        break

                    frame_data = await self._reader.readexactly(frame_len)

                    # Decode based on format
                    if self.encode_format == "h264":
                        # Check for keyframe (IDR NAL unit)
                        is_keyframe = self._is_h264_keyframe(frame_data)
                        
                        if waiting_for_keyframe:
                            if is_keyframe:
                                logger.info(f"H264: Got keyframe ({frame_len} bytes), starting decode")
                                waiting_for_keyframe = False
                            else:
                                # Skip non-keyframes until we sync
                                continue
                        
                        try:
                            # Parse and decode H264 data
                            packets = self._codec.parse(frame_data)
                            for packet in packets:
                                for frame in self._codec.decode(packet):
                                    numpy_frame = frame.to_ndarray(format='bgr24')
                                    frame_count += 1
                                    decode_errors = 0  # Reset error counter on success
                                    if frame_count <= 5 or frame_count % 100 == 0:
                                        logger.info(f"RPi H264 frame #{frame_count}: {numpy_frame.shape}")
                                    self.on_frame(numpy_frame)
                        except av.error.InvalidDataError as e:
                            decode_errors += 1
                            if decode_errors <= 3:
                                logger.warning(f"H264 decode error ({decode_errors}): {e}")
                            if decode_errors > 10:
                                # Too many errors, reset codec and wait for keyframe
                                logger.warning("H264: Too many errors, resetting codec")
                                self._codec = av.CodecContext.create('h264', 'r')
                                waiting_for_keyframe = True
                                decode_errors = 0
                    else:
                        # Decode MJPEG (JPEG) data
                        numpy_frame = cv2.imdecode(
                            np.frombuffer(frame_data, dtype=np.uint8),
                            cv2.IMREAD_COLOR
                        )
                        if numpy_frame is not None:
                            frame_count += 1
                            if frame_count <= 5 or frame_count % 100 == 0:
                                logger.info(f"RPi MJPEG frame #{frame_count}: {numpy_frame.shape}")
                            self.on_frame(numpy_frame)
                        else:
                            logger.warning(f"Failed to decode JPEG frame ({frame_len} bytes)")

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
                self._codec = None
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

    @staticmethod
    def _is_h264_keyframe(data: bytes) -> bool:
        """Check if H.264 NAL unit is a keyframe (IDR slice or SPS)."""
        # Look for NAL start codes and check NAL type
        # NAL type 5 = IDR (keyframe), type 7 = SPS (also indicates keyframe AU)
        i = 0
        while i < len(data) - 4:
            if data[i:i+3] == b'\x00\x00\x01':
                nal_type = data[i+3] & 0x1F
                if nal_type in (5, 7):  # IDR or SPS
                    return True
                i += 3
            elif data[i:i+4] == b'\x00\x00\x00\x01':
                if i + 4 < len(data):
                    nal_type = data[i+4] & 0x1F
                    if nal_type in (5, 7):  # IDR or SPS
                        return True
                i += 4
            else:
                i += 1
        return False
