# Catalog Builder: Bloomberg BLPAPI + ORATS Integration

## Overview

The `build_catalogs.py` and `orats_fetch.py` scripts build production-grade catalogs for the V2 universe-wide trading system using:
- **Bloomberg Desktop API (BLPAPI)** for secmaster, liquidity stats, and futures
- **ORATS API** for options data and IV analytics

## Prerequisites

### 1. Bloomberg Terminal
- Bloomberg Terminal must be running
- Desktop API (DAPI) must be enabled
- Terminal > Settings > API Settings > Enable API

### 2. Python Dependencies
```powershell
pip install blpapi pandas pyarrow requests typer tqdm python-dateutil
```

**Note:** `blpapi` wheels come from Bloomberg. Install per your Terminal setup:
- Windows: Usually auto-installed with Terminal
- Or download from Bloomberg support

### 3. Environment Variables

Already configured in `.env`:
```bash
# Bloomberg Desktop API
BLP_HOST=localhost
BLP_PORT=8194

# ORATS API
ORATS_TOKEN=68e16f4d-0867-4bbe-8936-b59d8902d9af
```

---

## Building Catalogs

### Quick Start (Full Universe Build)

```powershell
# 1. Build secmaster from major indices (auto-expands to members)
python build_catalogs.py secmaster `
  --add-indices "SPX Index,NDX Index,RTY Index,SX5E Index,DAX Index,CAC Index,UKX Index"

# 2. Create ETF catalog (seed list you can extend)
python build_catalogs.py etfs

# 3. Compute liquidity stats (ADV + spreads)
python build_catalogs.py stats

# 4. (Optional) Futures front contracts
python build_catalogs.py futures-roll
```

**Result:**
```
catalog/
  secmaster.parquet     (~2,000-3,000 rows from indices)
  etf_catalog.parquet   (35 ETFs)
  stats.parquet         (~2,000-3,000 rows with liquidity)
  futures_roll.yml      (7 futures fronts)
```

### Custom Universe Build

**From text file:**
```powershell
# Create seeds.txt with one security per line
echo "AAPL US Equity" > seeds.txt
echo "NVDA US Equity" >> seeds.txt
echo "005930 KS Equity" >> seeds.txt
echo "2330 TT Equity" >> seeds.txt
echo "AIR FP Equity" >> seeds.txt

python build_catalogs.py secmaster --seed-file seeds.txt
```

**From comma-separated list:**
```powershell
python build_catalogs.py secmaster `
  --seeds "AAPL US Equity,NVDA US Equity,META US Equity,TSLA US Equity"
```

**Mix of direct tickers + indices:**
```powershell
python build_catalogs.py secmaster `
  --seeds "BITO US Equity,ETHE US Equity" `
  --add-indices "SPX Index,NDX Index"
```

---

## Catalog Outputs

### `secmaster.parquet`
**Columns:**
- `symbol` - Ticker (AAPL, 005930, etc.)
- `exchange` - Exchange code (US, KS, FP, etc.)
- `mic` - Market Identifier Code (XNAS, XKRX, etc.)
- `country` - Country of domicile (US, KR, FR, etc.)
- `sector` - GICS sector or industry
- `name` - Security name
- `isin` - ISIN code
- `ric` - Reuters code
- `bbg` - Bloomberg security string
- `adr_us` - US ADR ticker (if applicable)

**Example rows:**
| symbol | exchange | mic | country | sector | name | adr_us |
|--------|----------|-----|---------|--------|------|--------|
| AAPL | US | XNAS | US | Information Technology | Apple Inc | null |
| 005930 | KS | XKRX | KR | Information Technology | Samsung Electronics | null |
| AIR | FP | XPAR | FR | Industrials | Airbus SE | EADSY |
| EADSY | US | XNAS | FR | Industrials | Airbus SE ADR | EADSY |

