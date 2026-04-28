from __future__ import annotations

import logging

import httpx

from alerts.base import BaseAlert
from core.models import AlertPayload

logger = logging.getLogger(__name__)


class DiscordAlert(BaseAlert):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, payload: dict) -> None:
        embed = self._build_embed(payload)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json={"embeds": [embed]})
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("Discord alert failed: %s", exc)

    async def send_structure(self, payload: dict) -> None:
        embed = self._build_structure_embed(payload)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json={"embeds": [embed]})
                resp.raise_for_status()
        except Exception as exc:
            logger.warning("Discord structure alert failed: %s", exc)

    def _build_embed(self, payload: dict) -> dict:
        direction = payload.get("direction", "").upper()
        color = 0x00FF88 if direction == "LONG" else 0xFF4444
        plan = payload.get("risk_plan", {})
        symbol = payload.get("symbol", "")
        score = payload.get("score", 0)
        alert_type = payload.get("alert_type", payload.get("scenario_name", ""))
        ict_badge = " ⭐ ICT Full Setup" if payload.get("ict_full_setup") else ""

        fields = [
            {"name": "Direction", "value": direction, "inline": True},
            {"name": "Score", "value": f"{score}/100", "inline": True},
            {"name": "R:R", "value": f"{plan.get('rr_ratio', 0):.2f}", "inline": True},
            {"name": "Entry", "value": f"{plan.get('entry_low', 0):.4f} – {plan.get('entry_high', 0):.4f}", "inline": False},
            {"name": "Stop Loss", "value": f"{plan.get('stop_loss', 0):.4f}", "inline": True},
            {"name": "TP1 / TP2 / TP3", "value": f"{plan.get('tp1', 0):.4f} / {plan.get('tp2', 0):.4f} / {plan.get('tp3', 0):.4f}", "inline": False},
        ]

        return {
            "title": f"🔔 {alert_type} — {symbol}{ict_badge}",
            "color": color,
            "fields": fields,
            "footer": {"text": f"trade-agent • {payload.get('timeframe', '')} • {payload.get('timestamp', '')}"},
        }

    def _build_structure_embed(self, payload: dict) -> dict:
        alert_type = str(payload.get("alert_type", "HTF_STRUCTURE_SHIFT"))
        if alert_type.startswith("LTF_") and alert_type.endswith("_BREAKOUT"):
            is_high_break = "_HIGH_" in alert_type
            color = 0x00CC66 if is_high_break else 0xCC6600
            symbol = payload.get("symbol", "")
            timeframe = payload.get("timeframe_ltf", payload.get("timeframe", ""))
            fields = [
                {"name": "Direction", "value": str(payload.get("direction", "")).upper(), "inline": True},
                {"name": "Broken Level", "value": f"{float(payload.get('broken_level', 0.0)):.6f}", "inline": True},
                {"name": "Current Close", "value": f"{float(payload.get('current_close', 0.0)):.6f}", "inline": True},
                {"name": "Displacement", "value": "Yes" if payload.get("displacement") else "No", "inline": True},
                {"name": "Reason", "value": str(payload.get("reason", "")), "inline": False},
            ]
            return {
                "title": f"📈 {alert_type} — {symbol}",
                "color": color,
                "fields": fields,
                "footer": {"text": f"trade-agent • {timeframe} • {payload.get('timestamp', '')}"},
            }

        is_bull = payload.get("alert_type") == "HTF_STRUCTURE_SHIFT_BULLISH"
        color = 0x00CC66 if is_bull else 0xCC3333
        symbol = payload.get("symbol", "")
        timeframe = payload.get("timeframe_htf", payload.get("timeframe", ""))
        fields = [
            {"name": "Previous Trend", "value": str(payload.get("previous_htf_trend", "neutral")), "inline": True},
            {"name": "New Trend", "value": str(payload.get("new_htf_trend", payload.get("direction", "neutral"))), "inline": True},
            {"name": "Broken Level", "value": f"{float(payload.get('broken_level', 0.0)):.6f}", "inline": True},
            {"name": "Current Close", "value": f"{float(payload.get('current_close', 0.0)):.6f}", "inline": True},
            {"name": "Reason", "value": str(payload.get("reason", "")), "inline": False},
        ]
        return {
            "title": f"📐 {payload.get('alert_type', 'HTF_STRUCTURE_SHIFT')} — {symbol}",
            "color": color,
            "fields": fields,
            "footer": {"text": f"trade-agent • {timeframe} • {payload.get('timestamp', '')}"},
        }
