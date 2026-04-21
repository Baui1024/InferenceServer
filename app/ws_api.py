"""WebSocket API — single /ws endpoint for all client communication."""

import asyncio
import json
from typing import Optional

import aiohttp
from aiohttp import web
from loguru import logger

import app.config as config
from app.camera_store import CameraStore
from app.pipeline_manager import PipelineManager
from app.camera_hw_proxy import HWProxyManager
from app.recorder import list_recordings, get_recording, delete_recording
from app.engine_manager import (
    list_engines, delete_engine, compile_engine, COMPILABLE_MODELS,
    _gpu_info, get_engine_path, ENGINES_DIR,
)
from app.knx_manager import KNXManager
from app.automation_settings import AutomationSettingsStore
from app.trigger_executor import execute_triggers


class WebSocketAPI:
    """Handles WebSocket connections and dispatches messages."""

    def __init__(self, store: CameraStore, manager: PipelineManager):
        self.store = store
        self.manager = manager
        self._clients: set[web.WebSocketResponse] = set()
        self._stats_task: Optional[asyncio.Task] = None
        self._compile_task: Optional[asyncio.Task] = None

        # HW proxy manager — forwards camera settings to RPi
        self.hw_proxies = HWProxyManager(on_settings=self._on_hw_settings)

        # Automation / KNX
        self.automation_store = AutomationSettingsStore()
        self.knx = KNXManager()

    async def start(self) -> None:
        """Start periodic stats broadcast and KNX connection."""
        self._stats_task = asyncio.create_task(self._stats_loop())
        # Auto-connect KNX if enabled
        auto = self.automation_store.get()
        if auto.get("knx_enabled"):
            await self.knx.start(
                auto["knx_gateway_ip"],
                auto["knx_gateway_port"],
                auto["knx_connection_type"],
            )
        # Note: zone transition callbacks are wired after pipelines start (see main.py)

    async def stop(self) -> None:
        """Stop stats broadcast, HW proxies, and KNX."""
        if self._stats_task:
            self._stats_task.cancel()
            try:
                await self._stats_task
            except asyncio.CancelledError:
                pass
        await self.hw_proxies.stop_all()
        await self.knx.stop()

    # -- WebSocket handler (aiohttp route) --

    async def handle(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._clients.add(ws)
        logger.info(f"WS client connected ({len(self._clients)} total)")

        await self._send_initial_state(ws)

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

    async def _send_initial_state(self, ws: web.WebSocketResponse) -> None:
        """Send server config and camera list to a newly connected client."""
        await self._send(ws, "server_config", {
            "recording_enabled": config.RECORDING_ENABLED,
            "gpu": _gpu_info(),
            "compilable_models": COMPILABLE_MODELS,
        })
        await self._send(ws, "engines", list_engines())
        # Automation settings
        auto = self.automation_store.get()
        auto["knx"] = self.knx.get_info()
        await self._send(ws, "automation_settings", auto)

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
            # Recording
            "start_recording": self._handle_start_recording,
            "stop_recording": self._handle_stop_recording,
            "list_recordings": self._handle_list_recordings,
            "delete_recording": self._handle_delete_recording,
            "play_recording": self._handle_play_recording,
            # Playback controls
            "playback_pause": self._handle_playback_pause,
            "playback_resume": self._handle_playback_resume,
            "playback_step": self._handle_playback_step,
            "playback_step_back": self._handle_playback_step_back,
            "playback_seek": self._handle_playback_seek,
            "playback_stop": self._handle_playback_stop,
            "playback_set_range": self._handle_playback_set_range,
            # TensorRT engines
            "list_engines": self._handle_list_engines,
            "compile_engine": self._handle_compile_engine,
            "delete_engine": self._handle_delete_engine,
            # Automation
            "get_automation_settings": self._handle_get_automation,
            "update_automation_settings": self._handle_update_automation,
        }.get(msg_type)

        if handler:
            await handler(ws, data)
        else:
            await self._send(ws, "error", {"message": f"Unknown type: {msg_type}"})

    # -- Camera CRUD handlers --

    async def _handle_list(self, ws, data):
        cameras = self._cameras_with_stats()
        await self._send(ws, "cameras", cameras)

    def _cameras_with_stats(self):
        cameras = self.store.all()
        stats = self.manager.get_all_stats()
        stats_map = {s["id"]: s for s in stats}
        for cam in cameras:
            cam["stats"] = stats_map.get(cam["id"], {})
        return cameras

    async def _broadcast_cameras(self):
        await self._broadcast("cameras", self._cameras_with_stats())

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
            p = self.manager.get_pipeline(camera["id"])
            if p:
                self._set_zone_callback(p, camera.get("name", camera["id"][:8]))
        await self._broadcast_cameras()

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
                p = self.manager.get_pipeline(camera_id)
                if p:
                    self._set_zone_callback(p, camera.get("name", camera_id[:8]))
            else:
                await self.manager.stop_camera(camera_id)
        else:
            # Sync live config to the running pipeline (e.g. zones, thresholds)
            p = self.manager.get_pipeline(camera_id)
            if p:
                p.cfg.update(data)

        await self._broadcast_cameras()

    async def _handle_remove(self, ws, data):
        camera_id = data.get("id", "")
        await self.manager.stop_camera(camera_id)
        await self.hw_proxies.remove_proxy(camera_id)
        removed = self.store.remove(camera_id)
        if removed:
            await self._broadcast("camera_removed", {"id": camera_id})
            await self._broadcast_cameras()
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

    async def _broadcast_stats(self) -> None:
        """Broadcast camera stats to all clients immediately."""
        stats = self.manager.get_all_stats()
        if stats and self._clients:
            if config.RECORDING_ENABLED:
                for s in stats:
                    p = self.manager.get_pipeline(s["id"])
                    s["recording"] = p.is_recording if p else False
            await self._broadcast("camera_stats", stats)

    async def _stats_loop(self) -> None:
        """Broadcast camera stats to all clients every 2 seconds."""
        while True:
            await asyncio.sleep(2)
            await self._broadcast_stats()

    # -- Recording handlers --

    async def _handle_start_recording(self, ws, data):
        if not config.RECORDING_ENABLED:
            await self._send(ws, "error", {"message": "Recording is not enabled on this server"})
            return
        camera_id = data.get("id", "")
        pipeline = self.manager.get_pipeline(camera_id)
        if not pipeline:
            await self._send(ws, "error", {"message": "Camera pipeline not running"})
            return
        rec_id = pipeline.start_recording()
        await self._broadcast("recording_started", {"camera_id": camera_id, "recording_id": rec_id})

    async def _handle_stop_recording(self, ws, data):
        camera_id = data.get("id", "")
        pipeline = self.manager.get_pipeline(camera_id)
        if not pipeline:
            await self._send(ws, "error", {"message": "Camera pipeline not running"})
            return
        meta = pipeline.stop_recording()
        if meta:
            await self._broadcast("recording_stopped", {"camera_id": camera_id, "recording": meta})
        else:
            await self._send(ws, "error", {"message": "Camera is not recording"})

    async def _handle_list_recordings(self, ws, data):
        recordings = list_recordings()
        await self._send(ws, "recordings", recordings)

    async def _handle_delete_recording(self, ws, data):
        rec_id = data.get("id", "")
        if not rec_id:
            await self._send(ws, "error", {"message": "Missing recording id"})
            return
        deleted = delete_recording(rec_id)
        if deleted:
            await self._broadcast("recordings", list_recordings())
        else:
            await self._send(ws, "error", {"message": "Recording not found"})

    async def _handle_play_recording(self, ws, data):
        """Create a playback camera from a recording, stored like any camera."""
        rec_id = data.get("recording_id", "")
        rec = get_recording(rec_id)
        if not rec:
            await self._send(ws, "error", {"message": "Recording not found"})
            return

        # Check if we already have a playback camera for this recording
        existing = [c for c in self.store.all() if c.get("recording_id") == rec_id]
        if existing:
            # Just restart its pipeline and select it
            cam = existing[0]
            await self.manager.start_camera(cam)
            await self._broadcast("cameras", self.store.all())
            await self._broadcast("playback_started", {"camera_id": cam["id"]})
            return

        # Add as a real camera in the store so update_camera works
        camera = self.store.add({
            "name": f"\u25b6 {rec.get('camera_name', rec_id)}",
            "type": "recording",
            "recording_id": rec_id,
            "host": "",
            "port": 0,
            "enabled": True,
            "playback_fps": data.get("playback_fps", 0),
            "loop_playback": True,
            "max_fps": 30,
            "motion_detection_enabled": False,
        })

        await self.manager.start_camera(camera)
        await self._broadcast("cameras", self.store.all())
        await self._broadcast("playback_started", {"camera_id": camera["id"]})

    # -- Playback control helpers --

    def _get_recording_input(self, data):
        """Get the RecordingInput for a camera, or None."""
        cam_id = data.get("id", "")
        pipeline = self.manager.get_pipeline(cam_id)
        if not pipeline:
            return None
        return pipeline.get_recording_input()

    async def _handle_playback_pause(self, ws, data):
        ri = self._get_recording_input(data)
        if ri:
            ri.pause()
            await self._broadcast_stats()

    async def _handle_playback_resume(self, ws, data):
        ri = self._get_recording_input(data)
        if ri:
            ri.resume()
            await self._broadcast_stats()

    async def _handle_playback_step(self, ws, data):
        ri = self._get_recording_input(data)
        if ri:
            ri.step_forward()
            await self._broadcast_stats()

    async def _handle_playback_step_back(self, ws, data):
        ri = self._get_recording_input(data)
        if ri:
            ri.step_backward()
            await self._broadcast_stats()

    async def _handle_playback_seek(self, ws, data):
        ri = self._get_recording_input(data)
        if ri:
            frame = data.get("frame", 0)
            ri.seek(int(frame))
            await self._broadcast_stats()

    async def _handle_playback_stop(self, ws, data):
        ri = self._get_recording_input(data)
        if ri:
            ri.pause()
            ri.seek(ri.start_frame)
            await self._broadcast_stats()

    async def _handle_playback_set_range(self, ws, data):
        ri = self._get_recording_input(data)
        if ri:
            ri.set_range(
                start=data.get("start_frame"),
                end=data.get("end_frame"),
            )
            await self._broadcast_stats()

    # -- TensorRT engine handlers --

    async def _handle_list_engines(self, ws, data):
        await self._send(ws, "engines", list_engines())

    async def _handle_compile_engine(self, ws, data):
        model_name = data.get("model", "")
        if not model_name:
            await self._send(ws, "error", {"message": "Missing model name"})
            return

        if self._compile_task and not self._compile_task.done():
            await self._send(ws, "error", {"message": "A compilation is already in progress"})
            return

        async def _run_compile():
            try:
                loop = asyncio.get_running_loop()

                def on_progress(status: str, percent: int):
                    asyncio.run_coroutine_threadsafe(
                        self._broadcast("engine_compile_progress", {
                            "model": model_name,
                            "status": status,
                            "percent": percent,
                        }),
                        loop,
                    )

                result = await compile_engine(model_name, on_progress)
                await self._broadcast("engine_compiled", result)
                await self._broadcast("engines", list_engines())
            except (ValueError, RuntimeError) as e:
                await self._broadcast("engine_compile_error", {
                    "model": model_name,
                    "error": str(e),
                })

        self._compile_task = asyncio.create_task(_run_compile())

    async def _handle_delete_engine(self, ws, data):
        filename = data.get("filename", "")
        if not filename:
            await self._send(ws, "error", {"message": "Missing engine filename"})
            return
        deleted = delete_engine(filename)
        if deleted:
            await self._broadcast("engines", list_engines())
        else:
            await self._send(ws, "error", {"message": "Engine not found"})

    # -- Automation handlers --

    async def _handle_get_automation(self, ws, data):
        auto = self.automation_store.get()
        auto["knx"] = self.knx.get_info()
        await self._send(ws, "automation_settings", auto)

    async def _handle_update_automation(self, ws, data):
        auto = self.automation_store.update(data)
        # Reconnect / disconnect KNX based on new settings
        if auto.get("knx_enabled"):
            await self.knx.reconnect(
                auto["knx_gateway_ip"],
                auto["knx_gateway_port"],
                auto["knx_connection_type"],
            )
        else:
            await self.knx.stop()
        auto["knx"] = self.knx.get_info()
        await self._broadcast("automation_settings", auto)

    def _wire_zone_callbacks(self) -> None:
        """Wire zone transition callbacks for all existing pipelines."""
        for cid, pipeline in self.manager._pipelines.items():
            cam = self.store.get(cid)
            cam_name = cam.get("name", cid[:8]) if cam else cid[:8]
            self._set_zone_callback(pipeline, cam_name)

    def _set_zone_callback(self, pipeline, camera_name: str) -> None:
        """Set the zone transition callback on a pipeline."""
        knx = self.knx

        def on_transition(zone_cfg: dict, transition: str):
            asyncio.run_coroutine_threadsafe(
                execute_triggers(zone_cfg, transition, knx, camera_name),
                pipeline._loop,
            )
            # Push updated stats immediately so frontend reflects zone change
            asyncio.run_coroutine_threadsafe(
                self._broadcast_stats(),
                pipeline._loop,
            )

        pipeline.set_zone_transition_callback(on_transition)

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
