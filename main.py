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

    # Build combined symbol list and tf_pairs, with symbol-scoped routing when
    # Twelve Data is enabled so crypto and forex pipelines don't cross-fire.
    all_symbols = list(cfg.symbols)
    htf_list = list(cfg.timeframes.htf)
    ltf_list = list(cfg.timeframes.ltf)
    all_scenarios = list(cfg.scenarios.enabled)
    symbol_tf_groups = None

    if cfg.twelvedata.enabled:
        td_tf = cfg.twelvedata.timeframe
        all_symbols.extend(cfg.twelvedata.symbols)
        htf_list.append(td_tf)
        ltf_list.append(td_tf)
        all_scenarios = list(dict.fromkeys(all_scenarios + cfg.twelvedata.scenarios))
        symbol_tf_groups = [
            {"symbols": cfg.symbols, "htf": h, "ltf": l}
            for h, l in zip(cfg.timeframes.htf, cfg.timeframes.ltf)
        ] + [
            {
                "symbols": cfg.twelvedata.symbols,
                "htf": td_tf,
                "ltf": td_tf,
            }
        ]

    return SignalEngine(
        symbols=all_symbols,
        htf=htf_list,
        ltf=ltf_list,
        min_score=cfg.scoring.min_score,
        min_rr_ratio=cfg.scoring.min_rr_ratio,
        risk_per_trade_pct=cfg.risk.risk_per_trade_pct,
        atr_sl_multiplier=cfg.risk.atr_sl_multiplier,
        enabled_scenarios=all_scenarios,
        alerts=alerts,
        htf_pivot_length=cfg.structure.htf_pivot_length,
        ltf_pivot_length=cfg.structure.ltf_pivot_length,
        min_swing_distance_atr_mult=cfg.structure.min_swing_distance_atr_mult,
        equal_level_tolerance=cfg.structure.equal_level_tolerance,
        use_close_for_break_confirmation=cfg.structure.use_close_for_break_confirmation,
        symbol_tf_groups=symbol_tf_groups,
    )


engine = build_engine()
app = create_app(engine)
engine.set_broadcaster(app.state.ws_manager.broadcast_json)


if __name__ == "__main__":
    _, env = load_settings()
    uvicorn.run("main:app", host=env.api_host, port=env.api_port, reload=False)