### `etf_catalog.parquet`
**Columns:**
- `etf` - ETF ticker
- `type` - "sector" or "country"
- `sector` - Sector name (if type=sector)
- `country` - Country code (if type=country)
- `name` - ETF name

**Example rows:**
| etf | type | sector | country | name |
|-----|------|--------|---------|------|
| SMH | sector | Semiconductors | null | SMH Semiconductors |
| EWY | country | null | KR | EWY KR |
| XOP | sector | Oil & Gas | null | XOP Oil & Gas |

### `stats.parquet`
**Columns:**
- `symbol` - Ticker
- `adv_usd` - Average daily volume in USD
- `avg_spread_bps` - Average spread in basis points

**Example rows:**
| symbol | adv_usd | avg_spread_bps |
|--------|---------|----------------|
| AAPL | 50000000000 | 1.2 |
| NVDA | 25000000000 | 2.1 |
| EA | 500000000 | 5.3 |

### `futures_roll.yml`
**Content:**
```yaml
fronts:
  6E: 6EZ4
  6J: 6JZ4
  CL: CLX4
  ES: ESZ4
  GC: GCZ4
  NQ: NQZ4
  ZN: ZNZ4
```

---

## ORATS Integration

### Fetch Options Data

```powershell
# Get implied vol summary for a ticker
python orats_fetch.py summaries --ticker AAPL

# Get full options chain
python orats_fetch.py chain --ticker AAPL --out data/aapl_chain.csv

# Get specific option by OPRA code
python orats_fetch.py option --opra AAPL241220C00175000
```

### Use Cases
- **IV percentile** checks before trading options
- **Strike selection** validation
- **Earnings date** detection
- **Liquidity** validation (open interest, volume)

---

## Bloomberg Field Reference

### Reference Data Fields (secmaster)
```
SECURITY_NAME          - Full company name
TICKER                 - Ticker symbol
ID_ISIN                - ISIN code
ID_RIC                 - Reuters Instrument Code
EXCH_CODE              - Exchange code (US, KS, FP, etc.)
ID_MIC_PRIM_EXCH       - MIC code (if entitled)
CNTRY_OF_DOMICILE      - Country code
GICS_SECTOR_NAME       - GICS sector classification
INDUSTRY_SECTOR        - Fallback sector
CRNCY                  - Trading currency
ADR_FLAG               - Boolean: is this an ADR?
ADR_UNDL_TICKER        - Underlying ticker for ADR
ADR_SH_PER_ADR         - ADR ratio
```

### Static Market Data Fields (stats)
```
BID                    - Current bid price
ASK                    - Current ask price
PX_LAST                - Last trade price
VOLUME_AVG_30D         - 30-day average volume
VOLUME_AVG_20D         - 20-day average volume (fallback)
EQY_SH_OUT             - Shares outstanding
CRNCY                  - Currency (for FX conversion)
```

### Bulk Fields (indices/futures)
```
INDX_MEMBERS           - Index constituents
FUT_CHAIN              - Futures chain with expiries
```

---

## Maintenance

### Daily Updates
None required for secmaster/ETFs.

### Quarterly Updates
```powershell
# Update futures fronts (roll to new contracts)
python build_catalogs.py futures-roll
```

### Monthly Updates (Recommended)
```powershell
# Refresh liquidity stats (ADV, spreads change)
python build_catalogs.py stats
```

### Full Rebuild (Quarterly/As Needed)
```powershell
# Rebuild everything from scratch
python build_catalogs.py secmaster --add-indices "SPX Index,NDX Index,..."
python build_catalogs.py etfs
python build_catalogs.py stats
python build_catalogs.py futures-roll
```

---

## Extending Catalogs

### Add New Sectors
Edit `build_catalogs.py`:
```python
SECTOR_ETFS = [
    # ... existing ...
    ("XRT", "Retail"),
    ("IBB", "Biotech"),
    # ... add more
]
```

Then rebuild:
```powershell
python build_catalogs.py etfs
```

