# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

**Trade-Agent** is a cryptocurrency trading signal system. It monitors Binance markets in real-time, detects high-confidence setups via a two-stage pipeline, scores them, plans risk/reward levels, and dispatches alerts via Telegram, Discord, Email, and webhooks. A React dashboard visualizes active signals.

## Commands

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Run in demo mode (synthetic data, no API keys needed)
python main.py

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_htf_pullback_continuation.py -v

# Run with coverage
pytest --cov=core tests/

# Dashboard (ui/dashboard/)
npm install && npm run dev     # dev server
npm run build                  # production build

# Docker
docker-compose up                          # demo mode
ENGINE_MODE=live docker-compose up         # live Binance feed
```

## Architecture

### Data Flow

```
Binance WebSocket (ccxt.pro)
  ↓
DataFeed (per symbol/timeframe)
  → StructureContext.update(candle)   ← market state updated each closed candle
  ↓
Pipeline.run(htf_ctx, ltf_ctx)
  ├─ Stage 1: Scenario.detect_setup()   → SETUP_DETECTED alert (once per structure event)
  ├─ Stage 2: Scenario.detect_trigger() → ENTRY_CONFIRMED alert (once per setup)
  ├─ Scorer [min_score=65, 6 weighted factors, total=100]
  ├─ RiskPlanner [entry / SL / TP1–3, min R:R = 2.0]
  └─ AlertPayload → Telegram / Discord / Email / Webhook
  ↓
WebSocket → React dashboard
```

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `core/engine.py` | Orchestrates multi-symbol/timeframe loops, demo and live modes |
| `core/pipeline.py` | Two-stage detection, alert dedup, cooldowns, signal lifecycle |
| `core/context.py` | `StructureContext` — per-candle state: swings, BOS/CHoCH (internal + external), FVGs, liquidity zones |
| `core/structure.py` | Low-level ICT calculations: swing detection, FVG, displacement, volume spikes |
| `scenarios/` | Plugin trading patterns — drop a new file here, it's auto-loaded |
| `scoring/scorer.py` | Weights 6 confidence factors; factors map to `Trigger.confidence_factors` keys |
| `risk/planner.py` | Entry/SL/TP levels from market structure; structural swing levels preferred over R-multiples |
| `alerts/` | Multi-channel dispatch; `BaseAlert` defines `send()`, `send_setup()`, `send_trigger()`, `send_tp_hit()`, `send_stop_hit()`, `send_invalidation()` |
| `api/server.py` | FastAPI REST + WebSocket for dashboard |
| `config/settings.yaml` | Runtime config (symbols, timeframes, scoring thresholds) |

### Active Scenario: `htf_pullback_continuation`

The **only** active scenario. Strictly requires `htf=1h`, `ltf=5m`.

**Setup conditions** (`detect_setup`):
1. HTF trend is bullish or bearish (from `external_structure_labels`, falls back to MA/price-position)
2. LTF shows an active pullback against HTF trend (≥3 of last 6 structure labels are counter-trend)
3. A displacement candle exists in recent LTF history (range > 1.5× avg, body ratio ≥ 60%)
4. An entry zone exists: FVG → Order Block → 50–61.8% Fibonacci (checked in that priority order)
5. Current candle **overlaps** the zone (with a small ATR pad)
6. **First-touch rule**: zero prior candle touches of that zone since displacement

**Trigger conditions** (`detect_trigger`):
- Zone overlap still holds
- Reaction candle closes above/below zone midpoint
- Displacement-class bar (range > 1.5× avg, body ≥ 60%)
- Directional body in trend direction
- Micro-BOS: close breaks the last LTF swing high/low formed since displacement
- LTF structure is no longer printing counter-trend labels

On trigger: mutates `setup.alert_type = "ENTRY_CONFIRMED"` and `setup.meta["state"] = "TRIGGERED"`.

**Scorer weights** (must match `Trigger.confidence_factors` keys exactly):
```
htf_alignment   20   pullback_active  15   zone_reaction  20
displacement    20   micro_bos        20   first_pullback  5
```

### Deduplication & Anti-Spam

`Pipeline` has two interlocking guards to prevent re-alerting on the same zone:

1. **Structure ID** (`consumed_structures: dict[str, datetime]`, TTL = 4 h): Every `Setup.meta["structure_id"]` is consumed after trigger, invalidation, or expiry. `_is_structure_consumed()` blocks re-detection of the same zone.
2. **Direction cooldown** (`alert_cooldowns: dict[tuple, datetime]`): Keyed on `(symbol, scenario_name, timeframe, direction)`. Blocks both new setup detection **and** trigger re-firing for `cooldown_minutes` (default 5).

A new setup is only accepted if **both** guards pass and trend alignment holds.

### Adding a New Scenario

1. Create `scenarios/my_scenario.py` — subclass `BaseScenario`, set `name` and `alert_type`
2. Implement `detect_setup()`, `detect_trigger()`, optionally `is_invalidated()`
3. Set `setup.meta["structure_id"]` to a stable, event-specific string (prevents re-alert spam)
4. Add the scenario name to `config/settings.yaml` under `scenarios.enabled`
5. Add matching factor keys to `scoring/scorer.py` `WEIGHTS` if the scenario uses different confidence factors

### StructureContext Key Properties

| Property | Returns |
|----------|---------|
| `trend` | `"bullish"` / `"bearish"` / `"neutral"` — prefers external labels |
| `last_bos` | Most recent BOS event (internal or external) |
| `last_external_bos` | Most recent `structure_kind="external"` BOS |
| `last_internal_bos` | Most recent `structure_kind="internal"` BOS |
| `last_choch` | Most recent CHoCH (always external) |
| `active_fvgs` | FVGs not yet touched at midpoint |

BOS events carry `displacement: bool` — set when the breaking candle was a displacement bar.

## Configuration

`config/settings.yaml`:
- `timeframes.htf`: `["1h"]` — `htf_pullback_continuation` hard-checks `htf == "1h"`
- `timeframes.ltf`: `["5m"]` — same, hard-checks `ltf == "5m"`
- `scoring.min_score`: `65`, `min_rr_ratio`: `2.0`
- `scenarios.enabled`: `["htf_pullback_continuation"]`

Secrets go in `.env`: Binance API keys, Telegram bot token, Discord webhook URL, SMTP credentials.
