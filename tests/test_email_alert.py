"""Tests for EmailAlert — aiosmtplib mocked, no real SMTP needed."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub aiosmtplib so the module can be imported without the real package
_aiosmtplib_stub = ModuleType("aiosmtplib")
_aiosmtplib_stub.send = AsyncMock()  # type: ignore[attr-defined]
sys.modules.setdefault("aiosmtplib", _aiosmtplib_stub)

from alerts.email_alert import EmailAlert  # noqa: E402


# ── Shared fixture ────────────────────────────────────────────────────────────

def _make_payload(
    symbol: str = "BTC/USDT",
    direction: str = "long",
    score: int = 75,
    htf_trend: str = "bullish",
    session: str = "london",
) -> dict:
    return {
        "scenario_name": "htf_pullback_continuation",
        "alert_type": "ENTRY_CONFIRMED",
        "symbol": symbol,
        "pair": symbol.replace("/", ""),
        "timeframe": "15m",
        "direction": direction,
        "score": score,
        "htf_trend": htf_trend,
        "session": session,
        "scenario_detail": "htf_pullback_continuation | long | confirmed",
        "ict_full_setup": False,
        "confidence_factors": {
            "htf_alignment": True,
            "fvg_or_ob_presence": True,
            "volume_confirmation": False,
            "liquidity_confluence": False,
            "session_time": True,
        },
        "risk_plan": {
            "entry_low": 83000.0,
            "entry_high": 83500.0,
            "stop_loss": 82500.0,
            "tp1": 84500.0,
            "tp2": 85800.0,
            "tp3": 87000.0,
            "rr_ratio": 2.8,
            "position_size_pct": 1.0,
            "invalidation_level": 82500.0,
        },
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@pytest.fixture
def alert() -> EmailAlert:
    return EmailAlert(
        host="smtp.gmail.com",
        port=587,
        username="test@example.com",
        password="secret",
        to_email="trader@example.com",
    )


# ── send() tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_calls_aiosmtplib(alert: EmailAlert) -> None:
    """send() aiosmtplib.send'i bir kez çağırmalı."""
    payload = _make_payload()
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await alert.send(payload)
        mock_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_passes_correct_smtp_params(alert: EmailAlert) -> None:
    """SMTP bağlantı parametreleri doğru iletilmeli."""
    payload = _make_payload()
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await alert.send(payload)
        _, kwargs = mock_send.call_args
        assert kwargs["hostname"] == "smtp.gmail.com"
        assert kwargs["port"] == 587
        assert kwargs["username"] == "test@example.com"
        assert kwargs["password"] == "secret"
        assert kwargs["start_tls"] is True


@pytest.mark.asyncio
async def test_send_email_headers(alert: EmailAlert) -> None:
    """Email From/To/Subject alanları doğru ayarlanmalı."""
    payload = _make_payload(symbol="ETH/USDT", direction="short")
    with patch("aiosmtplib.send", new_callable=AsyncMock) as mock_send:
        await alert.send(payload)
        msg = mock_send.call_args[0][0]
        assert msg["From"] == "test@example.com"
        assert msg["To"] == "trader@example.com"
        assert "ETH/USDT" in msg["Subject"]
        assert "SHORT" in msg["Subject"]


@pytest.mark.asyncio
async def test_send_smtp_error_does_not_raise(alert: EmailAlert) -> None:
    """SMTP hatası exception olarak dışarı sızmamalı."""
    payload = _make_payload()
    with patch("aiosmtplib.send", side_effect=ConnectionRefusedError("SMTP down")):
        # Should not raise — alerts must be resilient
        try:
            await alert.send(payload)
        except Exception:
            pytest.fail("send() SMTP hatasında exception fırlattı")


# ── _format_text() tests ──────────────────────────────────────────────────────

def test_format_text_contains_symbol(alert: EmailAlert) -> None:
    payload = _make_payload(symbol="SOL/USDT")
    text = alert._format_text(payload)
    assert "SOL/USDT" in text


def test_format_text_contains_direction(alert: EmailAlert) -> None:
    payload = _make_payload(direction="short")
    text = alert._format_text(payload)
    assert "short" in text.lower()


def test_format_text_contains_score(alert: EmailAlert) -> None:
    payload = _make_payload(score=82)
    text = alert._format_text(payload)
    assert "82" in text


def test_format_text_contains_entry_zone(alert: EmailAlert) -> None:
    payload = _make_payload()
    text = alert._format_text(payload)
    assert "83000" in text
    assert "83500" in text


def test_format_text_contains_stop(alert: EmailAlert) -> None:
    payload = _make_payload()
    text = alert._format_text(payload)
    assert "82500" in text


def test_format_text_contains_all_tps(alert: EmailAlert) -> None:
    payload = _make_payload()
    text = alert._format_text(payload)
    assert "84500" in text   # TP1
    assert "85800" in text   # TP2
    assert "87000" in text   # TP3


def test_format_text_contains_rr(alert: EmailAlert) -> None:
    payload = _make_payload()
    text = alert._format_text(payload)
    assert "2.8" in text


def test_format_text_long_signal(alert: EmailAlert) -> None:
    payload = _make_payload(symbol="BTC/USDT", direction="long", score=90)
    text = alert._format_text(payload)
    assert len(text) > 50  # mesaj boş değil


# ── Constructor tests ──────────────────────────────────────────────────────────

def test_constructor_stores_params() -> None:
    a = EmailAlert("host", 465, "user@x.com", "pw", "dest@x.com")
    assert a.host == "host"
    assert a.port == 465
    assert a.username == "user@x.com"
    assert a.password == "pw"
    assert a.to_email == "dest@x.com"
