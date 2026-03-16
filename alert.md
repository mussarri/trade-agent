# Alert System — Implementation Spec v2.0
> AI Trade Alert System | Trend Continuation | ICT / Smart Money | Multi-Timeframe

---

## Claude Code Talimatları

Bu dosya mevcut trade-agent projesine uygulanacak alert sistemi spesifikasyonudur.
Aşağıdaki adımları sırayla uygula. Her adımı tamamladıktan sonra test et,
hata varsa düzelt, sonra bir sonraki adıma geç.

**Strateji odağı: Trend Continuation**
Sistem yalnızca mevcut trend yönünde setup arar. HTF alignment olmadan
hiçbir sinyal üretilmez — bu kuralın istisnası yoktur.

---

## 1. Sistem Mimarisi

```
Price API (Binance WebSocket)
        ↓
  Market Analyzer
  ├── swing highs / lows
  ├── equal highs / lows  →  LiquidityZone
  ├── market structure (HH/HL/LH/LL)
  ├── BOS (Break of Structure)
  ├── FVG (Fair Value Gap)
  └── volume spikes
        ↓
  Scenario Engine  [3 senaryo]
  ├── BOSContinuation    — trend devamı ana senaryo
  ├── FVGRetraceEntry    — pullback entry
  └── LiquiditySweep     — sweep + trend yönüne dönüş
        ↓
  Confidence Scorer
  HTF alignment (30) | FVG/OB presence (25) | Volume (20)
  Liquidity confluence (15) | Session (10)
        ↓
  Hard Filter: htf_alignment == False → sinyal YOK
        ↓
  Alert Engine
  ├── Telegram Bot
  ├── Discord Webhook
  ├── HTTP Webhook
  └── Email (SMTP)
```

---

## 2. Temel Prensipler

```
1. HTF trend yönü belirler — LTF sadece entry verir
2. HTF alignment FALSE ise pipeline durur, hesaplama yapılmaz
3. Setup oluşur → bekle → konfirmasyon gelince alert
4. Az sinyal, doğru sinyal — min_score 65, min_rr 2.5
5. 3 senaryo confluence olduğunda (BOS + FVG + Sweep aynı bölge)
   bu en güçlü setup sayılır → ICT full setup bonus
```

---

## 3. Veri Kaynağı & Konfigürasyon

```yaml
# config/settings.yaml

data:
  poll_interval_seconds: 15
  history_bars: 200

timeframes:
  ltf: "15m"           # ana analiz (5m veya 15m)
  htf: "1h"            # trend doğrulama (1h veya 4h)

symbols:
  - BTC/USDT
  - ETH/USDT
  - SOL/USDT

scoring:
  min_score: 65                 # 55'ten 65'e — trend continuation daha seçici
  min_rr_ratio: 2.5             # 2.0'dan 2.5'e
  htf_alignment_required: true  # hard filter — istisnası yok

alerts:
  telegram:
    enabled: true
  discord:
    enabled: false
  webhook:
    enabled: false
  email:
    enabled: false
    daily_summary: true
    summary_hour: 8

  filters:
    cooldown_minutes: 5
    allowed_sessions:
      - london
      - new_york
```

```bash
# .env.example
BINANCE_API_KEY=
BINANCE_SECRET=
ENGINE_MODE=live

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

DISCORD_WEBHOOK_URL=
WEBHOOK_URL=
WEBHOOK_SECRET=

EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USER=
EMAIL_PASSWORD=
EMAIL_TO=

API_HOST=0.0.0.0
API_PORT=8000

ALERT_MIN_SCORE=65
ALERT_MIN_RR=2.5
ALERT_COOLDOWN_MINUTES=5
```

---

## 4. Veri Modelleri

### Yeni dosya: `core/models.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from pydantic import BaseModel


# ── Market Analyzer Çıktıları ─────────────────────────────────────────────

@dataclass
class LiquidityZone:
    level: float
    kind: Literal["equal_high", "equal_low"]
    touch_count: int = 2
    swept: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FairValueGap:
    direction: Literal["long", "short"]
    low: float
    high: float
    midpoint: float
    active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BOSEvent:
    direction: Literal["bullish", "bearish"]
    level: float
    timestamp: datetime


