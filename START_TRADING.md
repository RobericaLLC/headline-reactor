# 🚀 Start Trading with headline-reactor

## Quick Start (3 Ways to Run)

### Option 1: Using Python Module (Recommended - Always Works)
```powershell
python -m headline_reactor.cli watch-v2
```

### Option 2: Using Direct Executable
```powershell
& "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\headline-reactor.exe" watch-v2
```

### Option 3: Add to PATH (One-time setup, then use short command)
```powershell
# Add Scripts directory to PATH (PowerShell Admin)
$scriptsPath = "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts"
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$scriptsPath", "User")

# Restart PowerShell, then:
headline-reactor watch-v2
```

---

## 🎮 **Start Live Monitoring**

### Full Command (Option 1 - Recommended):
```powershell
python -m headline_reactor.cli watch-v2
```

**What you'll see:**
```
Watching 'Alert Catcher' (V2 universe-wide mode)... Ctrl+C to exit.
Whitelist: AAPL, AMD, BITO, CVS, EA, GE, ...

[NEWS] NVDA US NVIDIA IN TALKS FOR MAJOR ACQUISITION
 -> NVDA BUY $2000 IOC TTL=10m (NEWS: ma_rumor)
 -> XLK BUY $2000 IOC TTL=10m (NEWS: ma_rumor)
 -> SPY BUY $2000 IOC TTL=10m (NEWS: ma_rumor)

[NEWS] AMD US AMD ANNOUNCES NEW AI CHIP
 -> AMD BUY $2000 IOC TTL=10m (NEWS: macro_ambiguous)
 -> XLK BUY $2000 IOC TTL=10m
 -> SPY BUY $2000 IOC TTL=10m
```

---

## 🧪 **Test Single Headline**

```powershell
python -m headline_reactor.cli suggest-v2 "AAPL US APPLE BEATS EARNINGS"
```

**Expected output:**
```
AAPL BUY $2000 IOC TTL=10m (NEWS: macro_ambiguous)
XLK BUY $2000 IOC TTL=10m
SPY BUY $2000 IOC TTL=10m
```

---

## 📊 **Get Options Data (ORATS)**

```powershell
# Get IV summary
python orats_fetch.py summaries NVDA

# Get full options chain
python orats_fetch.py chain NVDA

# Specific option
python orats_fetch.py option NVDA241220C00185000
```

---

## 🛡️ **Pre-Flight Checks**

### Before Each Session:
```powershell
# 1. Validate catalog
python scripts/universe_guard.py
# Expected: PASS

# 2. Run smoke tests
python scripts/smoke_e2e.py
# Expected: 5/5 PASS

# 3. Check market session
python -c "from src.headline_reactor.safety.market_gates import USMarketCalendar; print(USMarketCalendar().session_info())"
# Expected: is_open=True during RTH
```

---

## 🎯 **Common Use Cases**

### M&A Rumor Alert:
```
Alert: "EA US ELECTRONIC ARTS NEAR DEAL"
System outputs:
  → EA BUY $2000 IOC TTL=10m (NEWS: ma_rumor)
  → XLC BUY $2000 IOC TTL=10m

Your action:
1. Review suggestion
2. Get options data: python orats_fetch.py summaries EA
3. Paste order into EMSX/IB
```

### Korea Semiconductor News:
```
Alert: "005930 KS SAMSUNG WINS MAJOR CONTRACT"
System outputs:
  → EWY BUY $2000 IOC TTL=10m (country ETF)
  → SMH BUY $2000 IOC TTL=10m (sector ETF)

Your action:
1. Review suggestion
2. Paste into trading system
```

### Oil/Macro Event:
```
Alert: "OPEC CUTS PRODUCTION WTI SURGES"
System outputs:
  → CLX4 BUY $2500 IOC TTL=10m (oil futures)

Your action:
1. Review suggestion
2. Execute futures order
```

---

## ⚙️ **Configuration**

### Adjust Budgets (`universe_v2.yml`):
```yaml
budgets:
  equity_usd: 2000      # Per equity order
  futures_usd: 2500     # Per futures order
  crypto_usd: 1500      # Per crypto order
```

### Tune Guardrails:
```yaml
guardrails:
  min_adv_usd: 5000000      # Minimum daily volume
  max_spread_bps: 40        # Maximum spread
```

### Customize Watch Parameters:
```powershell
python -m headline_reactor.cli watch-v2 `
  --roi-top 115 `
  --roi-height 20 `
  --poll-ms 250
```

---

## 🔧 **Troubleshooting**

### Command Not Found:
Use: `python -m headline_reactor.cli watch-v2`

### No Window Found:
- Ensure Bloomberg Alert Catcher window is visible
- Try adjusting `--roi-top` and `--roi-height`

### Tesseract Not Found:
- Verify Tesseract installed: `tesseract --version`
- Check path configured in `src/headline_reactor/ocr.py`

### Bloomberg Connection:
- Terminal must be running
- DAPI must be enabled
- Port 8194 accessible

### ORATS Errors:
- Check `.env` has ORATS_TOKEN
- Verify token: `68e16f4d-0867-4bbe-8936-b59d8902d9af`

---

## 📈 **What to Monitor**

### Success Indicators:
- ✅ Consistent 1-2s response times
- ✅ Mix of single-name + ETF suggestions
- ✅ ORATS cache files appearing (data/cache/orats/)
- ✅ No repeated errors

### Warning Signs:
- ⚠️ Response >3s consistently
- ⚠️ Many "NO ACTION" for known stocks
- ⚠️ ORATS 429 rate limits
- ⚠️ Bloomberg disconnects

---

## 🎉 **YOU'RE READY!**

**Start now:**
```powershell
python -m headline_reactor.cli watch-v2
```

**System includes:**
✅ 6,370 US securities  
✅ Bloomberg + ORATS integration  
✅ 1.24s average response  
✅ Operational hardening  
✅ Circuit breakers  
✅ Market session awareness  

**Happy trading!** 🎯📈

