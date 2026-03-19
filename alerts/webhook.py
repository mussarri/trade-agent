from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time

import httpx

from alerts.base import BaseAlert

logger = logging.getLogger(__name__)


class WebhookAlert(BaseAlert):
    def __init__(self, url: str, secret: str = ""):
        self.url = url
        self.secret = secret

    async def send(self, payload: dict) -> None:
        headers = {"Content-Type": "application/json"}
        body = json.dumps(payload, default=str)
        if self.secret:
            ts = str(int(time.time()))
            sig = hmac.new(self.secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest()
            headers["X-Webhook-Timestamp"] = ts
            headers["X-Webhook-Signature"] = f"sha256={sig}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.url, content=body, headers=headers)
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("Webhook alert failed: %s", exc)

    async def send_structure(self, payload: dict) -> None:
        await self.send(payload)
