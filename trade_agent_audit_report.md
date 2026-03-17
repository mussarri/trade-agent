### 🔍 Scenario Interpretation
`Trade-Agent` currently implements 3 live scenarios, and all 3 are mostly internal-structure pattern detectors, not full ICT execution models.

`bos_continuation`
- Detects: latest LTF close break of last swing (`last_bos`) + pullback zone between that BOS level and last swing extreme.
- Actual market type: mostly `INTERNAL BOS pullback`, not guaranteed external BOS continuation.
- Not detecting: liquidity sweep as prerequisite, CHoCH reversal, range breakout.
- Naming accuracy: partially accurate, but overstated.

`fvg_retrace`
- Detects: active same-direction FVG + loose “displacement” check + candle interaction with FVG bounds.
- Actual market type: FVG touch continuation/reaction, often early.
- Not detecting: true CHoCH reversal or range breakout logic.
- Naming accuracy: `fvg_retrace` is okay; `SMART_MONEY_ENTRY` alert name is too broad.

`liquidity_sweep`
- Detects: equal-level zone wick-through + close back over/under zone.
- Actual market type: liquidity sweep reversal attempt (closest to ICT concept among 3).
- Not detecting: required MSS/BOS after sweep before entry.
- Naming accuracy: mostly accurate.

---

### ⚙️ System Behavior
- BOS is close > last swing high / close < last swing low only, from very short swing logic (`lookback=2`), so internal breaks are treated as BOS ([context.py:126](/Users/mustafa/Desktop/projects/trade-agent/core/context.py:126), [structure.py:17](/Users/mustafa/Desktop/projects/trade-agent/core/structure.py:17)).
- CHoCH is derived from trend vote heuristic (last labels, 60% threshold), so noisy trend flips can create false CHoCH flags ([structure.py:51](/Users/mustafa/Desktop/projects/trade-agent/core/structure.py:51), [context.py:132](/Users/mustafa/Desktop/projects/trade-agent/core/context.py:132)).
- Trigger timing is candle-close based only; there is no “first touch only”, no zone freshness decay, no prior-outside→inside transition requirement.
- FVG trigger condition is overly permissive (`low <= zone_high and close >= zone_low` for long), which can fire before meaningful retrace completion ([fvg_retrace.py:90](/Users/mustafa/Desktop/projects/trade-agent/scenarios/fvg_retrace.py:90)).
- Session/volume/liquidity are only score factors, not hard gating.
- Critical pipeline defects:
  - `min_rr_ratio=2.5`, but risk fallback TP1 is 2R, so most/all trades are filtered out ([scoring.py:16](/Users/mustafa/Desktop/projects/trade-agent/scoring/scorer.py:16), [planner.py:60](/Users/mustafa/Desktop/projects/trade-agent/risk/planner.py:60), [pipeline.py:195](/Users/mustafa/Desktop/projects/trade-agent/core/pipeline.py:195)).
  - Alerts are dispatched with `AlertPayload` object, while alert formatters expect dict (`payload.get`), causing runtime failures in formatters ([pipeline.py:223](/Users/mustafa/Desktop/projects/trade-agent/core/pipeline.py:223), [telegram.py:23](/Users/mustafa/Desktop/projects/trade-agent/alerts/telegram.py:23)).
  - Produced signals are never added to `SignalStore`; lifecycle tracking can’t work ([pipeline.py:26](/Users/mustafa/Desktop/projects/trade-agent/core/pipeline.py:26), [pipeline.py:136](/Users/mustafa/Desktop/projects/trade-agent/core/pipeline.py:136)).

---

### ❌ Issues Found
- No external/internal structure separation, so BOS quality is low.
- BOS events can duplicate repeatedly on same broken level across candles (no dedupe guard) ([context.py:130](/Users/mustafa/Desktop/projects/trade-agent/core/context.py:130)).
- `fvg_retrace` and `liquidity_sweep` force short when HTF is neutral (`else "short"`), introducing bearish bias ([fvg_retrace.py:21](/Users/mustafa/Desktop/projects/trade-agent/scenarios/fvg_retrace.py:21), [liquidity_sweep.py:21](/Users/mustafa/Desktop/projects/trade-agent/scenarios/liquidity_sweep.py:21)).
- No true range-breakout scenario exists despite architecture claims.
- No true CHoCH-based trade scenario exists.
- “OB presence” is scored, but OB is never computed.
- Symbol-level cooldown blocks all scenarios for same symbol (too coarse for multi-setup engines) ([pipeline.py:93](/Users/mustafa/Desktop/projects/trade-agent/core/pipeline.py:93)).
- Confidence model is static boolean weights; no distance-to-zone, impulse size, or excursion metrics.

---

### ⚠️ Risk Problems
- SL/invalidations are inconsistent between setup and risk plan.
- Entry uses zone midpoint, not actual trigger fill assumption.
- TP1/TP2 mostly synthetic R-multiples, not real liquidity targets (pipeline never passes liquidity arrays to planner).
- With current defaults, RR filter likely suppresses nearly all signals.
- No volatility regime filter beyond ATR existence.
- No spread/slippage buffer, no funding/news risk adaptation.

---

### 🧠 Correct Label
`BOS_CONTINUATION`
- Should be: `INTERNAL_BOS_PULLBACK` unless external swing break + displacement + continuation confirmation are present.

`SMART_MONEY_ENTRY` (for `fvg_retrace`)
- Should be: `FVG_RETRACE_REACTION` (not “smart money” by default).

`LIQUIDITY_SWEEP`
- Should be: `LIQUIDITY_SWEEP_REVERSAL_ATTEMPT` unless followed by MSS/BOS confirmation.

---

### 🚀 Improvements
1. Structure engine upgrade
- Add dual swing layers: `internal` (lookback 2-3) and `external` (lookback 8-20).
- BOS validity rule: close beyond external swing by min `0.15*ATR` and body ratio threshold.
- CHoCH validity rule: opposite-side liquidity take + MSS close + displacement.

2. Setup/trigger timing hardening
- Add zone state: `fresh`, `tapped`, `consumed`.
- Trigger only on first valid re-entry after setup timestamp.
- Require previous candle outside zone and trigger candle inside zone.
- Add expiry by zone age and by distance traveled after setup.

3. Scenario-specific fixes
- `fvg_retrace`: reject neutral HTF; require displacement candle linked to the same FVG; require retrace depth (e.g., 50%+ into FVG).
- `bos_continuation`: require prior liquidity sweep or imbalance origin before pullback.
- `liquidity_sweep`: require post-sweep MSS/BOS confirmation before entry.

4. Risk model correction
- Pass real liquidity levels from context into planner.
- Compute TP1 on nearest opposing liquidity pool, TP2 on external swing, TP3 on HTF objective.
- Harmonize `min_rr_ratio` with target logic (either lower threshold to 2.0 or raise TP1 policy).
- Use trigger price or executable zone edge, not always midpoint.

5. Pipeline/alert reliability fixes
- Convert payload to dict before dispatch (`payload.model_dump(...)`).
- Add `self.signal_store.add(payload)` after production.
- Call `_check_active_signals` every LTF close.
- Change cooldown key to `(symbol, scenario, direction)`.

6. Filters for institutional-grade precision
- Session hard gate (London/NY) for selected scenarios, not only score bonus.
- Volatility regime filter: ATR percentile and candle spread filter.
- Noise filter: minimum displacement efficiency (`net move / total range`).
- Add “already moved” filter: skip if price has delivered >X ATR from entry zone before trigger.

Validation note: I ran local tests with `python3 -m pytest ...` and all 24 passed; these are architectural/logic precision issues not currently covered by tests.
