"""Camera hardware settings proxy — forwards WS commands to RPi cameras."""

import asyncio
import ssl
from typing import Callable, Optional

import aiohttp
from loguru import logger


class CameraHWProxy:
    """Manages a WebSocket connection to a Raspberry Pi camera control server."""

    def __init__(self, camera_id: str, host: str, port: int,
                 on_settings: Callable[[str, dict], None],
                 use_tls: bool = False):
        """
        Args:
            camera_id: ID of the camera this proxy belongs to.
            host: RPi hostname / IP.
            port: RPi camera WS port (e.g. 8082).
            on_settings: Callback(camera_id, settings_dict) when settings arrive.
            use_tls: Connect via wss:// instead of ws://.
        """
        self.camera_id = camera_id
        self.host = host
        self.port = port
        self.use_tls = use_tls
        self._on_settings = on_settings

        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self) -> None:
        """Open WebSocket to the camera and start listening."""
        self._running = True
        self._session = aiohttp.ClientSession()
        self._task = asyncio.create_task(self._listen_loop())

    async def disconnect(self) -> None:
        """Close WebSocket and session."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
            self._session = None

    async def send_get(self) -> None:
        """Request current camera settings."""
        await self._send({"type": "get"})

    async def send_set(self, settings: dict) -> None:
        """Send updated settings to the camera."""
        await self._send({"type": "set", "data": settings})

    async def send_reset(self) -> None:
        """Reset camera to default settings."""
        await self._send({"type": "reset"})

    async def _send(self, msg: dict) -> None:
        if self._ws and not self._ws.closed:
            await self._ws.send_json(msg)

    async def _listen_loop(self) -> None:
        """Connect and listen, with auto-reconnect."""
        scheme = "wss" if self.use_tls else "ws"
        url = f"{scheme}://{self.host}:{self.port}"
        ssl_ctx: Optional[ssl.SSLContext] = None
        if self.use_tls:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        delay = 1.0
        while self._running:
            try:
                logger.debug(f"HW proxy connecting to {url}")
                self._ws = await self._session.ws_connect(url, ssl=ssl_ctx)  # type: ignore[union-attr]
                delay = 1.0
                logger.info(f"HW proxy connected to {url}")

                async for msg in self._ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            data = msg.json()
                            if data.get("type") == "settings" and "data" in data:
                                self._on_settings(self.camera_id, data["data"])
                        except Exception:
                            pass
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break

            except (aiohttp.ClientError, OSError, asyncio.TimeoutError) as e:
                logger.warning(f"HW proxy {url}: {e}")
            except asyncio.CancelledError:
                return

            if self._running:
                logger.debug(f"HW proxy reconnecting in {delay:.0f}s...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 16.0)


class HWProxyManager:
    """Manages CameraHWProxy instances for all RPi cameras."""

    def __init__(self, on_settings: Callable[[str, dict], None]):
        self._proxies: dict[str, CameraHWProxy] = {}
        self._on_settings = on_settings

    async def ensure_proxy(self, camera_id: str, host: str, port: int,
                           use_tls: bool = False) -> CameraHWProxy:
        """Get or create a proxy for a camera."""
        if camera_id in self._proxies:
            return self._proxies[camera_id]
        proxy = CameraHWProxy(camera_id, host, port, self._on_settings, use_tls=use_tls)
        self._proxies[camera_id] = proxy
        await proxy.connect()
        return proxy

    async def remove_proxy(self, camera_id: str) -> None:
        proxy = self._proxies.pop(camera_id, None)
        if proxy:
            await proxy.disconnect()

    async def stop_all(self) -> None:
        for cid in list(self._proxies.keys()):
            await self.remove_proxy(cid)

    def get_proxy(self, camera_id: str) -> Optional[CameraHWProxy]:
        return self._proxies.get(camera_id)
