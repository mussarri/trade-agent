from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAlert(ABC):
    @abstractmethod
    async def send(self, payload: dict) -> None:
        """ENTRY_CONFIRMED alert."""
        raise NotImplementedError

    async def send_setup(self, payload: dict) -> None:
        """SETUP_DETECTED alert. No-op by default."""
        return None

    async def send_structure(self, payload: dict) -> None:
        """HTF structure-shift alert. No-op by default."""
        return None