@dataclass
class VolumeSpike:
    candle_index: int
    volume: float
    avg_volume: float
    ratio: float          # volume / avg_volume, >2.0 ise güçlü spike


# ── Setup & Trigger ───────────────────────────────────────────────────────

@dataclass
class Setup:
    scenario_name: str
    symbol: str
    direction: Literal["long", "short"]
    created_at: datetime

    watch_low: float              # entry bölgesi alt
    watch_high: float             # entry bölgesi üst

    invalidation_level: float     # bu seviye kapanışta setup iptal
    timeout_candles: int = 20
    candles_elapsed: int = 0

    meta: dict = field(default_factory=dict)


@dataclass
class TriggerCondition:
    kind: Literal["close_confirm", "sweep_reversal", "breakout_close"]


@dataclass
class Trigger:
    setup: Setup
    condition: TriggerCondition
    entry_low: float
    entry_high: float
    stop_loss: float
    timestamp: datetime
    confidence_factors: dict[str, bool]


# ── Alert Payload ─────────────────────────────────────────────────────────

class AlertPayload(BaseModel):
    pair: str
    type: str
    direction: Literal["LONG", "SHORT"]
    entry_zone: list[float]
    stop: float
    targets: list[float]
    confidence: float
    score: int
    scenario_detail: str
    htf_trend: str
    session: str
    timestamp: datetime
    confidence_factors: dict[str, bool]
```

---

## 5. Market Analyzer Güncellemesi

### `core/structure.py` — Eklenecek fonksiyonlar

```python
def detect_equal_levels(
    swing_highs: list[SwingPoint],
    swing_lows: list[SwingPoint],
    tolerance_pct: float = 0.001,
) -> list[LiquidityZone]:
    """
    Ardışık swing noktaları arasındaki fark tolerance_pct'ten küçükse
    equal high / equal low → LiquidityZone oluşur.
    """


def detect_volume_spike(
    candles: list[Candle],
    lookback: int = 20,
    threshold: float = 2.0,
) -> VolumeSpike | None:
    """
    Son mumun hacmi son lookback mumun ortalamasından
    threshold kat fazlaysa VolumeSpike döndür.
    """


def detect_sweep(
    candle: Candle,
    zones: list[LiquidityZone],
) -> LiquidityZone | None:
    """
    Wick zone seviyesini geçti, close geri döndüyse sweep.

    Equal high sweep: candle.high > zone.level AND candle.close < zone.level
    Equal low sweep:  candle.low  < zone.level AND candle.close > zone.level

    Sweep olan zone.swept = True yap.
    """


def current_session() -> str:
    """
    UTC saatine göre:
    00:00–08:00 → asian
    08:00–12:00 → london
    12:00–13:00 → overlap
    13:00–21:00 → new_york
    21:00–00:00 → off
    """
```

### `core/context.py` — Güncellenecek alanlar

`StructureContext`'e ekle:

```python
liquidity_zones: list[LiquidityZone] = field(default_factory=list)
volume_spikes: list[VolumeSpike] = field(default_factory=list)
```

`update()` metoduna ekle:

```python
# Equal high/low
new_zones = detect_equal_levels(self.swing_highs, self.swing_lows)
for z in new_zones:
    if not any(abs(z.level - ex.level) < 1e-6 for ex in self.liquidity_zones):
        self.liquidity_zones.append(z)

# Sweep
swept_zone = detect_sweep(candle, self.liquidity_zones)
if swept_zone:
    swept_zone.swept = True

# Volume spike
spike = detect_volume_spike(self.candles)
if spike:
    self.volume_spikes.append(spike)
```

---

## 6. Scenario Engine — İki Aşamalı Mimari

### `scenarios/base.py` — Tam yeniden yaz

```python
from abc import ABC, abstractmethod
from core.context import StructureContext
from core.models import Setup, Trigger


