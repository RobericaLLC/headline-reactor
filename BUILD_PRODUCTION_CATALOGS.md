# Build Production Catalogs - Ready to Run

## ✅ Prerequisites Met

Both APIs are confirmed working:
- ✅ **Bloomberg BLPAPI v3.25.8.1** - Connected to Terminal (AAPL: $255.45)
- ✅ **ORATS API** - Live data streaming (AAPL IV 30d: 25.19%)
- ✅ **Tesseract OCR v5.4.0** - Extracting Bloomberg alerts
- ✅ **headline-reactor V2** - All tests passing

---

## 🎯 Quick Build (Recommended)

### Full Production Universe (~2,000-3,000 symbols)
```powershell
# 1. Build secmaster from major US indices
python build_catalogs.py secmaster `
  --add-indices "SPX Index,NDX Index,RTY Index"

# Expected: ~2,500 symbols in 5-10 minutes
```

### Global Universe (~5,000+ symbols)
```powershell
# Add European and Asian indices
python build_catalogs.py secmaster `
  --add-indices "SPX Index,NDX Index,RTY Index,SX5E Index,DAX Index,CAC Index,UKX Index,NKY Index,HSI Index,KOSPI Index"

# Expected: ~5,000+ symbols in 10-20 minutes
```

### Complete the Build
```powershell
# 2. Create ETF mappings (35 ETFs, <1 second)
python build_catalogs.py etfs

# 3. Compute liquidity stats (2-4 minutes)
python build_catalogs.py stats

# 4. Set futures fronts (<30 seconds)
python build_catalogs.py futures-roll
```

---

## 📊 What You'll Get

### Current (Stub Catalogs)
- 14 symbols (AAPL, Samsung, Airbus, etc.)
- 15 ETFs  
- Basic liquidity data
- 7 futures fronts

### After Production Build
- **2,500-5,000+ symbols** from major indices
- **Complete ADR coverage** (foreign → US ADR auto-resolved)
- **Real-time liquidity stats** (actual ADV, live spreads)
- **Global coverage** (US, Europe, Asia)

---

## 🧪 Test After Building

```powershell
# Test with any global stock
headline-reactor suggest-v2 "SIE GY SIEMENS BEATS Q4 EARNINGS"
# Should output: SIEGY BUY (US ADR) + EWG BUY (Germany ETF)

headline-reactor suggest-v2 "NESN SW NESTLE RAISES GUIDANCE"
# Should output: NSRGY BUY (US ADR) + EWL BUY (Switzerland ETF)

# Start live monitoring
headline-reactor watch-v2
```

---

## ⏱️ Build Time Estimates

| Step | Symbols | Time | Network |
|------|---------|------|---------|
| secmaster (SPX only) | ~500 | 2-3 min | Moderate |
| secmaster (SPX+NDX+RTY) | ~2,500 | 5-10 min | Heavy |
| secmaster (Global) | ~5,000+ | 10-20 min | Heavy |
| etfs | 35 | <1 sec | None |
| stats | 2,500 | 2-4 min | Moderate |
| futures-roll | 7 | 10-30 sec | Light |

**Total for full build:** ~7-15 minutes

---

## 🔧 Customization Options

### Build Specific Universe
```powershell
# Just tech stocks from file
echo "AAPL US Equity" > my_universe.txt
echo "NVDA US Equity" >> my_universe.txt
echo "META US Equity" >> my_universe.txt

python build_catalogs.py secmaster --seed-file my_universe.txt
```

### Add Specific Sectors
```powershell
# Semiconductors only
python build_catalogs.py secmaster `
  --seeds "NVDA US Equity,AMD US Equity,INTC US Equity,MU US Equity,AVGO US Equity"
```

### Test Small Build First
```powershell
# Build with just one index to test
python build_catalogs.py secmaster --add-indices "NDX Index"
# ~100 symbols in ~1 minute
```

---

## 📋 Maintenance After Build

### Quarterly
```powershell
# Update futures fronts (contract rolls)
python build_catalogs.py futures-roll
```

### Monthly  
```powershell
# Refresh liquidity stats
python build_catalogs.py stats
```

### As Needed
```powershell
# Add new symbols to universe
python build_catalogs.py secmaster --seeds "NEW_TICKER US Equity"
```

---

## 🎯 Next Steps

### Option 1: Build Full Production Universe (Recommended)
```powershell
python build_catalogs.py secmaster --add-indices "SPX Index,NDX Index,RTY Index"
python build_catalogs.py etfs
python build_catalogs.py stats
python build_catalogs.py futures-roll
```

### Option 2: Test Small Build First
```powershell
python build_catalogs.py secmaster --add-indices "NDX Index"
python build_catalogs.py etfs
python build_catalogs.py stats
```

### Option 3: Keep Using Stub Catalogs
```powershell
# Already working! Just start using it
headline-reactor watch-v2
```

---

## ✅ Confirmation

**Both APIs are now installed and verified working:**
- ✅ Bloomberg BLPAPI v3.25.8.1 (tested: AAPL $255.45)
- ✅ ORATS API (tested: AAPL IV 30d = 25.19%)

**Ready to build production catalogs whenever you're ready!**

