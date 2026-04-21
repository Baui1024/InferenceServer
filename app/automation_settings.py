"""Global automation settings — persisted to automation_settings.json."""

import json
import os
import threading
from pathlib import Path

from loguru import logger

import app.config as config

_DEFAULTS = {
    "knx_gateway_ip": config.KNX_GATEWAY_IP,
    "knx_gateway_port": config.KNX_GATEWAY_PORT,
    "knx_connection_type": config.KNX_CONNECTION_TYPE,  # "tunneling" | "routing"
    "knx_enabled": False,
}


class AutomationSettingsStore:
    """Thread-safe store for global automation/KNX settings."""

    def __init__(self, path: str | None = None):
        self._path = Path(path or config.AUTOMATION_SETTINGS_FILE)
        self._lock = threading.Lock()
        self._settings: dict = {**_DEFAULTS}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._settings = {**_DEFAULTS, **data}
                    logger.info(f"Loaded automation settings from {self._path}")
                    return
            except Exception as e:
                logger.warning(f"Failed to load automation settings: {e}")
        logger.info("Using default automation settings")

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._settings, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    def get(self) -> dict:
        with self._lock:
            return {**self._settings}

    def update(self, data: dict) -> dict:
        with self._lock:
            for k in _DEFAULTS:
                if k in data:
                    self._settings[k] = data[k]
            self._save()
            return {**self._settings}