class BaseScenario(ABC):
    name: str
    alert_type: str

    @abstractmethod
    def detect_setup(
        self,
        htf_ctx: StructureContext,
        ltf_ctx: StructureContext,
    ) -> Setup | None:
        """
        Koşul oluştu mu? Henüz alert YOK.
        Pipeline HTF alignment kontrolünü dışarıda yapıyor,
        burada tekrar kontrol etme.
        """
        ...

    @abstractmethod
    def detect_trigger(
        self,
        setup: Setup,
        ltf_ctx: StructureContext,
    ) -> Trigger | None:
        """
        Konfirmasyon geldi mi? Bu noktada alert GİDER.

        Türler:
        - close_confirm:   bölge içinde yön kapanışı
        - sweep_reversal:  wick dışı + geri kapanış
        - breakout_close:  seviye üzeri/altı kapanış
        """
        ...

    def is_invalidated(
        self,
        setup: Setup,
        ltf_ctx: StructureContext,
    ) -> bool:
        if setup.candles_elapsed >= setup.timeout_candles:
            return True
        close = ltf_ctx.last_close
        if close is None:
            return False
        if setup.direction == "long":
            return close < setup.invalidation_level
        return close > setup.invalidation_level

    def describe(self, setup: Setup, trigger: Trigger) -> str:
        return f"{self.name} | {setup.direction} | {trigger.condition.kind}"
```

---

## 7. Senaryolar

### 7.1 `scenarios/bos_continuation.py` — ANA SENARYO

```
Amaç: BOS sonrası pullback entry — trend devamı

detect_setup():
  Ön koşul:
    HTF bullish → sadece long setup
    HTF bearish → sadece short setup

  - ltf_ctx.last_bos var mı?
  - BOS yönü HTF trend ile aynı mı?
  - Pullback bölgesi:
      Long:  watch_low  = BOS sonrası ilk swing low
             watch_high = BOS seviyesi
      Short: watch_low  = BOS seviyesi
             watch_high = BOS sonrası ilk swing high
  - FVG aynı bölgede varsa watch zone'u FVG sınırlarına daralt
  - invalidation:
      Long:  BOS seviyesinin altında kapanış
      Short: BOS seviyesinin üzerinde kapanış
  - timeout_candles: 20
  - meta["bos_level"] = BOS seviyesi
  - meta["has_fvg"]   = bool

detect_trigger():
  Option A — close_confirm:
    Long:  close içinde ve üst yarıda (close > midpoint)
    Short: close içinde ve alt yarıda (close < midpoint)

  Option B — sweep_reversal:
    Long:  candle.low < watch_low AND close > watch_low
    Short: candle.high > watch_high AND close < watch_high

  confidence_factors:
    htf_alignment:        TRUE (pipeline garantiliyor)
    fvg_or_ob_presence:   meta["has_fvg"]
    volume_confirmation:  son 3 mumda VolumeSpike var mı
    liquidity_confluence: watch bölgesinde LiquidityZone var mı
    session_time:         current_session() in ["london", "new_york", "overlap"]

alert_type: "BOS_CONTINUATION"
```

### 7.2 `scenarios/fvg_retrace.py`

```
Amaç: Displacement + FVG + retrace — smart money entry

detect_setup():
  - ltf_ctx.active_fvgs içinde HTF trend yönüyle aynı FVG var mı?
      HTF bullish → long FVG
      HTF bearish → short FVG
  - Displacement kontrolü (FVG öncesi mum):
      body > ATR * 1.5  VEYA  volume spike
      İkisi de yoksa setup oluşturma — zayıf FVG
  - watch_low  = fvg.low
  - watch_high = fvg.high
  - invalidation:
      Long:  close < fvg.low - ATR * 0.3
      Short: close > fvg.high + ATR * 0.3
  - timeout_candles: 15
  - meta["fvg_midpoint"]    = fvg.midpoint
  - meta["has_displacement"] = bool

