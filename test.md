# Test & Debug Prompt — trade-agent
> Claude Code için | Sırayla uygula | Her adımı doğrula

---

## Acil Sorun: Context Boş

Engine live modda çalışıyor ama `engine.contexts = {}`.
WebSocket bağlantısı kurulmuyor veya veri gelmiyor.
Önce bunu düzelt, sonra testleri yaz.

---

## Adım 1: Root Cause Bul ve Düzelt

Şu komutları çalıştır, çıktıları analiz et:

```bash
# Engine logları
docker logs trade-agent-engine --tail=50 2>&1

# ccxt.pro kurulu mu?
docker exec trade-agent-engine python3 -c "import ccxt.pro; print('OK')"

# Binance erişimi var mı?
docker exec trade-agent-engine python3 -c "
import urllib.request
try:
    urllib.request.urlopen('https://api.binance.com/api/v3/ping', timeout=5)
    print('Binance OK')
except Exception as e:
    print('HATA:', e)
"

# ENGINE_MODE ve run_live çağrısı nerede?
docker exec trade-agent-engine grep -n "ENGINE_MODE\|run_live\|seed_demo\|on_candle_closed" /app/main.py /app/api/server.py

# Engine kodunu gör
docker exec trade-agent-engine cat /app/core/engine.py
```

Çıktılara göre sorunu tespit et ve düzelt.

**Doğrulama — bu çıktıyı görene kadar Adım 1'den çıkma:**

```bash
docker exec trade-agent-engine python3 -c "
from main import engine
print('contexts:', len(engine.contexts))
for k, ctx in list(engine.contexts.items())[:2]:
    print(k, 'candles:', len(ctx.candles), 'trend:', ctx.trend)
"
```

`contexts > 0` olana kadar devam et.

---

## Adım 2: Fixture Üretici Yaz

`tests/fixtures/make_candles.py` dosyasını oluştur.

**Fonksiyon imzası:**

```python
def make_candles(
    n: int,
    start_price: float = 100.0,
    pattern: str = "trending_up",
    symbol: str = "BTC/USDT",
    timeframe: str = "15m",
) -> list[Candle]:
```

**Pattern'lar ve davranışları:**

`trending_up`
Net HH/HL dizisi üretir. Her 5 mumda bir swing high/low oluşur.
Swing'ler giderek yükselir. ATR küçük, gürültü az.
Sonuçta `market_direction` → `"bullish"` döndürmeli.

`trending_down`
Net LH/LL dizisi. `trending_up`'ın tersi.
`market_direction` → `"bearish"` döndürmeli.

`ranging`
`start_price ± %1` bandında gidip gelir.
Swing'ler oluşur ama net yön yoktur.
`market_direction` → `"neutral"` döndürmeli.

`fvg_up`
`trending_up` bazında başlar.
Ortasında büyük bullish displacement mumu ekler (`body = ATR * 3`).
Displacement sonrası gap kalır (`c1.high < c3.low`).
`detect_fvg` → `"long"` FVG döndürmeli.

`fvg_down`
`trending_down` bazında başlar.
Büyük bearish displacement mumu ekler.
`detect_fvg` → `"short"` FVG döndürmeli.

`sweep_down`
`ranging` bazında başlar.
Equal low oluşturur (iki ardışık swing low aynı seviyede ±%0.1).
Son mumda wick equal low seviyesinin altına iner, close üstünde kapanır.
`detect_sweep` → `"equal_low"` zone döndürmeli.

`sweep_up`
`ranging` bazında başlar.
Equal high oluşturur.
Son mumda wick equal high seviyesinin üstüne çıkar, close altında kapanır.
`detect_sweep` → `"equal_high"` zone döndürmeli.

**Tüm pattern'larda:**
- `timestamp`: şimdiden geriye doğru, timeframe'e göre adım adım
- `volume`: 100–500 arası, spike pattern'larda 3x artış
- `is_closed`: `True`

---

## Adım 3: Senaryo Testleri Yaz

**Ortak helper — tüm test dosyalarında kullan:**

```python
from core.context import StructureContext
from tests.fixtures.make_candles import make_candles

def build_ctx(candles, symbol="BTC/USDT", timeframe="15m") -> StructureContext:
    ctx = StructureContext(symbol=symbol, timeframe=timeframe)
    for c in candles:
        ctx.update(c)
    return ctx
```

