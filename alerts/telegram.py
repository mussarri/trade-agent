from __future__ import annotations

import logging

from telegram import Bot

from alerts.base import BaseAlert

logger = logging.getLogger(__name__)

EMOJI = {
    "BOS_CONTINUATION":  "📈",
    "SMART_MONEY_ENTRY": "💰",
    "LIQUIDITY_SWEEP":   "🎯",
}


class TelegramAlert(BaseAlert):
    def __init__(self, bot_token: str, chat_id: str):
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id

    async def send(self, payload: dict) -> None:
        text = self._format(payload)
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Telegram alert failed: %s", exc)

    async def send_setup(self, payload: dict) -> None:
        text = self._format_setup(payload)
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Telegram setup alert failed: %s", exc)

    async def send_trigger(self, payload: dict) -> None:
        text = self._format_trigger(payload)
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Telegram trigger alert failed: %s", exc)

    async def send_tp_hit(self, payload: dict) -> None:
        text = self._format_tp_hit(payload)
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Telegram TP hit alert failed: %s", exc)

    async def send_stop_hit(self, payload: dict) -> None:
        text = self._format_stop_hit(payload)
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Telegram stop alert failed: %s", exc)

    async def send_invalidation(self, payload: dict) -> None:
        text = self._format_invalidation(payload)
        try:
            await self.bot.send_message(chat_id=self.chat_id, text=text, parse_mode="HTML")
        except Exception as exc:
            logger.warning("Telegram invalidation alert failed: %s", exc)

    def _format_tp_hit(self, payload: dict) -> str:
        status = payload.get("status", "")
        level_map = {"tp1_hit": ("TP1", "tp1"), "tp2_hit": ("TP2", "tp2"), "tp3_hit": ("TP3", "tp3")}
        label, key = level_map.get(status, ("TP", "tp1"))
        pair = payload.get("pair") or payload.get("symbol", "").replace("/", "")
        direction = payload.get("direction", "").upper()
        dir_icon = "▲" if payload.get("direction") == "long" else "▼"
        rp = payload.get("risk_plan", {})
        tp_price = rp.get(key, 0)
        rr = rp.get("rr_ratio", 0)
        alert_type = payload.get("alert_type", payload.get("scenario_name", ""))
        emoji = EMOJI.get(alert_type, "🔔")
        return (
            f"✅ <b>{label} HIT</b> {emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {pair}  {dir_icon} {direction}\n"
            f"📋 {alert_type}\n"
            f"🎯 {label} Price : {tp_price:.4f}\n"
            f"📊 R:R        : {rr:.2f}"
        )

    def _format_stop_hit(self, payload: dict) -> str:
        pair = payload.get("pair") or payload.get("symbol", "").replace("/", "")
        direction = payload.get("direction", "").upper()
        dir_icon = "▲" if payload.get("direction") == "long" else "▼"
        rp = payload.get("risk_plan", {})
        stop = rp.get("stop_loss", 0)
        entry_low = rp.get("entry_low", 0)
        entry_high = rp.get("entry_high", 0)
        alert_type = payload.get("alert_type", payload.get("scenario_name", ""))
        emoji = EMOJI.get(alert_type, "🔔")
        return (
            f"🛑 <b>STOP HIT</b> {emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {pair}  {dir_icon} {direction}\n"
            f"📋 {alert_type}\n"
            f"🛑 Stop       : {stop:.4f}\n"
            f"📍 Entry was  : {entry_low:.4f} – {entry_high:.4f}"
        )

    def _format_invalidation(self, payload: dict) -> str:
        pair = payload.get("pair") or payload.get("symbol", "").replace("/", "")
        direction = payload.get("direction", "").upper()
        dir_icon = "▲" if payload.get("direction") == "long" else "▼"
        rp = payload.get("risk_plan", {})
        inv = rp.get("invalidation_level", 0)
        alert_type = payload.get("alert_type", payload.get("scenario_name", ""))
        emoji = EMOJI.get(alert_type, "🔔")
        return (
            f"❌ <b>INVALIDATED</b> {emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {pair}  {dir_icon} {direction}\n"
            f"📋 {alert_type}\n"
            f"🚫 Invalidation: {inv:.4f}"
        )

    def _format_setup(self, payload: dict) -> str:
        alert_type = payload.get("alert_type", payload.get("scenario_name", ""))
        pair = payload.get("pair") or payload.get("symbol", "").replace("/", "")
        direction = payload.get("direction", "").upper()
        emoji = EMOJI.get(alert_type, "🔔")
        dir_icon = "▲" if payload.get("direction") == "long" else "▼"
        low = payload.get("entry_zone_low", 0)
        high = payload.get("entry_zone_high", 0)
        inv = payload.get("invalidation_level", 0)
        timeout = payload.get("max_candles", 0)
        htf_trend = payload.get("htf_trend", "")
        return (
            f"👀 <b>SETUP DETECTED</b> {emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {pair}  {dir_icon} {direction}\n"
            f"📋 {alert_type}\n"
            f"📈 HTF: {htf_trend}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👁 Watch zone : {low:.4f} – {high:.4f}\n"
            f"🚫 Invalidation: {inv:.4f}\n"
            f"⏳ Timeout    : {timeout} candles"
        )

    def _format_trigger(self, payload: dict) -> str:
        alert_type = payload.get("alert_type", payload.get("scenario_name", ""))
        pair = payload.get("pair") or payload.get("symbol", "").replace("/", "")
        direction = payload.get("direction", "").upper()
        emoji = EMOJI.get(alert_type, "🔔")
        dir_icon = "▲" if payload.get("direction") == "long" else "▼"
        low = payload.get("entry_zone_low", 0)
        high = payload.get("entry_zone_high", 0)
        conditions = payload.get("conditions", {})
        cond_str = ", ".join(k for k, v in conditions.items() if v) or "—"
        f = payload.get("confidence_factors", {})
        fvg_ok = f.get("fvg_presence", f.get("fvg_or_ob_presence"))
        factors = (
            f"{'✅' if f.get('htf_alignment')         else '❌'} HTF   "
            f"{'✅' if fvg_ok                          else '❌'} FVG\n"
            f"{'✅' if f.get('volume_confirmation')   else '❌'} Vol   "
            f"{'✅' if f.get('liquidity_confluence')  else '❌'} Liq\n"
            f"{'✅' if f.get('session_time')          else '❌'} Session"
        )
        return (
            f"⚡ <b>TRIGGER FIRED</b> {emoji}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {pair}  {dir_icon} {direction}\n"
            f"📋 {alert_type}\n"
            f"🎯 Condition  : {cond_str}\n"
            f"📍 Zone       : {low:.4f} – {high:.4f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{factors}"
        )

    def _format(self, payload: dict) -> str:
        plan = payload.get("risk_plan", {})
        direction = payload.get("direction", "").upper()
        alert_type = payload.get("alert_type", payload.get("scenario_name", ""))
        pair = payload.get("pair") or payload.get("symbol", "").replace("/", "")
        score = payload.get("score", 0)
        htf_trend = payload.get("htf_trend", "")
        session = payload.get("session", "")
        scenario_detail = payload.get("scenario_detail", "")

        f = payload.get("confidence_factors", {})
        fvg_ok = f.get("fvg_presence", f.get("fvg_or_ob_presence"))
        factors = (
            f"{'✅' if f.get('htf_alignment')         else '❌'} HTF Trend    "
            f"{'✅' if fvg_ok                          else '❌'} FVG\n"
            f"{'✅' if f.get('volume_confirmation')   else '❌'} Volume       "
            f"{'✅' if f.get('liquidity_confluence')  else '❌'} Liquidity\n"
            f"{'✅' if f.get('session_time')          else '❌'} Session"
        )

        emoji = EMOJI.get(alert_type, "🔔")
        ict_badge = " ⭐" if payload.get("ict_full_setup") else ""

        entry_low = plan.get("entry_low", 0)
        entry_high = plan.get("entry_high", 0)
        stop = plan.get("stop_loss", 0)
        tp1 = plan.get("tp1", 0)
        tp2 = plan.get("tp2", 0)
        tp3 = plan.get("tp3", 0)

        return (
            f"{emoji} <b>{alert_type}{ict_badge}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Pair      : {pair}\n"
            f"📊 Direction : {direction}\n"
            f"⭐ Score     : {score}/100\n"
            f"📈 HTF Trend : {htf_trend}\n"
            f"🕐 Session   : {session}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📍 Entry     : {entry_low:.4f} – {entry_high:.4f}\n"
            f"🛑 Stop      : {stop:.4f}\n"
            f"🎯 TP1       : {tp1:.4f}\n"
            f"🎯 TP2       : {tp2:.4f}\n"
            f"🎯 TP3       : {tp3:.4f}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{factors}\n"
            f"📝 {scenario_detail}"
        )