detect_trigger():
  Option A — close_confirm:
    Long:  candle.low <= fvg.high AND candle.close >= fvg.low
    Short: candle.high >= fvg.low AND candle.close <= fvg.high

  Option B — sweep_reversal:
    Long:  candle.low < fvg.low AND close > fvg.low
    Short: candle.high > fvg.high AND close < fvg.high

  ICT Full Setup — meta["ict_bonus"] = True:
    LiquidityZone sweep oldu (ltf_ctx'te swept zone var)
    VE bu FVG o sweep sonrası oluştu
    VE displacement var
    → Üçü birden varsa ict_bonus = True

  confidence_factors:
    htf_alignment:        TRUE
    fvg_or_ob_presence:   TRUE (bu senaryo zaten FVG)
    volume_confirmation:  displacement mumunda volume spike
    liquidity_confluence: FVG öncesinde swept LiquidityZone var mı
    session_time:         current_session() in ["london", "new_york", "overlap"]

alert_type: "SMART_MONEY_ENTRY"
```

### 7.3 `scenarios/liquidity_sweep.py`

```
Amaç: Stop hunt → trend yönüne dönüş

Trend continuation bağlamı:
  HTF bullish → equal LOW sweep ara (buy-side entry)
  HTF bearish → equal HIGH sweep ara (sell-side entry)
  Trende karşı sweep arama.

detect_setup():
  - ltf_ctx.liquidity_zones içinde swept == False zone var mı?
  - Zone yönü HTF trend ile uyumlu mu?
      HTF bullish → equal_low zone
      HTF bearish → equal_high zone
  - watch bölgesi:
      Long:  watch_low  = zone.level - ATR * 0.5
             watch_high = zone.level + ATR * 0.2
      Short: watch_low  = zone.level - ATR * 0.2
             watch_high = zone.level + ATR * 0.5
  - invalidation:
      Long:  close < zone.level - ATR * 1.5
      Short: close > zone.level + ATR * 1.5
  - timeout_candles: 30
  - meta["zone_level"] = zone.level
  - meta["zone_kind"]  = zone.kind

detect_trigger():
  SWEEP OLMADAN TRİGGER YOK — close_confirm kabul edilmez.

  Long (equal low sweep):
    candle.low < zone.level AND candle.close > zone.level
    → sweep_reversal

  Short (equal high sweep):
    candle.high > zone.level AND candle.close < zone.level
    → sweep_reversal

  confidence_factors:
    htf_alignment:        TRUE
    fvg_or_ob_presence:   sweep bölgesinde FVG veya OB var mı
    volume_confirmation:  sweep mumunda volume spike
    liquidity_confluence: birden fazla equal level aynı bölgede
    session_time:         current_session() in ["london", "new_york", "overlap"]

alert_type: "LIQUIDITY_SWEEP"
```

---

## 8. Confluence — En Güçlü Setup

Üç senaryo aynı bölgede aynı anda tetikleniyorsa tek sinyal üret:

```python
# pipeline.py
def _merge_confluence(self, signals: list[AlertPayload]) -> list[AlertPayload]:
    """
    Aynı sembol + aynı yön + 15 dakika içinde birden fazla sinyal varsa:
    - En yüksek score'luyu tut
    - Diğerlerinin confidence_factors'larını OR ile birleştir
    - Tek sinyal döndür
    """
```

---

## 9. Confidence Scorer

### `scoring/scorer.py` — Trend continuation ağırlıkları

```python
WEIGHTS = {
    "htf_alignment":          30,   # kritik
    "fvg_or_ob_presence":     25,   # entry kalitesi
    "volume_confirmation":    20,   # momentum teyidi
    "liquidity_confluence":   15,   # güçlendirici
    "session_time":           10,   # timing
}
# Toplam: 100

ICT_FULL_SETUP_BONUS = 15    # cap: 100

def score(match) -> int:
    total = sum(WEIGHTS.get(k, 0) for k, v in match.confidence_factors.items() if v)
    bonus = ICT_FULL_SETUP_BONUS if match.meta.get("ict_bonus") else 0
    return min(total + bonus, 100)
```

---

## 10. Pipeline — Hard Filter & Akış

### `core/pipeline.py` — Güncellenecek `run()` metodu

```python
async def run(self, htf_ctx: StructureContext, ltf_ctx: StructureContext):
    symbol = ltf_ctx.symbol

    # ── HARD FILTER ──────────────────────────────────────────────────────
    htf_trend = htf_ctx.trend
    if htf_trend == "neutral":
        logger.debug("HTF neutral — %s skipped", symbol)
        return []

    produced = []

    for scenario in self.scenarios:
        key = f"{scenario.name}:{symbol}"
        setups = self.active_setups.setdefault(key, [])

        # 1. Elapsed
        for s in setups:
            s.candles_elapsed += 1

        # 2. Invalidasyon
        valid = [s for s in setups if not scenario.is_invalidated(s, ltf_ctx)]
        self.active_setups[key] = valid

        # 3. Yeni setup — yön HTF trend ile uyumlu mu kontrol et
        if not self.active_setups[key]:
            new_setup = scenario.detect_setup(htf_ctx, ltf_ctx)
            if new_setup:
                trend_ok = (
                    (htf_trend == "bullish" and new_setup.direction == "long") or
                    (htf_trend == "bearish" and new_setup.direction == "short")
                )
                if trend_ok:
                    self.active_setups[key].append(new_setup)
                    logger.info("Setup: %s %s %s watch=[%.4f, %.4f]",
                        scenario.name, symbol, new_setup.direction,
                        new_setup.watch_low, new_setup.watch_high)

        # 4. Trigger
        for setup in self.active_setups[key][:]:
            trigger = scenario.detect_trigger(setup, ltf_ctx)
            if not trigger:
                continue

            # Cooldown
            last_alert = self.alert_cooldowns.get(symbol)
            if last_alert:
                elapsed_min = (datetime.now(timezone.utc) - last_alert).total_seconds() / 60
                if elapsed_min < self.cooldown_minutes:
                    continue

            # Skor
            computed_score = score(trigger)
            if computed_score < self.min_score:
                self.active_setups[key].remove(setup)
                continue

            # Risk planı
            plan = self.risk_planner.plan_from_trigger(trigger, ltf_ctx)
            if plan.rr_ratio < self.min_rr_ratio:
                self.active_setups[key].remove(setup)
                continue

            # Payload
            payload = AlertPayload(
                pair=symbol.replace("/", ""),
                type=scenario.alert_type,
                direction=setup.direction.upper(),
                entry_zone=[trigger.entry_low, trigger.entry_high],
                stop=trigger.stop_loss,
                targets=[plan.tp1, plan.tp2, plan.tp3],
                confidence=round(computed_score / 100, 2),
                score=computed_score,
                scenario_detail=scenario.describe(setup, trigger),
                htf_trend=htf_trend,
                session=current_session(),
                timestamp=trigger.timestamp,
                confidence_factors=trigger.confidence_factors,
            )

            self.alert_cooldowns[symbol] = datetime.now(timezone.utc)
            self.active_setups[key].remove(setup)
            produced.append(payload)

            await self._dispatch_alerts(payload)
            if self.broadcaster:
                maybe = self.broadcaster(payload.model_dump(mode="json"))
                if asyncio.iscoroutine(maybe):
                    await maybe

    return self._merge_confluence(produced)
```

---

## 11. Alert Formatları

### Telegram

```python
EMOJI = {
    "BOS_CONTINUATION":  "📈",
    "SMART_MONEY_ENTRY": "💰",
    "LIQUIDITY_SWEEP":   "🎯",
}

def format_telegram(payload: AlertPayload) -> str:
    emoji = EMOJI.get(payload.type, "🔔")
    f = payload.confidence_factors
    factors = (
        f"{'✅' if f.get('htf_alignment')         else '❌'} HTF Trend    "
        f"{'✅' if f.get('fvg_or_ob_presence')    else '❌'} FVG/OB\n"
        f"{'✅' if f.get('volume_confirmation')   else '❌'} Volume       "
        f"{'✅' if f.get('liquidity_confluence')  else '❌'} Liquidity\n"
        f"{'✅' if f.get('session_time')          else '❌'} Session"
    )
    return (
        f"{emoji} {payload.type}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Pair      : {payload.pair}\n"
        f"📊 Direction : {payload.direction}\n"
        f"⭐ Score     : {payload.score}/100\n"
        f"📈 HTF Trend : {payload.htf_trend}\n"
        f"🕐 Session   : {payload.session}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📍 Entry     : {payload.entry_zone[0]} – {payload.entry_zone[1]}\n"
        f"🛑 Stop      : {payload.stop}\n"
        f"🎯 TP1       : {payload.targets[0]}\n"
        f"🎯 TP2       : {payload.targets[1]}\n"
        f"🎯 TP3       : {payload.targets[2]}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{factors}\n"
        f"📝 {payload.scenario_detail}"
    )
```

### Alert JSON

```json
{
  "pair": "BTCUSDT",
  "type": "SMART_MONEY_ENTRY",
  "direction": "LONG",
  "entry_zone": [83100.0, 83450.0],
  "stop": 82600.0,
  "targets": [84500.0, 85800.0, 87200.0],
  "confidence": 0.80,
  "score": 80,
  "scenario_detail": "FVG retrace after sweep | ICT Full Setup",
  "htf_trend": "bullish",
  "session": "london",
  "timestamp": "2026-03-15T10:30:00Z",
  "confidence_factors": {
    "htf_alignment": true,
    "fvg_or_ob_presence": true,
    "volume_confirmation": true,
    "liquidity_confluence": true,
    "session_time": true
  }
}
```

---

## 12. Alert Kanalları

### `alerts/discord.py` — Yeni dosya

```python
import httpx
from alerts.base import BaseAlert
from core.models import AlertPayload

class DiscordAlert(BaseAlert):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    async def send(self, payload: AlertPayload) -> None:
        color = 0x00FF88 if payload.direction == "LONG" else 0xFF4444
        embed = {
            "title": f"{payload.type} — {payload.pair}",
            "color": color,
            "fields": [
                {"name": "Direction",  "value": payload.direction,                                    "inline": True},
                {"name": "Score",      "value": f"{payload.score}/100",                               "inline": True},
                {"name": "HTF Trend",  "value": payload.htf_trend,                                    "inline": True},
                {"name": "Entry Zone", "value": f"{payload.entry_zone[0]} – {payload.entry_zone[1]}", "inline": False},
                {"name": "Stop",       "value": str(payload.stop),                                    "inline": True},
                {"name": "TP1 / TP2",  "value": f"{payload.targets[0]} / {payload.targets[1]}",       "inline": True},
            ],
            "footer": {"text": payload.scenario_detail},
            "timestamp": payload.timestamp.isoformat(),
        }
        async with httpx.AsyncClient() as client:
            await client.post(self.webhook_url, json={"embeds": [embed]}, timeout=10.0)
```

### `alerts/webhook.py` — Yeni dosya

```python
import httpx
from alerts.base import BaseAlert
from core.models import AlertPayload

class WebhookAlert(BaseAlert):
    def __init__(self, url: str, headers: dict | None = None):
        self.url = url
        self.headers = headers or {}

    async def send(self, payload: AlertPayload) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                self.url,
                json=payload.model_dump(mode="json"),
                headers=self.headers,
                timeout=10.0,
            )