---

### `tests/test_bos_continuation.py`

```
TestBOSContinuation
│
├── test_long_setup_bullish_htf
│   htf = trending_up 50 mum (1h)
│   ltf = trending_up 30 mum (5m)
│   assert htf.trend == "bullish"
│   setup = detect_setup(htf, ltf)
│   assert setup is not None
│   assert setup.direction == "long"
│
├── test_no_setup_wrong_direction
│   htf = trending_down 50 mum
│   ltf = trending_up 30 mum
│   setup = detect_setup(htf, ltf)
│   assert setup is None
│
├── test_short_setup_bearish_htf
│   htf = trending_down 50 mum
│   ltf = trending_down 30 mum
│   setup = detect_setup(htf, ltf)
│   assert setup is not None
│   assert setup.direction == "short"
│
├── test_trigger_close_confirm
│   htf = trending_up 50 mum
│   ltf = trending_up 50 mum
│   setup = detect_setup(htf, ltf)
│   assert setup is not None
│   # watch bölgesi ortasına 5 mum ekle
│   extra = make_candles(5,
│       start_price=(setup.watch_low + setup.watch_high) / 2,
│       pattern="trending_up", timeframe="5m")
│   for c in extra: ltf.update(c)
│   trigger = detect_trigger(setup, ltf)
│   assert trigger is not None
│
├── test_invalidation_by_level
│   setup oluştuktan sonra invalidation_level altına düş
│   assert is_invalidated(setup, ltf) is True
│
└── test_invalidation_by_timeout
    setup.candles_elapsed = setup.timeout_candles
    assert is_invalidated(setup, ltf) is True
```

---

### `tests/test_fvg_retrace.py`

```
TestFVGRetrace
│
├── test_setup_with_displacement
│   htf = trending_up 50 mum (1h)
│   ltf = fvg_up 40 mum (5m)
│   assert len(ltf.active_fvgs) > 0
│   setup = detect_setup(htf, ltf)
│   assert setup is not None
│
├── test_no_setup_without_displacement
│   htf = trending_up 50 mum
│   ltf = ranging 30 mum (FVG yok)
│   setup = detect_setup(htf, ltf)
│   assert setup is None
│
├── test_wrong_direction_fvg_ignored
│   htf = trending_up (bullish)
│   ltf = fvg_down (bearish FVG)
│   setup = detect_setup(htf, ltf)
│   assert setup is None
│
└── test_ict_bonus_when_sweep_before_fvg
    htf = trending_up
    ltf = sweep_down 30 mum başlangıç
    sonra üstüne fvg_up 20 mum ekle
    setup = detect_setup(htf, ltf)
    if setup:
        assert setup.meta.get("ict_bonus") is True
```

---

### `tests/test_liquidity_sweep.py`

```
TestLiquiditySweep
│
├── test_equal_low_setup_bullish_htf
│   htf = trending_up
│   ltf = sweep_down (equal low var, sweep oldu)
│   setup = detect_setup(htf, ltf)
│   assert setup is not None
│   assert setup.direction == "long"
│
├── test_no_equal_high_setup_when_bullish
│   htf = trending_up
│   ltf = sweep_up (equal high var)
│   setup = detect_setup(htf, ltf)
│   assert setup is None   # bullish trendde equal high sweep arama
│
├── test_sweep_reversal_trigger
│   sweep_down pattern → setup oluştur
│   sweep mumu ekle: wick < zone.level, close > zone.level
│   trigger = detect_trigger(setup, ltf)
│   assert trigger is not None
│   assert trigger.condition.kind == "sweep_reversal"
│
└── test_no_trigger_without_sweep
    Equal low var ama sweep gerçekleşmedi
    trigger = detect_trigger(setup, ltf)
    assert trigger is None
```

---

### `tests/test_pipeline.py`

**Pipeline kurulumu:**

```python
import asyncio
from datetime import datetime, timezone
from core.pipeline import Pipeline
from risk.planner import RiskPlanner

pipeline = Pipeline(
    min_score=65,
    min_rr_ratio=2.5,
    risk_planner=RiskPlanner(
        risk_per_trade_pct=1.0,
        atr_sl_multiplier=0.5,
    ),
    enabled_scenarios=["bos_continuation", "fvg_retrace", "liquidity_sweep"],
    cooldown_minutes=0,   # test için kapalı
)
```

