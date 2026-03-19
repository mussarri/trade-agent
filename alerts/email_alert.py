from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from alerts.base import BaseAlert

logger = logging.getLogger(__name__)


class EmailAlert(BaseAlert):
    def __init__(self, host: str, port: int, username: str, password: str, to_email: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.to_email = to_email

    async def send(self, payload: dict) -> None:
        msg = EmailMessage()
        msg["From"] = self.username
        msg["To"] = self.to_email
        msg["Subject"] = f"Signal Alert: {payload['symbol']} {payload['direction'].upper()}"
        msg.set_content(self._format_text(payload))
        # Port 465 → implicit TLS (use_tls); port 587 → STARTTLS (start_tls)
        use_tls = self.port == 465
        try:
            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=use_tls,
                start_tls=not use_tls,
            )
        except Exception as exc:
            logger.warning("Email alert failed: %s", exc)

    async def send_structure(self, payload: dict) -> None:
        msg = EmailMessage()
        msg["From"] = self.username
        msg["To"] = self.to_email
        msg["Subject"] = f"HTF Structure Shift: {payload.get('symbol', '')} {payload.get('new_htf_trend', '').upper()}"
        msg.set_content(self._format_structure_text(payload))
        use_tls = self.port == 465
        try:
            await aiosmtplib.send(
                msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=use_tls,
                start_tls=not use_tls,
            )
        except Exception as exc:
            logger.warning("Email structure alert failed: %s", exc)

    def _format_text(self, payload: dict) -> str:
        plan = payload["risk_plan"]
        return (
            f"Scenario: {payload['scenario_name']}\n"
            f"Symbol: {payload['symbol']}\n"
            f"Direction: {payload['direction']}\n"
            f"Score: {payload['score']}\n"
            f"Entry Zone: {plan['entry_low']:.4f} - {plan['entry_high']:.4f}\n"
            f"Stop: {plan['stop_loss']:.4f} | TP1: {plan['tp1']:.4f} | TP2: {plan['tp2']:.4f} | TP3: {plan['tp3']:.4f}\n"
            f"RR: {plan['rr_ratio']:.2f}"
        )

    def _format_structure_text(self, payload: dict) -> str:
        return (
            f"Alert: {payload.get('alert_type', 'HTF_STRUCTURE_SHIFT')}\n"
            f"Symbol: {payload.get('symbol', '')}\n"
            f"Timeframe: {payload.get('timeframe_htf', payload.get('timeframe', ''))}\n"
            f"Previous Trend: {payload.get('previous_htf_trend', 'neutral')}\n"
            f"New Trend: {payload.get('new_htf_trend', payload.get('direction', 'neutral'))}\n"
            f"Broken Level: {float(payload.get('broken_level', 0.0)):.6f}\n"
            f"Current Close: {float(payload.get('current_close', 0.0)):.6f}\n"
            f"Reason: {payload.get('reason', '')}\n"
        )
