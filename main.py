from __future__ import annotations

import logging
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
from api.server import create_app
from config.settings import load_settings
from core.engine import SignalEngine


def build_engine() -> SignalEngine:
    cfg, env = load_settings()

    alerts = []
    if cfg.alerts.telegram.enabled and env.telegram_bot_token and env.telegram_chat_id:
        from alerts.telegram import TelegramAlert
        alerts.append(TelegramAlert(
            bot_token=env.telegram_bot_token,
            chat_id=env.telegram_chat_id,
        ))

    if cfg.alerts.email.enabled and env.email_smtp_host and env.email_user and env.email_to:
        from alerts.email_alert import EmailAlert
        alerts.append(EmailAlert(
            host=env.email_smtp_host,
            port=env.email_smtp_port,
            username=env.email_user,
            password=env.email_password,
            to_email=env.email_to,
        ))

    if cfg.alerts.discord.enabled and env.discord_webhook_url:
        from alerts.discord import DiscordAlert
        alerts.append(DiscordAlert(webhook_url=env.discord_webhook_url))

    if cfg.alerts.webhook.enabled and env.webhook_url:
        from alerts.webhook import WebhookAlert
        alerts.append(WebhookAlert(url=env.webhook_url, secret=env.webhook_secret))

    return SignalEngine(
        symbols=cfg.symbols,
        htf=cfg.timeframes.htf,
        ltf=cfg.timeframes.ltf,
        min_score=cfg.scoring.min_score,
        min_rr_ratio=cfg.scoring.min_rr_ratio,
        risk_per_trade_pct=cfg.risk.risk_per_trade_pct,
        atr_sl_multiplier=cfg.risk.atr_sl_multiplier,
        enabled_scenarios=cfg.scenarios.enabled,
        alerts=alerts,
    )


engine = build_engine()
app = create_app(engine)
engine.set_broadcaster(app.state.ws_manager.broadcast_json)


if __name__ == "__main__":
    _, env = load_settings()
    uvicorn.run("main:app", host=env.api_host, port=env.api_port, reload=False)
