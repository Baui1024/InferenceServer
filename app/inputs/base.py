"""Abstract base class for input frame receivers."""

from abc import ABC, abstractmethod
from typing import Callable


class InputReceiver(ABC):
    """Base interface all camera input sources must implement.

    Subclasses connect to a camera device, receive JPEG frames,
    and invoke ``on_frame(jpeg_bytes)`` for each one.
    """

    def __init__(self, on_frame: Callable[[bytes], None]):
        self.on_frame = on_frame

    @abstractmethod
    async def start(self) -> None:
        """Begin receiving frames (may run until stop is called)."""

    @abstractmethod
    async def stop(self) -> None:
        """Cleanly shut down the receiver."""
