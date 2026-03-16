from __future__ import annotations

from abc import ABC, abstractmethod


class BaseAlert(ABC):
    @abstractmethod
    async def send(self, payload: dict) -> None:
        """Full signal alert — passed score + R:R filters."""
        raise NotImplementedError

    async def send_setup(self, payload: dict) -> None:
        """Stage 1 alert: setup detected, watching zone. No-op by default."""

    async def send_trigger(self, payload: dict) -> None:
        """Stage 2 alert: trigger fired (before score/R:R filter). No-op by default."""

    async def send_tp_hit(self, payload: dict) -> None:
        """TP level hit alert (tp1_hit / tp2_hit / tp3_hit). No-op by default."""

    async def send_stop_hit(self, payload: dict) -> None:
        """Stop loss hit alert. No-op by default."""

    async def send_invalidation(self, payload: dict) -> None:
        """Signal invalidated alert. No-op by default."""
