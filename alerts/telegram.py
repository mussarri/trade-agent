from __future__ import annotations

import asyncio
import logging

from telegram import Bot

from alerts.base import BaseAlert

logger = logging.getLogger(__name__)

EMOJI = {
    "SETUP_DETECTED": "👀",
    "ENTRY_CONFIRMED": "✅",
    "HTF_STRUCTURE_SHIFT_BULLISH": "🟢",
    "HTF_STRUCTURE_SHIFT_BEARISH": "🔴",
}


class TelegramAlert(BaseAlert):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.timeout_seconds = 30
        self.max_attempts = 3

    async def send(self, payload: dict) -> None:
        text = self._format_entry(payload)
        await self._send_message(text, "entry")

    async def send_setup(self, payload: dict) -> None:
        text = self._format_setup(payload)
        await self._send_message(text, "setup")

    async def send_structure(self, payload: dict) -> None:
        text = self._format_structure_shift(payload)
        await self._send_message(text, "structure")

    async def _send_message(self, text: str, alert_kind: str) -> None:
        for attempt in range(1, self.max_attempts + 1):
            try:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode="HTML",
                    connect_timeout=self.timeout_seconds,
                    read_timeout=self.timeout_seconds,
                    write_timeout=self.timeout_seconds,
                    pool_timeout=self.timeout_seconds,
                )
                return
            except Exception as exc:
                if attempt >= self.max_attempts:
                    logger.warning("Telegram %s alert failed after %s attempts: %s", alert_kind, attempt, exc)
                    return
                logger.warning(
                    "Telegram %s alert failed on attempt %s/%s: %s",
                    alert_kind,
                    attempt,
                    self.max_attempts,
                    exc,
                )
                await asyncio.sleep(attempt)

    def _format_setup(self, payload: dict) -> str:
        pair = payload.get("pair") or payload.get("symbol", "").replace("/", "")
        direction = payload.get("direction", "").upper()
        trend = payload.get("trend", payload.get("htf_trend", ""))
        zone = payload.get("zone") or [payload.get("entry_zone_low", 0), payload.get("entry_zone_high", 0)]
        low = float(zone[0]) if len(zone) > 0 else 0.0
        high = float(zone[1]) if len(zone) > 1 else 0.0
        inv = float(payload.get("sl", payload.get("invalidation_level", 0.0)))
        timeout = int(payload.get("max_candles", 0))
        return (
            f"{EMOJI['SETUP_DETECTED']} <b>SETUP_DETECTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {pair}  {direction}\n"
            f"📈 HTF Trend : {trend}\n"
            f"👁 Zone      : {low:.4f} - {high:.4f}\n"
            f"🛑 SL (watch): {inv:.4f}\n"
            f"⏳ Timeout   : {timeout} candles"
        )

    def _format_entry(self, payload: dict) -> str:
        plan = payload.get("risk_plan", {})
        pair = payload.get("pair") or payload.get("symbol", "").replace("/", "")
        direction = payload.get("direction", "").upper()
        trend = payload.get("trend", payload.get("htf_trend", ""))
        score = int(payload.get("score", 0))
        rr = float(plan.get("rr_ratio", 0.0))
        entry = float(payload.get("entry", (plan.get("entry_low", 0.0) + plan.get("entry_high", 0.0)) / 2))
        stop = float(payload.get("sl", plan.get("stop_loss", 0.0)))
        tp = payload.get("tp") or [plan.get("tp1", 0.0), plan.get("tp2", 0.0), plan.get("tp3", 0.0)]
        tp1 = float(tp[0]) if len(tp) > 0 else 0.0
        tp2 = float(tp[1]) if len(tp) > 1 else 0.0
        tp3 = float(tp[2]) if len(tp) > 2 else 0.0
        return (
            f"{EMOJI['ENTRY_CONFIRMED']} <b>ENTRY_CONFIRMED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {pair}  {direction}\n"
            f"📈 HTF Trend : {trend}\n"
            f"⭐ Confidence : {score}/100\n"
            f"📍 Entry      : {entry:.4f}\n"
            f"🛑 SL         : {stop:.4f}\n"
            f"🎯 TP1/TP2/TP3: {tp1:.4f} / {tp2:.4f} / {tp3:.4f}\n"
            f"📊 R:R        : {rr:.2f}"
        )

    def _format_structure_shift(self, payload: dict) -> str:
        alert_type = str(payload.get("alert_type", "HTF_STRUCTURE_SHIFT"))
        if alert_type.startswith("LTF_") and alert_type.endswith("_BREAKOUT"):
            icon = "🚀" if "_HIGH_" in alert_type else "⚠️"
            symbol = payload.get("symbol", "")
            timeframe = payload.get("timeframe_ltf", payload.get("timeframe", ""))
            level = float(payload.get("broken_level", 0.0))
            close = float(payload.get("current_close", 0.0))
            direction = str(payload.get("direction", "")).upper()
            reason = payload.get("reason", "")
            return (
                f"{icon} <b>{alert_type}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 {symbol} ({timeframe})\n"
                f"📍 Broken Level : {level:.6f}\n"
                f"💵 Current Close: {close:.6f}\n"
                f"🧭 Direction    : {direction}\n"
                f"📝 {reason}"
            )

        icon = EMOJI.get(alert_type, "📐")
        symbol = payload.get("symbol", "")
        timeframe = payload.get("timeframe_htf", payload.get("timeframe", ""))
        prev_trend = str(payload.get("previous_htf_trend", "neutral"))
        new_trend = str(payload.get("new_htf_trend", payload.get("direction", "neutral")))
        level = float(payload.get("broken_level", 0.0))
        close = float(payload.get("current_close", 0.0))
        reason = payload.get("reason", "")
        return (
            f"{icon} <b>{alert_type}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {symbol} ({timeframe})\n"
            f"🧱 Broken Level : {level:.6f}\n"
            f"💵 Current Close: {close:.6f}\n"
            f"↪️ Trend Shift   : {prev_trend} → {new_trend}\n"
            f"📝 {reason}"
        )
