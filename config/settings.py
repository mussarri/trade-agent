from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExchangeConfig(BaseModel):
    id: str = "binance"
    sandbox: bool = False


class TimeframesConfig(BaseModel):
    htf: list[str] = Field(default_factory=lambda: ["4h", "1d"])
    ltf: list[str] = Field(default_factory=lambda: ["15m", "1h"])


class ScoringConfig(BaseModel):
    min_score: int = 65
    min_rr_ratio: float = 2.0


class RiskConfig(BaseModel):
    risk_per_trade_pct: float = 1.0
    atr_sl_multiplier: float = 0.5
    atr_period: int = 14


class TelegramConfig(BaseModel):
    enabled: bool = True


class EmailAlertConfig(BaseModel):
    enabled: bool = False
    daily_summary: bool = True
    summary_hour: int = 8


class DiscordConfig(BaseModel):
    enabled: bool = False


class WebhookConfig(BaseModel):
    enabled: bool = False


class AlertFiltersConfig(BaseModel):
    min_score: int = 65
    min_rr_ratio: float = 2.0
    cooldown_minutes: int = 5


class AlertsConfig(BaseModel):
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    email: EmailAlertConfig = Field(default_factory=EmailAlertConfig)
    discord: DiscordConfig = Field(default_factory=DiscordConfig)
    webhook: WebhookConfig = Field(default_factory=WebhookConfig)
    filters: AlertFiltersConfig = Field(default_factory=AlertFiltersConfig)


class ScenarioConfig(BaseModel):
    enabled: list[str] = Field(
        default_factory=lambda: [
            "bos_continuation",
            "choch_confirmation",
            "fvg_retrace",
            "liquidity_sweep",
        ]
    )


class AppConfig(BaseModel):
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig)
    symbols: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    timeframes: TimeframesConfig = Field(default_factory=TimeframesConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    alerts: AlertsConfig = Field(default_factory=AlertsConfig)
    scenarios: ScenarioConfig = Field(default_factory=ScenarioConfig)


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    binance_api_key: str = ""
    binance_secret: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    discord_webhook_url: str = ""

    webhook_url: str = ""
    webhook_secret: str = ""

    alert_min_score: int = 65
    alert_min_rr: float = 2.0
    alert_cooldown_minutes: int = 5

    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_user: str = ""
    email_password: str = ""
    email_to: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000


def load_yaml(path: str | Path = "config/settings.yaml") -> dict[str, Any]:
    cfg_path = Path(path)
    if not cfg_path.exists():
        return {}
    with cfg_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError("settings.yaml root must be a mapping")
    return raw


def load_settings(path: str | Path = "config/settings.yaml") -> tuple[AppConfig, EnvSettings]:
    app_cfg = AppConfig.model_validate(load_yaml(path))
    env_cfg = EnvSettings()
    return app_cfg, env_cfg
