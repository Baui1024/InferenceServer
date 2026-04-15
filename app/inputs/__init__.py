"""Input receivers — abstract base and factory."""

from .base import InputReceiver
from .rpi_tls import RPiTLSReceiver

__all__ = ["InputReceiver", "RPiTLSReceiver"]