### Add New Countries
```python
COUNTRY_ETFS = [
    # ... existing ...
    ("EWS", "SG"),  # Singapore
    ("THD", "TH"),  # Thailand
]
```

### Add More MIC Mappings
```python
EXCH_TO_MIC_FALLBACK = {
    # ... existing ...
    "SG": "XSES",  # Singapore
    "TH": "XBKK",  # Thailand
}
```

---

## Troubleshooting

### Bloomberg Connection Issues
```
Error: Failed to start Bloomberg session
```
**Fix:**
1. Ensure Bloomberg Terminal is running
2. Check Terminal > Settings > API Settings > Enable API
3. Verify `BLP_HOST=localhost` and `BLP_PORT=8194` in `.env`
4. Try restarting Terminal

### Entitlement Errors
```
securityError: Insufficient Permissions
```
**Fix:**
- Some fields require specific entitlements
- The script gracefully handles missing fields
- Check Bloomberg entitlements for: GICS, ID_MIC_PRIM_EXCH, bulk fields

### ORATS Token Issues
```
RuntimeError: Set ORATS_TOKEN env var
```
**Fix:**
- Token is already in `.env`
- Make sure `.env` is in project root
- Token: `68e16f4d-0867-4bbe-8936-b59d8902d9af`

### Missing blpapi
```
blpapi not installed
```
**Fix:**
```powershell
# Bloomberg provides wheels - check your installation guide
# Usually auto-installed with Bloomberg Terminal Python
# Or download from Bloomberg support portal
```

---

## Performance

### secmaster Build
- **10-50 securities:** ~5-10 seconds
- **500 securities:** ~1-2 minutes
- **2,000+ securities (index expansion):** ~5-10 minutes

### stats Build
- **500 securities:** ~30-60 seconds
- **2,000+ securities:** ~2-4 minutes

### ORATS Fetch
- **Summaries:** <1 second
- **Chain:** 1-2 seconds
- **Single option:** <1 second

---

## Integration with headline-reactor

Once catalogs are built, they're automatically used by V2 commands:

```powershell
# V2 uses catalog-driven resolution
headline-reactor suggest-v2 "AIR FP AIRBUS WINS ORDER"
# Looks up AIR FP in secmaster → finds EADSY ADR → outputs both

headline-reactor watch-v2
# Continuously resolves all symbols via catalogs
```

---

## Security & Compliance

### Bloomberg Data
- ✅ Used locally only (no redistribution)
- ✅ Respects terminal entitlements
- ✅ No data leaves your machine
- ⚠️ Ensure compliance with Bloomberg Terminal agreement

### ORATS Data
- ✅ Your API token (personal/firm license)
- ✅ Used for options analytics only
- ⚠️ Check ORATS terms for usage limits

---

## Files

**Scripts:**
- `build_catalogs.py` - Bloomberg catalog builder (450+ lines)
- `orats_fetch.py` - ORATS API helpers (80+ lines)

**Outputs:**
- `catalog/secmaster.parquet` - Symbol metadata + ADR links
- `catalog/etf_catalog.parquet` - Sector/country ETF mappings
- `catalog/stats.parquet` - Liquidity guardrails (ADV, spreads)
- `catalog/futures_roll.yml` - Front month contracts

**Configuration:**
- `.env` - API keys and endpoints (ORATS token pre-configured)

---

## Next Steps

1. **Test Bloomberg connection:**
   ```powershell
   python build_catalogs.py etfs
   ```

2. **Build small test universe:**
   ```powershell
   python build_catalogs.py secmaster --seeds "AAPL US Equity,NVDA US Equity"
   ```

3. **Full production build:**
   ```powershell
   python build_catalogs.py secmaster --add-indices "SPX Index,NDX Index,RTY Index"
   python build_catalogs.py stats
   ```

4. **Test V2 with real catalogs:**
   ```powershell
   headline-reactor suggest-v2 "AAPL US APPLE BEATS EARNINGS"
   ```

**Repository:** https://github.com/RobericaLLC/headline-reactor