```

---

## 13. API Endpoint Güncellemesi

### `api/server.py` — Eklenecek endpoint'ler

```python
@app.get("/api/setups")
async def get_active_setups() -> dict:
    """Trigger beklenen aktif setup'ları listele."""
    result = {}
    for key, setups in engine.pipeline.active_setups.items():
        if setups:
            result[key] = [
                {
                    "scenario":        s.scenario_name,
                    "symbol":          s.symbol,
                    "direction":       s.direction,
                    "watch_low":       s.watch_low,
                    "watch_high":      s.watch_high,
                    "candles_elapsed": s.candles_elapsed,
                    "timeout_candles": s.timeout_candles,
                    "progress_pct":    round(s.candles_elapsed / s.timeout_candles * 100),
                }
                for s in setups
            ]
    return result


@app.get("/api/market/{symbol}")
async def get_market_context(symbol: str) -> dict:
    """Sembol için HTF + LTF yapısal özet."""
    sym = symbol.replace("USDT", "/USDT")
    htf_ctx = engine.contexts.get((sym, engine.htf))
    ltf_ctx = engine.contexts.get((sym, engine.ltf))
    return {
        "symbol":          sym,
        "htf_trend":       htf_ctx.trend if htf_ctx else "unknown",
        "ltf_trend":       ltf_ctx.trend if ltf_ctx else "unknown",
        "active_fvgs":     len(ltf_ctx.active_fvgs) if ltf_ctx else 0,
        "liquidity_zones": len(ltf_ctx.liquidity_zones) if ltf_ctx else 0,
        "last_bos":        str(ltf_ctx.last_bos) if ltf_ctx and ltf_ctx.last_bos else None,
    }
