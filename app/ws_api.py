"""WebSocket API — single /ws endpoint for all client communication."""

import asyncio
import json
from typing import Optional

import aiohttp
from aiohttp import web
from loguru import logger

from app.camera_store import CameraStore
from app.pipeline_manager import PipelineManager
from app.camera_hw_proxy import HWProxyManager


class WebSocketAPI:
    """Handles WebSocket connections and dispatches messages."""

    def __init__(self, store: CameraStore, manager: PipelineManager):
        self.store = store
        self.manager = manager
        self._clients: set[web.WebSocketResponse] = set()
        self._stats_task: Optional[asyncio.Task] = None

        # HW proxy manager — forwards camera settings to RPi
        self.hw_proxies = HWProxyManager(on_settings=self._on_hw_settings)

    async def start(self) -> None:
        """Start periodic stats broadcast."""
        self._stats_task = asyncio.create_task(self._stats_loop())

    async def stop(self) -> None:
        """Stop stats broadcast and HW proxies."""
        if self._stats_task:
            self._stats_task.cancel()
            try:
                await self._stats_task
            except asyncio.CancelledError:
                pass
        await self.hw_proxies.stop_all()

    # -- WebSocket handler (aiohttp route) --

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._clients.add(ws)
        logger.info(f"WS client connected ({len(self._clients)} total)")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    await self._dispatch(ws, msg.data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
        finally:
            self._clients.discard(ws)
            logger.info(f"WS client disconnected ({len(self._clients)} total)")

        return ws

    # -- Message dispatch --

    async def _dispatch(self, ws: web.WebSocketResponse, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await self._send(ws, "error", {"message": "Invalid JSON"})
            return

        msg_type = msg.get("type", "")
        data = msg.get("data", {})

        handler = {
            "list_cameras": self._handle_list,
            "get_camera": self._handle_get,
            "add_camera": self._handle_add,
            "update_camera": self._handle_update,
            "remove_camera": self._handle_remove,
            "camera_hw_get": self._handle_hw_get,
            "camera_hw_set": self._handle_hw_set,
            "camera_hw_reset": self._handle_hw_reset,
        }.get(msg_type)

        if handler:
            await handler(ws, data)
        else:
            await self._send(ws, "error", {"message": f"Unknown type: {msg_type}"})

    # -- Camera CRUD handlers --

    async def _handle_list(self, ws, data):
        cameras = self.store.all()
        stats = self.manager.get_all_stats()
        stats_map = {s["id"]: s for s in stats}
        for cam in cameras:
            cam["stats"] = stats_map.get(cam["id"], {})
        await self._send(ws, "cameras", cameras)

    async def _handle_get(self, ws, data):
        camera = self.store.get(data.get("id", ""))
        if camera:
            stats = self.manager.get_stats(camera["id"])
            camera["stats"] = stats or {}
            await self._send(ws, "camera", camera)
        else:
            await self._send(ws, "error", {"message": "Camera not found"})

    async def _handle_add(self, ws, data):
        camera = self.store.add(data)
        if camera.get("enabled", True):
            await self.manager.start_camera(camera)
        await self._broadcast("cameras", self.store.all())

    async def _handle_update(self, ws, data):
        camera_id = data.pop("id", None)
        if not camera_id:
            await self._send(ws, "error", {"message": "Missing camera id"})
            return

        needs_restart = CameraStore.needs_pipeline_restart(data)
        camera = self.store.update(camera_id, data)
        if not camera:
            await self._send(ws, "error", {"message": "Camera not found"})
            return

        if needs_restart:
            if camera.get("enabled", True):
                await self.manager.start_camera(camera)
            else:
                await self.manager.stop_camera(camera_id)

        await self._broadcast("cameras", self.store.all())

    async def _handle_remove(self, ws, data):
        camera_id = data.get("id", "")
        await self.manager.stop_camera(camera_id)
        await self.hw_proxies.remove_proxy(camera_id)
        removed = self.store.remove(camera_id)
        if removed:
            await self._broadcast("camera_removed", {"id": camera_id})
            await self._broadcast("cameras", self.store.all())
        else:
            await self._send(ws, "error", {"message": "Camera not found"})

    # -- Camera hardware proxy handlers --

    async def _handle_hw_get(self, ws, data):
        camera_id = data.get("id", "")
        camera = self.store.get(camera_id)
        if not camera:
            await self._send(ws, "error", {"message": "Camera not found"})
            return
        if camera["type"] != "rpi":
            await self._send(ws, "error", {"message": "HW settings only supported for RPi cameras"})
            return

        proxy = await self.hw_proxies.ensure_proxy(
            camera_id, camera["host"], camera.get("camera_ws_port", 8082))
        await proxy.send_get()

    async def _handle_hw_set(self, ws, data):
        camera_id = data.get("id", "")
        settings = data.get("settings", {})
        camera = self.store.get(camera_id)
        if not camera:
            await self._send(ws, "error", {"message": "Camera not found"})
            return
        if camera["type"] != "rpi":
            await self._send(ws, "error", {"message": "HW settings only supported for RPi cameras"})
            return

        proxy = await self.hw_proxies.ensure_proxy(
            camera_id, camera["host"], camera.get("camera_ws_port", 8082))
        await proxy.send_set(settings)

    async def _handle_hw_reset(self, ws, data):
        camera_id = data.get("id", "")
        camera = self.store.get(camera_id)
        if not camera:
            await self._send(ws, "error", {"message": "Camera not found"})
            return
        if camera["type"] != "rpi":
            await self._send(ws, "error", {"message": "HW settings only supported for RPi cameras"})
            return

        proxy = await self.hw_proxies.ensure_proxy(
            camera_id, camera["host"], camera.get("camera_ws_port", 8082))
        await proxy.send_reset()

    # -- HW settings callback (from proxy) --

    def _on_hw_settings(self, camera_id: str, settings: dict) -> None:
        """Called from HWProxy when camera sends settings back."""
        asyncio.ensure_future(
            self._broadcast("camera_hw_settings", {"id": camera_id, "settings": settings})
        )

    # -- Stats broadcast loop --

    async def _stats_loop(self) -> None:
        """Broadcast camera stats to all clients every 2 seconds."""
        while True:
            await asyncio.sleep(2)
            stats = self.manager.get_all_stats()
            if stats and self._clients:
                await self._broadcast("camera_stats", stats)

    # -- Messaging helpers --

    async def _send(self, ws: web.WebSocketResponse, msg_type: str, data) -> None:
        if not ws.closed:
            await ws.send_json({"type": msg_type, "data": data})

    async def _broadcast(self, msg_type: str, data) -> None:
        payload = json.dumps({"type": msg_type, "data": data})
        closed = []
        for ws in self._clients:
            if ws.closed:
                closed.append(ws)
            else:
                try:
                    await ws.send_str(payload)
                except Exception:
                    closed.append(ws)
        for ws in closed:
            self._clients.discard(ws)
