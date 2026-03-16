# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

**Trade-Agent** is an AI-powered cryptocurrency trading signal system using ICT (Inner Circle Trading) and Smart Money analysis. It monitors Binance markets in real-time, detects high-confidence setups via a two-stage pipeline, scores them with confluence factors, plans risk/reward levels, and dispatches alerts via Telegram, Discord, Email, and webhooks. A React dashboard visualizes active signals.

## Commands

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Run in demo mode (synthetic data, no API keys needed)
python main.py

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_scorer.py -v

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
  → StructureContext (market state)
  → SignalEngine.on_candle_closed()
  ↓
Pipeline:
  ├─ Stage 1: Scenario.detect_setup()   ← pattern forms
  ├─ Stage 2: Scenario.detect_trigger() ← entry confirmed
  ├─ Scorer [min_score=55, 6 weighted factors]
  ├─ RiskPlanner [entry / SL / TP1–3]
  └─ AlertPayload → Dispatch channels
  ↓
WebSocket → React dashboard
```

### Key Modules

| Module | Responsibility |
|--------|---------------|
| `core/engine.py` | Orchestrates multi-symbol/timeframe processing, demo and live modes |
| `core/pipeline.py` | Two-stage detection loop, cooldown management, ICT tracking |
| `core/context.py` | Market state machine — swings, BOS/CHoCH, FVGs, liquidity zones |
| `core/structure.py` | ICT technical calculations (swing detection, BOS, FVG, ranges) |
| `scenarios/` | Plugin-based trading patterns; add new ones here without touching core |
| `scoring/scorer.py` | Confluence scoring: 6 weighted factors + ICT bonus (+15), min score 55 |
| `risk/planner.py` | Entry/SL/TP generation, R:R enforcement (min 2.0), position sizing |
| `alerts/` | Multi-channel dispatch — Telegram, Discord, Email, HTTP webhooks |
| `api/server.py` | FastAPI REST endpoints + WebSocket for dashboard |
| `config/` | Pydantic-based settings loaded from `config/settings.yaml` + `.env` |

### Design Patterns

- **Two-stage detection**: Setup forms first, then trigger confirms — reduces false positives.
- **Plugin scenarios**: Drop a new file in `scenarios/` and it's auto-loaded.
- **State machine**: `StructureContext` holds all derived market data, updated per closed candle.
- **Async pipeline**: Each symbol runs independently via `asyncio`; no shared mutable state between symbols.
- **Risk-first levels**: Entry, SL, and all TPs are derived from market structure — never arbitrary.

## Configuration

`config/settings.yaml` — key defaults:
- `symbols`: `["BTC/USDT", "ETH/USDT"]`
- `timeframes`: HTF=`4h`, LTF=`15m`
- `scoring.min_score`: `55`, `min_rr_ratio`: `2.0`
- `risk.risk_per_trade_pct`: `1.0`, `atr_sl_multiplier`: `0.5`
- `alert_cooldown`: 60 min per symbol/scenario

Secrets go in `.env`: Binance API keys, Telegram bot token, Discord webhook URL, SMTP credentials.