```

---

## 14. Test Senaryoları

```python
# tests/test_bos_continuation.py
def test_long_setup_bullish_htf():
    """HTF bullish + LTF BOS bullish → long setup oluşmalı"""

def test_no_setup_neutral_htf():
    """HTF neutral → setup oluşmamalı"""

def test_no_long_setup_bearish_htf():
    """HTF bearish → long setup oluşmamalı"""

def test_trigger_close_confirm():
    """Bölge içi üst yarı kapanış → trigger"""

def test_trigger_sweep_reversal():
    """Wick dışı + geri kapanış → trigger"""

def test_invalidation_level():
    """BOS seviyesi altı kapanış → setup iptal"""

def test_invalidation_timeout():
    """20 mum → setup iptal"""


# tests/test_fvg_retrace.py
def test_weak_fvg_no_setup():
    """Displacement yok, volume spike yok → setup oluşmamalı"""

def test_ict_full_setup_bonus():
    """Sweep + displacement + FVG + retrace → score +15"""

def test_wrong_direction_fvg_skipped():
    """HTF bullish iken short FVG → setup oluşmamalı"""


# tests/test_liquidity_sweep.py
def test_sweep_trend_direction_only():
    """HTF bullish → sadece equal LOW sweep"""

def test_no_close_confirm():
    """Sweep olmadan close_confirm → trigger yok"""

