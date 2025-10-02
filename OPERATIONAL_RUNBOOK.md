# Operational Runbook: headline-reactor Production Trading

## 🕐 Daily Operations

### Pre-Market (08:20 ET)

**1. System Health Check:**
```powershell
# Validate catalog integrity
python scripts/universe_guard.py
# Expected: PASS with 6,370 symbols, 100% coverage
```

**2. Smoke Test:**
```powershell
# Run 5 test headlines
python scripts/smoke_e2e.py
# Expected: 5/5 PASS, avg <1.5s
```

**3. Market Session Check:**
```powershell
python -c "from src.headline_reactor.safety.market_gates import USMarketCalendar; cal = USMarketCalendar(); sess = cal.session_info(); print(f'Market: {sess.reason}, Open: {sess.is_open}, Close in: {sess.minutes_to_close}m')"
```

**4. Start Monitoring:**
```powershell
headline-reactor watch-v2
```

---

### During Market Hours (09:30-16:00 ET)

**Monitor for:**

#### Normal Operation Indicators:
- ✅ Headlines processing every 250ms
- ✅ Response times 1-2 seconds
- ✅ Mix of single-name + ETF suggestions
- ✅ ORATS cache hits (data/cache/orats/*.csv)

#### Warning Signals:
- ⚠️ Response time >3s for 5+ consecutive alerts
- ⚠️ Many "NO ACTION" for known stocks (catalog issue)
- ⚠️ ORATS errors >10% (rate limit or network)
- ⚠️ Bloomberg connection drops (restart Terminal)

#### Critical Alerts:
- 🚨 Tesseract OCR failures (restart watch-v2)
- 🚨 Bloomberg DAPI disconnect (restart Terminal)
- 🚨 System crashes (check logs, restart)

---

### Market Stress Scenarios

#### Scenario 1: Market-Wide Halt
```
Symptoms: Multiple "TRADING_STATUS=HALT" alerts
Actions:
  1. System auto-degrades to ETF_ONLY mode
  2. Futures/FX suggestions continue
  3. Single-name suppressed until clear
```

#### Scenario 2: LULD Trigger
```
Symptoms: Price approaching LULD bands
Actions:
  1. System checks LULD_LOWER/UPPER_PRICE_BAND
  2. Skips suggestions if price outside bands
  3. Routes to sector ETF proxy
```

#### Scenario 3: Short Sale Restriction (SSR)
```
Symptoms: SHORT_SALE_RESTRICTION = True
Actions:
  1. For SELL orders: Prefer puts over short stock
  2. Or route to ETF short (if permitted)
  3. Flag in suggestion output
```

#### Scenario 4: Wide Spreads (Market Stress)
```
Symptoms: Spread >80bps on target names
Actions:
  1. Circuit breaker records wide_spread event
  2. After 2 events in 60s → ETF_ONLY mode
  3. Skip illiquid single-names
```

---

### Circuit Breaker Activation

**Triggers:**
- 3+ errors in 60 seconds
- 2+ timeouts in 60 seconds  
- 2+ wide-spread events in 60 seconds

**Actions:**
- System enters **ETF_ONLY** mode
- Suppresses single-name and options
- Continues ETF, futures, FX suggestions
- Auto-recovers after 60s if conditions clear

**Manual Reset:**
```powershell
# Restart watch-v2 to reset circuit
Ctrl+C
headline-reactor watch-v2
```

---

### End of Day (16:00+ ET)

**1. Review Performance:**
```powershell
# Check how many suggestions were generated
wc -l data/logs/events.jsonl  # If logging enabled
```

**2. Weekly Archive (Friday EOD):**
```powershell
# Archive logs
Compress-Archive data/logs/*.jsonl -DestinationPath archive/logs_week_$(Get-Date -Format 'yyyy-MM-dd').zip

# Clear cache
Remove-Item data/cache/orats/*.csv -Force
```

**3. Monthly Maintenance (Last Friday):**
```powershell
# Refresh liquidity stats
python build_catalogs.py stats

# Update futures fronts
python build_catalogs.py futures-roll
```

---

## 🛠️ Troubleshooting Guide

### Issue: No Suggestions Generated

**Symptoms:** All headlines return "NO ACTION"

**Diagnosis:**
```powershell
python scripts/universe_guard.py
```

**Fixes:**
- Catalog corrupted → Rebuild from backup
- Bloomberg disconnected → Restart Terminal
- Wrong universe file → Check config points to us_universe.parquet

---

### Issue: Slow Response Time (>3s)

**Symptoms:** Consistent latency above SLO

**Diagnosis:**
1. Check OCR performance (capture time)
2. Check Bloomberg refdata calls
3. Check catalog size (too large?)

**Fixes:**
- OCR slow → Restart Tesseract, check CPU
- Bloomberg slow → Check Terminal health, network
- Catalog too large → Filter to active names only

---

### Issue: ORATS Rate Limits

**Symptoms:** HTTP 429 errors from ORATS

**Diagnosis:**
```powershell
# Check cache TTL
ls data/cache/orats/*.csv
```

**Fixes:**
- Increase cache TTL from 15s to 30s
- Reduce max_workers for batch operations
- Implement token bucket rate limiter

---

### Issue: Bloomberg DAPI Disconnect

**Symptoms:** "Failed to start Bloomberg session"

**Fixes:**
1. Check Terminal is running
2. Terminal → Settings → API Settings → Enable API
3. Restart Bloomberg Terminal
4. Check port 8194 not blocked by firewall

---

## 📊 Performance Baselines

### Normal Market Conditions:
| Metric | Baseline | Alert Threshold |
|--------|----------|-----------------|
| Avg latency | 1.2s | >2.0s |
| p95 latency | 1.8s | >3.0s |
| p99 latency | 2.5s | >5.0s |
| Error rate | <1% | >5% |
| ORATS hit rate | >95% | <80% |

### Volatile Conditions:
| Metric | Baseline | Alert Threshold |
|--------|----------|-----------------|
| Avg latency | 1.5s | >3.0s |
| Circuit trips | 0-2/day | >5/day |
| ETF_ONLY duration | <5min | >15min |

---

## 🔐 Security Checklist

### API Keys:
- [ ] OPENAI_API_KEY in .env only (not committed)
- [ ] ORATS_TOKEN in .env only (not committed)
- [ ] Bloomberg uses localhost only (no external)

### Data Handling:
- [ ] No PII in logs
- [ ] Bloomberg data stays local (no redistribution)
- [ ] ORATS data cached <1 minute
- [ ] Event logs archived securely

### Compliance:
- [ ] Bloomberg Terminal agreement allows local OCR
- [ ] ORATS terms reviewed for usage limits
- [ ] Internal approval for automated trading obtained

---

## 📈 Success Metrics (Week 1)

### Reliability:
- [ ] **Uptime:** >95% during RTH (9:30-16:00 ET)
- [ ] **Latency:** p95 <2s
- [ ] **Error rate:** <2%

### Coverage:
- [ ] **Hit rate:** >75% of alerts get suggestions
- [ ] **Proxy quality:** ETF proxies used appropriately
- [ ] **False positives:** <5%

### Operations:
- [ ] **Circuit trips:** <3 per day
- [ ] **Manual interventions:** <2 per day
- [ ] **Bloomberg reconnects:** <1 per day

---

## 🚨 Incident Response

### P1: System Down
```
1. Check Bloomberg Terminal running
2. Check Tesseract installed
3. Restart: headline-reactor watch-v2
4. If fails: Check logs, reboot system
```

### P2: Degraded Performance
```
1. Check circuit breaker status
2. Review error logs
3. Consider ETF_ONLY mode manually
4. Monitor for 5 minutes
```

### P3: Data Quality Issue
```
1. Run universe_guard.py
2. Check catalog timestamps
3. Refresh if >7 days old
4. Validate with smoke tests
```

---

## 📞 Escalation

### Level 1: Operational Issues
- Bloomberg Terminal disconnects
- OCR failures
- Network timeouts
- **Action:** Restart components, monitor

### Level 2: Data Issues
- Catalog corruption
- ORATS outages
- Bloomberg entitlement changes
- **Action:** Rebuild catalogs, validate data

### Level 3: Code Issues
- Classification errors
- Proxy selection bugs
- Performance degradation
- **Action:** Review code, test fixes, deploy

---

## 📝 Daily Log Template

```
Date: 2025-10-02
Market: OPEN (09:30-16:00 ET)
System Start: 09:25 ET

Performance:
- Alerts processed: XXX
- Suggestions generated: XXX
- Avg latency: X.XXs
- Circuit trips: X

Issues:
- None / [Description]

Actions Taken:
- None / [Description]

Notes:
- [Any observations]
```

---

## 🎯 Operational Excellence

**Your system now has:**
✅ Market session awareness (holidays, early closes)
✅ Trading halt detection
✅ LULD band checking
✅ SSR awareness
✅ Circuit breakers (auto-degrade)
✅ SLO metrics (optional StatsD)
✅ Price banding (marketable limits)
✅ Comprehensive runbook

**This is production-grade operational hardening!** 🛡️

