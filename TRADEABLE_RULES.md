# Tradeable Rules Implementation

This document summarizes the major enhancements to headline-reactor that enable **actionable, paste-ready trade suggestions** for RTH-tradeable events.

## What Changed

### 1. Expanded Rulepack (Beyond Ratings/Macros)

Added **5 new tradeable event categories**:

#### `supplier_pop_korea_semi`
- **Triggers:** Samsung, SK Hynix supply deals or positive news
- **Output:** Multi-output with sympathy trades
  ```
  EWY BUY $1500 IOC TTL=10m (NEWS: supplier_pop_korea_semi)
  SMH BUY $1500 IOC TTL=10m (NEWS: supplier_pop_korea_semi)
  ```

#### `bigtech_pivot`
- **Triggers:** Apple/Meta/Google product cancellations or deprioritizations
- **Output:** Short suggestion on direct ticker
  ```
  AAPL SELL $1500 IOC TTL=10m (NEWS: bigtech_pivot)
  ```

#### `country_ratings_up` / `country_ratings_down`
- **Triggers:** Sovereign credit rating changes (Fitch, Moody's, S&P)
- **Output:** Country ETF + pair trade vs regional benchmark
  ```
  EWP BUY $1500 IOC TTL=30m (NEWS: country_ratings_up)
  PAIR EWP/FEZ LONG/SHORT $1000/$1000 IOC TTL=30m (NEWS: country_ratings_up)
  ```

#### `ma_confirmed` / `ma_rumor`
- **Triggers:** M&A deals confirmed or rumored
- **Output:** Direct ticker BUY
  ```
  EA BUY $1500 IOC TTL=10m (NEWS: ma_rumor)
  ```

---

## 2. Smart Ticker Extraction

### Direct Ticker Parsing
The system now **parses tickers directly from the Alert Catcher row** instead of fuzzy text matching:

**Example row:**
```
000660 KS;005930 KS  SAMSUNG, SK HYNIX SHARES JUMP ON OPENAI'S...
```

**Extracted tickers:**
- `000660 KS` → Korean exchange code
- `005930 KS` → Korean exchange code
- Primary: `EWY` (KS → EWY mapping)
- Sympathy: `SMH` (Samsung/Hynix → semis)

### Exchange Code Mappings

Foreign exchange suffixes automatically map to US-traded ETFs:

**Europe:**
- `ES`, `SM` → `EWP` (Spain)
- `FR`, `FP` → `EWQ` (France)
- `DE`, `GR` → `EWG` (Germany)
- `IT` → `EWI` (Italy)
- `GB`, `LN` → `EWU` (UK)

**Asia:**
- `KS`, `KQ` → `EWY` (Korea)
- `JP`, `T` → `EWJ` (Japan)
- `HK` → `EWH` (Hong Kong)
- `TW` → `EWT` (Taiwan)
- `CN`, `SS`, `SZ` → `MCHI` (China)

### Company → Sector Sympathy

```python
COMPANY_TO_SECTOR = {
    "SAMSUNG": "SEMIS",
    "SK HYNIX": "SEMIS",
    "TSMC": "SEMIS",
}

SECTOR_TO_ETF = {
    "SEMIS": "SMH",  # Van Eck Semiconductor ETF
}
```

---

## 3. Multi-Output Ranked Suggestions

Headlines now generate **multiple trade ideas** ranked by confidence:

### Confidence Scoring
```python
_CONF = {
    "ma_confirmed": 0.95,        # Highest confidence
    "ma_rumor": 0.70,
    "country_ratings_up": 0.75,
    "country_ratings_down": 0.70,
    "supplier_pop_korea_semi": 0.65,
    "bigtech_pivot": 0.55,
    "macro_ambiguous": 0.0,      # No action
}
```

### Example Multi-Output

**Input:**
```
000660 KS;005930 KS SAMSUNG, SK HYNIX SHARES JUMP ON OPENAI'S STARGATE SUPPLY DEAL
```

**Output (2 suggestions):**
```
EWY BUY $1500 IOC TTL=10m (NEWS: supplier_pop_korea_semi)   [conf: 0.65]
SMH BUY $1500 IOC TTL=10m (NEWS: supplier_pop_korea_semi)   [conf: 0.60]
```

---

## 4. Enhanced CLI Parameters

### Tunable ROI Positioning
```powershell
headline-reactor watch `
  --roi-top 115 `      # Top pixel offset for first alert row
  --roi-height 20      # Row height in pixels
```

### Expanded Whitelist
```powershell
--whitelist "EWP,EA,SPY,FEZ,SMH,SOXX,EWY,AAPL,META"
```

### Watch Mode Command
```powershell
headline-reactor watch `
  --window-title "Alert Catcher" `
  --roi-top 115 `
  --roi-height 20 `
  --whitelist "EWY,SMH,AAPL,META,EA,EWP,FEZ" `
  --poll-ms 250
```

---

## 5. Updated Configuration

### `newsreactor.yml` Playbooks

```yaml
playbooks:
  supplier_pop_korea_semi:
    action: BUY
    equity_offset_px: 0.03
    ttl_sec: 600        # 10 minutes
  
  bigtech_pivot:
    action: SELL
    equity_offset_px: 0.03
    ttl_sec: 600        # 10 minutes
  
  country_ratings_up:
    action: BUY
    equity_offset_px: 0.02
    ttl_sec: 1800       # 30 minutes
  
  country_ratings_down:
    action: SELL
    equity_offset_px: 0.02
    ttl_sec: 1800       # 30 minutes
```

---

## Testing Results

### Test 1: Korea Semiconductor News
```bash
$ headline-reactor suggest "000660 KS;005930 KS SAMSUNG, SK HYNIX SHARES JUMP ON OPENAIS STARGATE SUPPLY DEAL"

EWY BUY $1500 IOC TTL=10m (NEWS: supplier_pop_korea_semi)
SMH BUY $1500 IOC TTL=10m (NEWS: supplier_pop_korea_semi)
```
✅ **PASS** - Generated both country (EWY) and sector (SMH) sympathy trades

### Test 2: Big Tech Product Pivot
```bash
$ headline-reactor suggest "AAPL;META APPLE SHELVES HEADSET REVAMP TO PRIORITIZE META-LIKE AI GLASSES"

AAPL SELL $1500 IOC TTL=10m (NEWS: bigtech_pivot)
```
✅ **PASS** - Direct ticker parsed, SELL action generated

### Test 3: Country Ratings
```bash
$ headline-reactor suggest "SPAIN UPGRADED TO A BY FITCH"

EWP BUY $1500 IOC TTL=30m (NEWS: country_ratings_up)
PAIR EWP/FEZ LONG/SHORT $1000/$1000 IOC TTL=30m (NEWS: country_ratings_up)
```
✅ **PASS** - Generated both outright and pair trade

### Test 4: M&A Rumor
```bash
$ headline-reactor suggest "EA ELECTRONIC ARTS NEAR DEAL WITH MICROSOFT"

EA BUY $1500 IOC TTL=10m (NEWS: ma_rumor)
```
✅ **PASS** - Matched rumor pattern, generated BUY

---

## Why These Are Tradeable

### ✅ Liquid US Instruments
- All suggestions use **US-traded ETFs or large-cap stocks**
- No illiquid ADRs or foreign exchanges
- Examples: EWY (Korea), SMH (semis), AAPL, META

### ✅ IOC + Time Stops
- Every order includes `IOC` (Immediate or Cancel)
- Time-to-live limits risk (10m for news, 30m for ratings)
- No overnight holds

### ✅ Sympathy Trades
- Korea semis → both **country proxy (EWY)** and **sector proxy (SMH)**
- Spain ratings → **outright (EWP)** and **pair vs region (EWP/FEZ)**

### ✅ Directional Clarity
- Rules determine BUY vs SELL based on event type
- Ratings up → BUY country ETF
- Product cancellation → SELL stock
- M&A rumor → BUY target

---

## Architecture Benefits

### 1. **Rules-First** (< 200ms)
Deterministic regex classification ensures:
- Predictable output
- Auditable decisions
- No LLM required for core logic

### 2. **Ticker-Aware**
Parses actual exchange codes from Bloomberg:
- `000660 KS` → EWY (not fuzzy matching "Samsung")
- `AAPL` → direct use (not name lookup)

### 3. **Multi-Output**
Generates ranked alternatives:
- Primary trade (highest confidence)
- Sympathy trades (slightly lower confidence)
- Pair trades (for hedged exposure)

### 4. **Local-Only**
- OCR runs locally (Tesseract)
- No network calls unless `LLM_ENABLED=1`
- Bloomberg compliance-friendly

---

## Future Enhancements

### Add More Exchanges
```python
EXCH_TO_ETF = {
    "MX": "EWW",  # Mexico
    "BR": "EWZ",  # Brazil
    # ... etc
}
```

### Custom Pair Strategies
```python
# In planner.py
if label == "bigtech_pivot":
    # Add pair vs QQQ
    out.append(Plan(
        line=f"PAIR {primary}/QQQ SHORT/LONG $1000/$1000 IOC TTL=10m",
        ...
    ))
```

### Integration with Trading Stack
```python
# Convert output line to execd one-shot call
execd_cmd = convert_to_execd(plan.line, plan.symbol)
```

---

## Repository

**GitHub:** https://github.com/RobericaLLC/headline-reactor

**Key Files:**
- `src/headline_reactor/rules.py` - Ticker extraction + classification
- `src/headline_reactor/planner.py` - Multi-output generation
- `src/headline_reactor/cli.py` - Watch mode + CLI
- `newsreactor.yml` - Playbook configuration

**Commit:** `35a1c21` - Add tradeable event rules with smart ticker extraction

