# Headline-Reactor Quick Start Guide

## Installation (5 minutes)

### 1. Install Tesseract OCR
```powershell
winget install --id UB-Mannheim.TesseractOCR
```

### 2. Install headline-reactor
```powershell
cd C:\Users\sean\Documents\GitHub\headline-reactor
pip install -e .
```

### 3. Configure environment
Copy `.env.example` to `.env` and add your OpenAI key (optional):
```bash
OPENAI_API_KEY=sk-your-key-here
LLM_ENABLED=1
LLM_MODEL=gpt-4o-mini
```

---

## V2 System (Recommended)

### Test Single Headlines

**US Stock:**
```powershell
headline-reactor suggest-v2 "AAPL US APPLE BEATS EARNINGS"
# Output: AAPL BUY $2000 IOC TTL=10m
```

**Foreign Stock (Auto ADR):**
```powershell
headline-reactor suggest-v2 "AIR FP AIRBUS WINS MAJOR ORDER"
# Output: EADSY BUY $2000 IOC TTL=10m (US ADR)
#         EWQ BUY $2000 IOC TTL=10m (country ETF: FR)
```

**Korean Stock (Auto ETF):**
```powershell
headline-reactor suggest-v2 "005930 KS SAMSUNG BEATS EARNINGS"
# Output: SMH BUY $2000 IOC TTL=10m (sector sympathy: SEMIS)
#         EWY BUY $2000 IOC TTL=10m (country ETF: KR)
```

**Oil/Futures:**
```powershell
headline-reactor suggest-v2 "OPEC CUTS PRODUCTION WTI SURGES"
# Output: CLX4 BUY $2500 IOC TTL=10m (oil proxy)
```

**Crypto:**
```powershell
headline-reactor suggest-v2 "BITCOIN SURGES PAST 100K"
# Output: BITO BUY $1500 IOC TTL=10m (BTC proxy)
```

**M&A:**
```powershell
headline-reactor suggest-v2 "EA ELECTRONIC ARTS NEAR DEAL"
# Output: EA BUY $2000 IOC TTL=10m (NEWS: ma_rumor)
```

### Live Watch Mode

```powershell
headline-reactor watch-v2
```

**Output format:**
```
Watching 'Alert Catcher' (V2 universe-wide mode)... Ctrl+C to exit.

[NEWS] AAPL US APPLE ANNOUNCES NEW IPHONE
 -> AAPL BUY $2000 IOC TTL=10m (NEWS: macro_ambiguous)
 -> SMH BUY $2000 IOC TTL=10m (NEWS: macro_ambiguous)

[NEWS] 005930 KS SAMSUNG ELECTRONICS BEATS EARNINGS
 -> SMH BUY $2000 IOC TTL=10m (NEWS: macro_ambiguous)
 -> EWY BUY $2000 IOC TTL=10m (NEWS: macro_ambiguous)
```

---

## V1 System (Whitelist-Based)

```powershell
# V1 commands use explicit whitelist
headline-reactor suggest "SPAIN UPGRADED TO A BY FITCH"
headline-reactor watch
```

---

## Key Differences: V1 vs V2

| Feature | V1 | V2 |
|---------|----|----|
| **Whitelist** | Required | None (liquidity-based) |
| **Symbology** | Limited | Universal (any format) |
| **Foreign Stocks** | Manual mapping | Auto ADR/ETF resolution |
| **Asset Classes** | Equity, ETF | Equity, ETF, Futures, FX, Crypto, Options |
| **Proxy Logic** | Simple | Waterfall (ADR → Sector → Country → Futures) |
| **Configuration** | newsreactor.yml | universe_v2.yml |
| **Commands** | suggest, watch | suggest-v2, watch-v2 |

---

##  Configuration

### V2: `universe_v2.yml`

**Budgets (adjust per risk tolerance):**
```yaml
budgets:
  equity_usd: 2000
  options_premium_usd: 500
  futures_usd: 2500
  crypto_usd: 1500
```

**Guardrails (liquidity filters):**
```yaml
guardrails:
  min_adv_usd: 5000000      # Minimum daily volume
  max_spread_bps: 40        # Maximum spread
  allow_foreign_local: false # Prefer US ADRs/ETFs
```

**Update Futures Fronts (quarterly):**
```yaml
futures_fronts:
  ES: ESZ4  # Update to ESH5, ESM5, etc.
  CL: CLX4  # Update monthly
  GC: GCZ4  # Update quarterly
```

### Catalogs

**Extend stub catalogs with real data:**
- `catalog/secmaster.parquet` - Add your full global listings
- `catalog/etf_catalog.parquet` - Country/sector ETF mappings
- `catalog/stats.parquet` - ADV and spread data

**Minimal columns required:**
```
secmaster: symbol, exchange, mic, country, sector, name, adr_us, isin, ric, bbg
etf_catalog: etf, type, country, sector, name
stats: symbol, adv_usd, avg_spread_bps
```

---

## Performance

**V2 System SLOs:**
- OCR + Classification: 0.5-1.5s
- Catalog Resolution: <150ms
- **Total (LLM OFF): <1.5s from beep to suggestions**
- With LLM: 2-6s total

---

## What's Next

1. **Start with V2** for maximum coverage
2. Add your real secmaster/ETF catalogs
3. Tune budgets and guardrails
4. Set up watch-v2 to monitor live alerts
5. Paste suggestions into EMSX/IB or your executor

**GitHub:** https://github.com/RobericaLLC/headline-reactor

