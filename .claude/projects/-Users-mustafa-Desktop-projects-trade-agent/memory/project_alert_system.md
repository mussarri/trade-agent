---
name: alert_system_implementation
description: v2.0 ICT alert system — 3 scenarios, HTF hard filter, confluence merge, new scoring
type: project
---

Alert system v2.0 uygulandı (alert.md spesifikasyonuna göre).

**Aktif senaryolar (3 adet):**
- `bos_continuation` → alert_type: BOS_CONTINUATION
- `fvg_retrace` → alert_type: SMART_MONEY_ENTRY (eski: fvg_retrace_continuation)
- `liquidity_sweep` → alert_type: LIQUIDITY_SWEEP (eski: liquidity_sweep_reversal)

**Silinen senaryolar:** choch_confirmation, order_block_reaction, range_liquidity_expansion, double_liquidity_sweep, fvg_retrace_continuation, liquidity_sweep_reversal

**Önemli değişiklikler:**
- Scoring: 5 faktör, yeni ağırlıklar (htf:30, fvg:25, vol:20, liq:15, session:10)
- MIN_SCORE: 55 → 65, MIN_RR: 2.0 → 2.5
- Pipeline: HTF neutral → hard filter (return []), per-symbol cooldown (5 dk)
- Confluence merge: aynı sembol+yön → en yüksek score, OR'lanmış faktörler
- ICT bonus: fvg_retrace senaryosu setup.meta["ict_bonus"] ile yönetiyor
- current_session(): "asian"/"london"/"overlap"/"new_york"/"off"
- AlertPayload: htf_trend, session, pair, scenario_detail alanları eklendi
- Telegram format: yeni spec (emoji + sembol + factor checkboxları)
- API: /api/setups (progress_pct ile), /api/market/{symbol} yeni eklendi

**Why:** alert.md v2.0 spec — trend continuation odaklı, daha az ama doğru sinyal

**How to apply:** Yeni senaryo eklerken sadece 5 confidence factor kullan. HTF alignment kontrolü pipeline'da yapılıyor, senaryolarda tekrar yapma.