```
TestPipeline
│
├── test_htf_neutral_score_penalty
│   htf = ranging (neutral)
│   ltf = trending_up
│   result = asyncio.run(pipeline.run(htf, ltf))
│   # Gelen sinyaller penalty sonrası 65'i geçmiş olmalı
│   for p in result:
│       assert p.score >= 65
│
├── test_htf_bearish_no_long
│   htf = trending_down
│   ltf = trending_up
│   result = asyncio.run(pipeline.run(htf, ltf))
│   assert all(p.direction != "LONG" for p in result)
│
├── test_confluence_merge
│   htf = trending_up
│   ltf = fvg_up (hem BOS hem FVG aynı bölgede)
│   result = asyncio.run(pipeline.run(htf, ltf))
│   long_signals = [p for p in result if p.direction == "LONG"]
│   assert len(long_signals) <= 1
│
└── test_cooldown_blocks_second_signal
    pipeline.cooldown_minutes = 5
    pipeline.alert_cooldowns["BTC/USDT"] = datetime.now(timezone.utc)
    htf = trending_up
    ltf = trending_up
    result = asyncio.run(pipeline.run(htf, ltf))
    assert len(result) == 0
```

---

### `tests/test_scorer.py`

`WEIGHTS` ve `ICT_FULL_SETUP_BONUS` değerlerini `scoring/scorer.py`'den import et.

```
TestScorer
│
├── test_all_factors_max_score
│   Tüm faktörler True → score == 100
│
├── test_only_htf_alignment
│   Sadece htf_alignment True → score == 30
│
├── test_ict_bonus_adds_to_score
│   htf_alignment + fvg_or_ob_presence True (30+25=55)
│   ict_bonus True → 55+15 = 70
│
├── test_ict_bonus_capped_at_100
│   Tüm faktörler True (100) + ict_bonus → hâlâ 100
│
└── test_neutral_penalty
    Normal score 80 → neutral penalty → int(80 * 0.7) == 56
    56 < 65 → min_score filtresi geçemez
```

---

## Adım 4: Testleri Çalıştır ve Düzelt

```bash
# Tüm testler
docker exec trade-agent-engine python3 -m pytest tests/ -v --tb=short 2>&1

# Tek dosya — hata varsa detay için
docker exec trade-agent-engine python3 -m pytest tests/test_bos_continuation.py -v --tb=long 2>&1
```

**Başarısız test varsa:**
1. Hata mesajını oku
2. İlgili senaryo veya pipeline kodunu düzelt
3. Testi tekrar çalıştır
4. Tüm testler yeşil olana kadar devam et

**Başarı kriteri:**

```
tests/test_bos_continuation.py  →  6/6 passed
tests/test_fvg_retrace.py       →  4/4 passed
tests/test_liquidity_sweep.py   →  4/4 passed
tests/test_pipeline.py          →  4/4 passed
tests/test_scorer.py            →  5/5 passed
```

---

## Adım 5: Entegrasyon Doğrulama

Testler geçtikten sonra sistem bütününü doğrula:

```bash
# Context dolu mu?
docker exec trade-agent-engine python3 -c "
from main import engine
print('contexts:', len(engine.contexts))
for k, ctx in engine.contexts.items():
    print(k, '| candles:', len(ctx.candles), '| trend:', ctx.trend, '| bos:', ctx.last_bos)
"

# Aktif setup'lar
curl http://localhost:8000/api/setups | python3 -m json.tool

# Tetiklenen sinyaller
curl http://localhost:8000/api/signals | python3 -m json.tool

# Sembol bazlı market durumu
curl http://localhost:8000/api/market/BTCUSDT | python3 -m json.tool
curl http://localhost:8000/api/market/ETHUSDT | python3 -m json.tool
curl http://localhost:8000/api/market/SOLUSDT | python3 -m json.tool
```

**Beklenen nihai durum:**

```
contexts       : 8  (4 sembol × 2 timeframe)
candles        : > 100 her context'te
trend          : bullish / bearish / neutral  (boş olmamalı)
active_fvgs    : > 0 (en az birinde)
liquidity_zones: > 0 (en az birinde)

/api/setups    : en az 1-2 aktif setup görünmeli
/api/signals   : trigger olan sinyaller listesi
/api/market    : htf_trend dolu, yapısal veriler mevcut
```


---

*trade-agent Test & Debug Prompt v1.0*