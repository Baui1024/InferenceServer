"""Singleton KNX/IP connection manager using xknx."""

import asyncio
from typing import Optional

from loguru import logger

try:
    from xknx import XKNX
    from xknx.io import ConnectionConfig, ConnectionType
    from xknx.core.value_reader import ValueReader
    from xknx.dpt import DPTBinary, DPTArray
    from xknx.telegram import GroupAddress, Telegram
    from xknx.telegram.apci import GroupValueWrite
    HAS_XKNX = True
except ImportError:
    HAS_XKNX = False


class KNXManager:
    """Manages a single xknx connection shared by all cameras."""

    def __init__(self):
        self._xknx: Optional["XKNX"] = None
        self._status: str = "disconnected"  # disconnected | connecting | connected | error
        self._error: Optional[str] = None
        self._lock = asyncio.Lock()

    @property
    def status(self) -> str:
        return self._status

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def connected(self) -> bool:
        return self._status == "connected"

    def get_info(self) -> dict:
        return {
            "status": self._status,
            "error": self._error,
            "available": HAS_XKNX,
        }

    async def start(self, gateway_ip: str, gateway_port: int, connection_type: str) -> None:
        """Open the KNX/IP connection."""
        if not HAS_XKNX:
            self._status = "error"
            self._error = "xknx library not installed"
            logger.error("xknx not installed — KNX support disabled")
            return

        async with self._lock:
            await self._disconnect()

            self._status = "connecting"
            self._error = None
            try:
                if connection_type == "routing":
                    conn_config = ConnectionConfig(
                        connection_type=ConnectionType.ROUTING,
                        local_ip=gateway_ip,
                    )
                else:
                    conn_config = ConnectionConfig(
                        connection_type=ConnectionType.TUNNELING,
                        gateway_ip=gateway_ip,
                        gateway_port=gateway_port,
                    )

                self._xknx = XKNX(connection_config=conn_config)
                await self._xknx.start()
                self._status = "connected"
                logger.info(f"KNX connected ({connection_type}) to {gateway_ip}:{gateway_port}")
            except Exception as e:
                self._status = "error"
                self._error = str(e)
                self._xknx = None
                logger.error(f"KNX connection failed: {e}")

    async def stop(self) -> None:
        async with self._lock:
            await self._disconnect()

    async def _disconnect(self) -> None:
        if self._xknx:
            try:
                await self._xknx.stop()
            except Exception as e:
                logger.warning(f"Error stopping xknx: {e}")
            self._xknx = None
        self._status = "disconnected"
        self._error = None

    async def reconnect(self, gateway_ip: str, gateway_port: int, connection_type: str) -> None:
        """Reconnect with new settings."""
        await self.start(gateway_ip, gateway_port, connection_type)

    async def send(self, group_address: str, dpt: str, value: int) -> bool:
        """Send a KNX telegram.

        Args:
            group_address: e.g. "1/2/3"
            dpt: "boolean" or "1byte"
            value: 0/1 for boolean, 0-255 for 1byte

        Returns:
            True if sent successfully.
        """
        if not self._xknx or self._status != "connected":
            logger.warning(f"KNX not connected — cannot send to {group_address}")
            return False

        try:
            if dpt == "boolean":
                payload = DPTBinary(value)
            else:  # 1byte
                payload = DPTArray(value & 0xFF)

            telegram = Telegram(
                destination_address=GroupAddress(group_address),
                payload=GroupValueWrite(payload),
            )
            await self._xknx.telegrams.put(telegram)
            logger.debug(f"KNX sent: {group_address} = {value} (dpt={dpt})")
            return True
        except Exception as e:
            logger.error(f"KNX send failed ({group_address}): {e}")
            return False
