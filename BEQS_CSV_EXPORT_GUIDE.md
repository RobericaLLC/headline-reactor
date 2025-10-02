# BEQS CSV Export Guide

## Problem: BEQS API Access Blocked

Your Bloomberg account can **create and view BEQS screens in Terminal** but is **blocked from BEQS API access** (error 4080).

**Solution:** Export screens to CSV from Terminal, then import via Python.

---

## Step-by-Step Instructions

### Step 1: Export from Bloomberg Terminal

#### Export Common Stocks Screen:
```
1. In Bloomberg Terminal, type: BEQS <GO>
2. Open your screen: "US_COMMON_PRIMARY"
3. Click "Actions" (top right)
4. Select "Export" → "Export All Results" or "Export to Excel"
5. Choose format: CSV
6. Save as: beqs_common.csv
7. Note: If 18k+ stocks, Bloomberg will export all (not just first 3k visible)
```

#### Export ETF Screen:
```
1. BEQS <GO>
2. Open "US_ETF_PRIMARY"
3. Actions → Export → Export All Results
4. Save as: beqs_etf.csv
```

#### Export ADR Screen:
```
1. BEQS <GO>
2. Open "US_ADR_PRIMARY"  
3. Actions → Export → Export All Results
4. Save as: beqs_adr.csv
```

### Step 2: Check CSV Format

```powershell
# See what columns are in your export
python import_beqs_csv.py show-columns beqs_common.csv
```

**Common column names in Bloomberg CSV exports:**
- `Security` (most common)
- `Ticker`
- `Name`
- `ID`
- `Bloomberg ID`

### Step 3: Import CSVs to Catalog

```powershell
# Import all three screens
python import_beqs_csv.py from-csv `
  --common-csv beqs_common.csv `
  --etf-csv beqs_etf.csv `
  --adr-csv beqs_adr.csv `
  --ticker-column "Security"

# If column name is different, use show-columns to find it, then:
# --ticker-column "YourColumnName"
```

**Expected output:**
```
[OK] Common Stocks: Loaded 18,000 from beqs_common.csv
[OK] ETFs: Loaded 5,000 from beqs_etf.csv
[OK] ADRs: Loaded 2,500 from beqs_adr.csv

[SUCCESS] Wrote catalog\beqs_securities.parquet
          25,500 unique securities ready for enrichment
```

### Step 4: Complete the Build

```powershell
# Enrich with Bloomberg reference data (10-15 minutes)
python us_universe_pipeline.py refdata-enrich

# Compute liquidity stats (5-10 minutes)
python us_universe_pipeline.py stats-cmd

# Create ETF mappings (<1 second)
python us_universe_pipeline.py etfs-cmd

# (Optional) Check ORATS coverage (20-40 minutes)
python us_universe_pipeline.py orats-cmd --max-workers 8
```

---

## Alternative: Use Current 6,370 Catalog (Already Working)

You already have a production-ready catalog:

```powershell
# Check what you have
python -c "import pandas; df = pandas.read_parquet('catalog/us_universe.parquet'); print('Symbols:', len(df))"

# Start trading NOW
headline-reactor watch-v2
```

**Current coverage:** ~80% of major headlines hit these 6,370 symbols

---

## Expected Timeline

### CSV Export Method (Full ~23k Universe):
1. **Export from Terminal:** 5-10 minutes (manual)
2. **Import CSVs:** <1 minute
3. **Enrich with Bloomberg:** 15-20 minutes
4. **Compute stats:** 10-15 minutes
5. **Total:** ~30-45 minutes

### Current Method (6,370 Symbols):
- **Ready NOW** (already built!)

---

## Troubleshooting CSV Exports

### Can't Find Export Option:
- Try right-clicking on results grid
- Look for "Export" in top menu bar
- Use keyboard shortcut (varies by version)

### Export Limits:
- Bloomberg should export ALL results (not just visible 3k)
- If truncated, try exporting in batches using screen filters

### Column Names:
- Use `show-columns` command to identify correct column
- Bloomberg CSV format varies by Terminal version
- Common names: Security, Ticker, ID

---

## Files

**Tools:**
- `import_beqs_csv.py` - CSV import utility
- `us_universe_pipeline.py` - Main pipeline

**Your BEQS Screens (in Terminal):**
- US_COMMON_PRIMARY (~18k stocks)
- US_ETF_PRIMARY (~5k ETFs)
- US_ADR_PRIMARY (~2-3k ADRs)

**Export these to CSV, then import!**

---

## Quick Decision

**Option A: Full Universe (CSV Export Method)**
- Get all ~23k US securities
- Requires CSV export from Terminal (10 min manual)
- Best coverage

**Option B: Current 6,370 Catalog**
- Already working
- Covers major headlines (~80%)
- Start trading immediately

**Which would you prefer?**