def test_sweep_volume_spike():
    """Sweep mumunda spike → volume_confirmation TRUE"""


# tests/test_pipeline.py
def test_htf_neutral_hard_filter():
    """HTF neutral → pipeline erken çıkış, sinyal yok"""

def test_htf_bearish_no_long():
    """HTF bearish → long setup pipeline'a girmiyor"""

def test_confluence_merge():
    """Aynı sembol/yönde 3 sinyal → tek birleşik sinyal"""

def test_cooldown():
    """5 dakika içinde aynı sembol → ikinci sinyal gönderilmez"""
```

---

## 15. Silinecek Dosyalar

```bash
# Artık kullanılmayan senaryolar
rm scenarios/choch_confirm.py
rm scenarios/ssob_reaction.py
rm scenarios/bos_retest.py    # bos_continuation ile değiştirildi
rm scenarios/fvg_fill.py      # fvg_retrace ile değiştirildi
```

---

## 16. Uygulama Sırası

```
Adım 1:  core/models.py oluştur
Adım 2:  core/structure.py güncelle
         (detect_equal_levels, detect_sweep, detect_volume_spike, current_session)
Adım 3:  core/context.py güncelle
         (liquidity_zones, volume_spikes + update() çağrıları)
Adım 4:  scenarios/base.py güncelle
Adım 5:  scenarios/bos_continuation.py yaz
Adım 6:  scenarios/fvg_retrace.py yaz
Adım 7:  scenarios/liquidity_sweep.py güncelle
Adım 8:  Eski senaryoları sil (adım 15)
Adım 9:  scoring/scorer.py güncelle (yeni ağırlıklar + ICT bonus)
Adım 10: alerts/discord.py oluştur
         alerts/webhook.py oluştur
Adım 11: core/pipeline.py güncelle
         (hard filter, iki aşamalı akış, cooldown, confluence merge)
Adım 12: api/server.py güncelle (/api/setups, /api/market/{symbol})
Adım 13: config/settings.yaml ve .env.example güncelle
Adım 14: pytest tests/ -v
Adım 15: docker compose build --no-cache && docker compose up -d
Adım 16: Doğrulama komutlarını çalıştır
```

---

## 17. Doğrulama Komutları

```bash
# HTF trend durumu
curl http://localhost:8000/api/market/BTCUSDT | python3 -m json.tool
curl http://localhost:8000/api/market/ETHUSDT | python3 -m json.tool

# Aktif setup'lar
curl http://localhost:8000/api/setups | python3 -m json.tool

# Tetiklenen sinyaller
curl http://localhost:8000/api/signals | python3 -m json.tool

# Engine logları
docker compose logs -f engine | grep -E "Setup|Trigger|Invalidat|Filter|Confluence"

# WebSocket
wscat -c ws://localhost:8000/ws
```

**Beklenen log akışı:**
```
HTF neutral — BTC/USDT skipped
HTF bullish — ETH/USDT processing
Setup: bos_continuation ETH/USDT long watch=[1891.0000, 1902.0000]
Setup: fvg_retrace ETH/USDT long watch=[1893.5000, 1899.0000]
Trigger: fvg_retrace ETH/USDT long | score=80 | session=london
Confluence merge: 2 signals → 1 (ETH/USDT long score=85)
```

---

*Alert System v2.0 | Trend Continuation | 3 Senaryo | HTF Hard Filter*
