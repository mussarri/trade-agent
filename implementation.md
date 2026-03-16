# Signal Engine — Implementation Plan v1.0
> Modüler Kripto Sinyal Sistemi | Binance | Multi-Timeframe | Telegram + E-posta

---

## İçindekiler

1. [Genel Mimari](#1-genel-mimari)
2. [Technology Stack](#2-technology-stack)
3. [Proje Klasör Yapısı](#3-proje-klasör-yapısı)
4. [Katman Detayları](#4-katman-detayları)
5. [Multi-Timeframe Stratejisi](#5-multi-timeframe-stratejisi)
6. [Konfigürasyon](#6-konfigürasyon)
7. [Dashboard UI](#7-dashboard-ui)
8. [Docker & Deployment](#8-docker--deployment)
9. [Implementation Roadmap](#9-implementation-roadmap)
10. [Genişleme Yol Haritası](#10-genişleme-yol-haritası)

---

## 1. Genel Mimari

Sistem altı bağımsız katmandan oluşur. Her katman kendi sorumluluğuna sahiptir; katmanlar arası iletişim standart arayüzler üzerinden gerçekleşir. Bu yaklaşım yeni senaryo eklemeyi, alert kanalı değiştirmeyi veya veri kaynağı geçişini minimal kod değişikliğiyle mümkün kılar.

```
┌─────────────────────────────────────────────────────────┐
│                     SIGNAL ENGINE                        │
├──────────────┬──────────────────────────────────────────┤
│  DATA LAYER  │  Binance WS + REST  →  Candle[]          │
├──────────────┼──────────────────────────────────────────┤
│  STRUCTURE   │  Swing H/L, BOS, CHoCH, FVG, Liquidity  │
├──────────────┼──────────────────────────────────────────┤
│  SCENARIO    │  Plugin Registry  →  ScenarioMatch[]     │
├──────────────┼──────────────────────────────────────────┤
│  SCORING     │  Confluence Factors  →  Score 0-100      │
├──────────────┼──────────────────────────────────────────┤
│  RISK        │  Entry / SL / TP1 / TP2 / R:R            │
├──────────────┼──────────────────────────────────────────┤
│  ALERT + UI  │  Telegram  |  E-posta  |  Dashboard      │
└──────────────┴──────────────────────────────────────────┘
```

### 1.1 Veri Akışı

Her sembol/timeframe çifti bağımsız bir pipeline olarak çalışır. HTF (4H, 1D) yapısal bağlamı sağlar; LTF (15m, 1H) entry tetikleyicilerini üretir.

```
BTC/USDT  ─┬─  4H  DataFeed  →  HTF StructureContext  ─┐
           │                                              ├─  Scorer  →  Alert
           └─  15m DataFeed  →  LTF StructureContext  ─┘
```

---

## 2. Technology Stack

| Katman | Teknoloji | Neden? |
|---|---|---|
| Veri | `ccxt` + `websockets` | Binance REST & WS tek kütüphane |
| Core Engine | Python 3.11+ / `asyncio` | Async pipeline, yüksek throughput |
| Senaryo Loader | `importlib` (plugin) | Sıfır config ile hot-plug senaryo |
| Veri Modeli | `pydantic` v2 | Tip güvenliği + validasyon |
| API | `FastAPI` + WebSocket | Dashboard'a realtime push |
| UI | React + TailwindCSS | Hızlı bileşen geliştirme |
| Telegram Alert | `python-telegram-bot` | Zengin mesaj + grafik desteği |
| E-posta Alert | `smtplib` / `sendgrid` | HTML template desteği |
| Config | `pydantic-settings` + YAML | Ortam değişkeni + dosya birleşimi |
| Test | `pytest` + `pytest-asyncio` | Async pipeline testleri |
| Backtest Stub | `pandas` + fixture candles | Gerçek senaryoları geçmiş veriyle test |
| Container | Docker + Docker Compose | Tek komutla deploy |
| Reverse Proxy | Nginx (opsiyonel) | HTTPS + dashboard routing |

---

## 3. Proje Klasör Yapısı

```
signal-engine/
├── core/
│   ├── candle.py             # Candle veri modeli (pydantic)
│   ├── data_feed.py          # CCXT WS + REST feed yöneticisi
│   ├── structure.py          # Swing H/L, BOS, CHoCH, FVG hesaplamaları
│   └── context.py            # StructureContext: canlı durum objesi
│
├── scenarios/
│   ├── base.py               # BaseScenario ABC + ScenarioMatch modeli
│   ├── liquidity_sweep.py    # EQH/EQL sweep + reversal sinyali
│   ├── bos_retest.py         # BOS sonrası geri test
│   ├── fvg_fill.py           # Fair Value Gap dolumu
│   ├── choch_confirm.py      # CHoCH + hacim konfirmasyonu
│   └── ssob_reaction.py      # SSL/BSL sweep + OB reaksiyon
│
├── scoring/
│   └── scorer.py             # Confluence faktör ağırlıklı skor motoru
│
├── risk/
│   └── planner.py            # Entry, SL, TP1/TP2/TP3, R:R hesabı
│
├── alerts/
│   ├── base.py               # BaseAlert ABC
│   ├── telegram.py           # Telegram Bot gönderici
│   └── email_alert.py        # SMTP / SendGrid gönderici
│
├── api/
│   └── server.py             # FastAPI REST + WebSocket endpoint'leri
│
├── ui/
│   └── dashboard/            # React frontend (Vite)
│       ├── src/
│       ├── public/
│       └── package.json
│
├── config/
│   ├── settings.py           # pydantic-settings ana config
│   └── settings.yaml         # Kullanıcı konfigürasyonu
│
├── tests/
│   ├── fixtures/             # Fixture mum verileri (JSON)
│   ├── test_structure.py
│   ├── test_scenarios.py
│   └── test_scorer.py
│
├── backtest/
│   └── runner.py             # Stub: geçmiş veri üzerinde senaryo koşucu
│
├── docker/
│   ├── Dockerfile            # Ana uygulama image
│   ├── Dockerfile.ui         # React frontend image
│   └── nginx.conf            # Reverse proxy config
│
├── docker-compose.yml        # Tam stack tanımı
├── docker-compose.dev.yml    # Geliştirme override
├── .env.example              # Ortam değişkeni şablonu
├── main.py                   # Giriş noktası
└── pyproject.toml
```

---

## 4. Katman Detayları

### 4.1 Data Layer

Her sembol/timeframe çifti için bağımsız bir `DataFeed` instance çalışır. Feed hem geçmiş mum yükler (REST) hem canlı kapanışları dinler (WebSocket). Yeni mum kapandığında `StructureContext`'i günceller ve pipeline'ı tetikler.

```python
# core/candle.py
from pydantic import BaseModel
from datetime import datetime

class Candle(BaseModel):
    symbol: str
    timeframe: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    is_closed: bool = False
```

```python
# core/data_feed.py  (özet)
class DataFeed:
    def __init__(self, symbol: str, timeframe: str, exchange: ccxt.Exchange):
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        self.context = StructureContext(symbol, timeframe)

    async def start(self):
        await self._load_history()     # REST ile geçmiş mumlar
        await self._stream_live()      # WS ile canlı kapanışlar

    async def _on_candle_closed(self, candle: Candle):
        self.context.update(candle)    # Yapıyı güncelle
        await pipeline.run(self.context)  # Pipeline'ı tetikle
```

> **Not:** CCXT farklı borsalardan gelen ham veriyi standart formata çevirir. Timestamp hassasiyeti ve hacim birimleri borsa bazında farklılık gösterebilir. `Candle` modeli bu farkları soyutlar.

---

### 4.2 Structure Engine

Ham mumlardan anlamlı yapısal bilgi üretir. Her yeni kapanış mumunda `StructureContext` güncellenir.

**Hesaplanan elemanlar:**

| Eleman | Açıklama |
|---|---|
| Swing High / Low | Parametrik lookback (varsayılan: 5 mum her yön) |
| Market Structure | HH / HL / LH / LL etiket dizisi |
| BOS | Break of Structure — son swing'in kırılma tespiti |
| CHoCH | Change of Character — yapı yön değişikliği |
| FVG | 3 mumlu imbalance tespit ve aktif takibi |
| Liquidity | Equal highs/lows (ATR toleransı ile) |
| Order Block | BOS/CHoCH öncesi son karşı mum |

> **Tasarım Kararı — Stateful Context:** `StructureContext` stateless değildir. Her sembol/timeframe için hafızada tutulur ve artımlı güncellenir. Bu yaklaşım her mumda tüm geçmişi yeniden hesaplamayı önler; ölçeklenebilirliği artırır.

---

### 4.3 Scenario Registry — Plugin Mimarisi

Projenin en kritik katmanı. Her senaryo `BaseScenario`'yu implement eden bağımsız bir sınıftır. Uygulama başlarken `scenarios/` klasöründeki tüm `.py` dosyaları otomatik yüklenir.

```python
# scenarios/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Literal
from datetime import datetime

class ScenarioMatch(BaseModel):
    scenario_name: str
    symbol: str
    timeframe: str
    direction: Literal['long', 'short']
    confidence_factors: dict[str, bool]
    key_levels: dict[str, float]   # entry_zone_low/high, swing_high, swing_low, fvg_mid
    timestamp: datetime

class BaseScenario(ABC):
    name: str
    required_timeframes: list[str]

    @abstractmethod
    def matches(
        self,
        htf_ctx: StructureContext,
        ltf_ctx: StructureContext
    ) -> ScenarioMatch | None:
        ...
```

**Plugin Loader:**

```python
# scenarios/__init__.py
import importlib
import pkgutil
from pathlib import Path

def load_all_scenarios() -> list[BaseScenario]:
    scenarios = []
    pkg_path = Path(__file__).parent
    for _, module_name, _ in pkgutil.iter_modules([str(pkg_path)]):
        if module_name == "base":
            continue
        module = importlib.import_module(f"scenarios.{module_name}")
        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, BaseScenario) and attr is not BaseScenario:
                scenarios.append(attr())
    return scenarios
```

**Önceden Tanımlı Senaryolar:**

| Senaryo | Dosya | Tetikleyici Koşul | Yön |
|---|---|---|---|
| Liquidity Sweep | `liquidity_sweep.py` | EQH/EQL alındı + wick + close geri | Her ikisi |
| BOS Retest | `bos_retest.py` | Swing kırıldı, fiyat OB'ye döndü | Her ikisi |
| FVG Fill | `fvg_fill.py` | Fiyat FVG bölgesine girdi + tepki | Her ikisi |
| CHoCH Confirm | `choch_confirm.py` | CHoCH + hacim spike konfirm | Her ikisi |
| SSOB Reaction | `ssob_reaction.py` | SSL/BSL sweep + OB'de engulfing | Her ikisi |

---

### 4.4 Scoring Engine

Her `ScenarioMatch` için 0–100 arası normalize edilmiş bir skor hesaplanır. Eşik altındaki sinyaller (varsayılan: **55**) pipeline'dan çıkarılır.

| Confluence Faktörü | Ağırlık | Açıklama |
|---|---|---|
| HTF Trend Alignment | +25 | HTF yapısı LTF yönünü destekliyor |
| OB / FVG Confluence | +25 | Entry bölgesi OB ve FVG ile örtüşüyor |
| Volume Confirmation | +20 | Tetikleyici mumda hacim spike'ı |
| Session Overlap | +15 | London veya NY seansı açık |
| Clean Market Structure | +15 | Net swing dizisi, iç içe kırılma yok |

```python
# scoring/scorer.py  (özet)
WEIGHTS = {
    "htf_alignment":    25,
    "ob_fvg_confluence": 25,
    "volume_confirm":   20,
    "session_overlap":  15,
    "clean_structure":  15,
}

def score(match: ScenarioMatch) -> int:
    total = sum(
        WEIGHTS[k] for k, v in match.confidence_factors.items() if v
    )
    return min(total, 100)
```

> **Minimum R:R Filtresi:** Scorer'ın yanı sıra Risk Planner da filtre uygular. Hesaplanan R:R < 1:2 ise sinyal, skoru ne olursa olsun geçersiz sayılır.

---

### 4.5 Risk Planner

Skor eşiğini geçen her `ScenarioMatch` için otomatik risk planı üretir.

| Parametre | Hesaplama Yöntemi |
|---|---|
| Entry Zone | OB üst/alt sınırı veya FVG midpoint (±%0.1 tolerans) |
| Stop Loss | İlgili swing high/low + ATR(14) × 0.5 buffer |
| TP1 | En yakın liquidity seviyesi (min 1:1.5) |
| TP2 | Bir sonraki HTF swing (min 1:2.5) |
| TP3 | HTF yapısal hedef (1:4+) |
| R:R Oranı | `(TP1 - Entry) / (Entry - SL)`, min 1:2 zorunlu |
| Position Size | `risk_pct / (Entry - SL)`, ayarlanabilir |

```python
# risk/planner.py
class RiskPlan(BaseModel):
    entry_low: float
    entry_high: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    rr_ratio: float
    position_size_pct: float    # Hesap bakiyesinin yüzdesi
    invalidation_level: float   # Bu seviye kapanışta plan geçersiz
```

---

### 4.6 Alert Layer

Her alert kanalı `BaseAlert`'i implement eder. Sinyal üretildiğinde tüm aktif kanallar **paralel** olarak çağrılır.

**Telegram Alert Formatı:**

```
🚨 SIGNAL — BTC/USDT  |  LONG
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 Senaryo   : BOS Retest + FVG Confluence
⭐ Skor       : 85/100
📊 Timeframe : 4H (HTF) + 15m (Entry)

📍 Entry Zone : 42,150 – 42,380
🛑 Stop Loss  : 41,720  (-1.02%)
🎯 TP1        : 43,200  (+2.47%)  R:R 2.4
🎯 TP2        : 44,100  (+4.51%)  R:R 4.4
🎯 TP3        : 45,800  (+8.53%)  R:R 8.4

✅ HTF Alignment     ✅ Volume Confirm
✅ OB+FVG Confluence  ✅ London Session
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Invalidasyon: 41,500 altı kapanış
```

**E-posta Alert:**
- Anlık: her sinyal üretildiğinde HTML e-posta
- Günlük Özet: gün içindeki tüm sinyaller sabah 08:00 UTC'de tek e-posta

---

## 5. Multi-Timeframe Stratejisi

| Katman | Timeframe'ler | Görev |
|---|---|---|
| HTF (High TF) | 4H + 1D | Trend yönü, büyük yapı, HTF liquidity |
| LTF (Low TF) | 15m + 1H | Kesin entry, OB/FVG tetikleyici, CHoCH |
| Confluence | HTF + LTF birlikte | Her iki katman aynı yönde → sinyal geçerli |

Her senaryonun `matches()` metodu `htf_ctx` ve `ltf_ctx` olmak üzere iki ayrı `StructureContext` alır. Bu sayede senaryo mantığı timeframe konfigürasyonundan bağımsızdır.

---

## 6. Konfigürasyon

Tüm ayarlar `settings.yaml` üzerinden yönetilir. Hassas veriler (API key, token) `.env` dosyasından okunur.

```yaml
# config/settings.yaml

exchange:
  id: binance
  sandbox: false

symbols:
  - BTC/USDT
  - ETH/USDT
  - SOL/USDT
  - BNB/USDT
  - AVAX/USDT

timeframes:
  htf: ["4h", "1d"]
  ltf: ["15m", "1h"]

scoring:
  min_score: 55           # Bu altı sinyaller filtrelenir
  min_rr_ratio: 2.0

risk:
  risk_per_trade_pct: 1.0 # Hesap bakiyesinin %1'i
  atr_sl_multiplier: 0.5
  atr_period: 14

alerts:
  telegram:
    enabled: true
    # TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env'den okunur
  email:
    enabled: true
    daily_summary: true
    summary_hour: 8       # 08:00 UTC

scenarios:
  enabled:
    - liquidity_sweep
    - bos_retest
    - fvg_fill
    - choch_confirm
    - ssob_reaction
```

```bash
# .env.example
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET=your_secret_here

TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_USER=your@email.com
EMAIL_PASSWORD=your_app_password
EMAIL_TO=alerts@email.com

# Dashboard
API_HOST=0.0.0.0
API_PORT=8000
```

---

## 7. Dashboard UI

React + TailwindCSS tabanlı hafif web arayüzü. FastAPI'nin WebSocket endpoint'inden gerçek zamanlı güncelleme alır.

**Ekranlar:**
- **Aktif Sinyaller** — skor, senaryo adı, sembol, entry/SL/TP kartları
- **Senaryo İstatistikleri** — hangi senaryonun kaç sinyal ürettiği, ortalama skor
- **Sembol Özeti** — her pair için aktif sinyal ve son yapı durumu
- **Geçmiş Log** — son 50 sinyal, filtrelenebilir tablo
- **Backtest Görüntüleyici** — stub; fixture veri ile senaryo test sonuçları

**API Endpoint'leri:**

```
GET  /api/signals          # Aktif sinyaller listesi
GET  /api/signals/history  # Son 50 sinyal
GET  /api/stats            # Senaryo & sembol istatistikleri
WS   /ws                   # Gerçek zamanlı sinyal push
```

---

## 8. Docker & Deployment

### 8.1 Dockerfile — Ana Uygulama

```dockerfile
# docker/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Uygulama kodu
COPY . .

# Config dizini için volume mount noktası
VOLUME ["/app/config"]

EXPOSE 8000

CMD ["python", "main.py"]
```

### 8.2 Dockerfile — React UI

```dockerfile
# docker/Dockerfile.ui
FROM node:20-alpine AS builder

WORKDIR /app
COPY ui/dashboard/package*.json ./
RUN npm ci

COPY ui/dashboard/ .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

### 8.3 Nginx Config

```nginx
# docker/nginx.conf
server {
    listen 80;

    # React frontend
    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # FastAPI backend proxy
    location /api/ {
        proxy_pass http://engine:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket proxy
    location /ws {
        proxy_pass http://engine:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
}
```

### 8.4 docker-compose.yml — Production

```yaml
# docker-compose.yml
version: "3.9"

services:

  engine:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: signal-engine
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./config:/app/config:ro       # Config dosyaları read-only
      - engine-logs:/app/logs
    ports:
      - "8000:8000"                   # Doğrudan erişim için (opsiyonel)
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s

  ui:
    build:
      context: .
      dockerfile: docker/Dockerfile.ui
    container_name: signal-ui
    restart: unless-stopped
    ports:
      - "80:80"
    depends_on:
      engine:
        condition: service_healthy

volumes:
  engine-logs:
```

### 8.5 docker-compose.dev.yml — Geliştirme

Geliştirme ortamında kod değişiklikleri container'ı yeniden build etmeden anında yansır.

```yaml
# docker-compose.dev.yml
version: "3.9"

services:

  engine:
    build:
      context: .
      dockerfile: docker/Dockerfile
    container_name: signal-engine-dev
    env_file: .env
    volumes:
      - .:/app                        # Tüm kaynak kod mount edilir (hot reload)
      - ./config:/app/config
    ports:
      - "8000:8000"
    command: ["python", "-m", "uvicorn", "api.server:app", "--reload", "--host", "0.0.0.0"]

  ui-dev:
    image: node:20-alpine
    container_name: signal-ui-dev
    working_dir: /app
    volumes:
      - ./ui/dashboard:/app
    ports:
      - "5173:5173"                   # Vite dev server
    command: sh -c "npm install && npm run dev -- --host"
    depends_on:
      - engine
```

### 8.6 pyproject.toml

```toml
[project]
name = "signal-engine"
version = "1.0.0"
requires-python = ">=3.11"
dependencies = [
    "ccxt>=4.2.0",
    "websockets>=12.0",
    "pydantic>=2.6.0",
    "pydantic-settings>=2.2.0",
    "fastapi>=0.110.0",
      "uvicorn[standard]>=0.27.0",
    "python-telegram-bot>=21.0",
    "pandas>=2.2.0",
    "pyyaml>=6.0.1",
    "httpx>=0.27.0",
    "aiosmtplib>=3.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
]
```

### 8.7 Kurulum & Çalıştırma

#### İlk Kurulum

```bash
# 1. Repo'yu klonla
git clone https://github.com/your-org/signal-engine.git
cd signal-engine

# 2. Ortam değişkenlerini ayarla
cp .env.example .env
# .env dosyasını düzenle: API key, token, e-posta bilgileri

# 3. Config'i özelleştir (opsiyonel)
nano config/settings.yaml
```

#### Production — Tek Komutla Başlat

```bash
docker compose up -d
```

Servisler:
- Dashboard UI → `http://localhost`
- API → `http://localhost/api`
- WebSocket → `ws://localhost/ws`

#### Geliştirme Ortamı

```bash
# Hot-reload ile geliştirme
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Sadece engine (UI olmadan)
docker compose up engine
```

#### Faydalı Komutlar

```bash
# Logları takip et
docker compose logs -f engine

# Container'ın içine gir
docker compose exec engine bash

# Servisleri yeniden başlat
docker compose restart engine

# Tamamen temizle (volume dahil)
docker compose down -v

# Sadece image'ı rebuild et
docker compose build --no-cache engine
```

#### Sağlık Kontrolü

```bash
# API sağlık durumu
curl http://localhost:8000/health

# Aktif sinyaller
curl http://localhost:8000/api/signals

# Container durumları
docker compose ps
```

---

## 9. Implementation Roadmap

| Faz | Süre | Teslimables |
|---|---|---|
| **Faz 1 — Foundation** | 1–2 hafta | Candle model, DataFeed (REST+WS), StructureContext, temel yapı hesaplamaları |
| **Faz 2 — Scenarios** | 1–2 hafta | BaseScenario + plugin loader, 5 senaryo, fixture testleri |
| **Faz 3 — Scoring & Risk** | 3–5 gün | Scorer, RiskPlanner, R:R filtresi, pipeline entegrasyonu |
| **Faz 4 — Alerts** | 3–5 gün | Telegram bot, e-posta HTML template, günlük özet modu |
| **Faz 5 — API & UI** | 1 hafta | FastAPI server, WebSocket broadcast, React dashboard |
| **Faz 6 — Docker & Polish** | 3–5 gün | Dockerfile, Compose, entegrasyon testleri, loglama |

> **Not:** Faz 1–3 çalışır hale geldiğinde sistem terminale log basarak sinyal üretebilir. Her faz bir öncekine bağımlıdır.

---

## 10. Genişleme Yol Haritası

Mevcut mimari aşağıdaki genişlemeler için hazır tasarlanmıştır:

- **Yeni Senaryo** — `scenarios/` klasörüne dosya ekle, sistem otomatik yükler; başka hiçbir değişiklik gerekmez
- **Yeni Alert Kanalı** — `BaseAlert` implement et, `alerts/` klasörüne ekle, config'de `enabled: true`
- **Discord Alert** — `BaseAlert` implement edilerek dakikalar içinde eklenir
- **Yeni Exchange** — CCXT destekli her borsa `DataFeed` adapter ile entegre edilebilir
- **ML Skor Katmanı** — `Scorer`'ın faktör ağırlıkları geçmiş sinyal başarısından öğrenen bir model ile değiştirilebilir; senaryo arayüzü değişmez
- **Backtest Motoru** — `runner.py` stub'ı gerçek backtester'a dönüştürülebilir
- **Çoklu Exchange** — HTF tek borsadan, LTF başka borsadan okunabilir

---

## Tasarım Prensipleri

| Prensip | Açıklama |
|---|---|
| Modüler tasarım | Her katman bağımsız test edilebilir |
| Plugin senaryolar | Sıfır config ile genişletilebilir |
| Confluence odaklı | Tek faktör asla yeterli değil |
| Risk önce | R:R < 1:2 olan sinyaller üretilmez |
| Konfigürasyon merkezli | Kod değiştirmeden davranış değişir |
| Container-first | Tek komutla her ortamda çalışır |

---

*Signal Engine — Implementation Plan v1.0*
