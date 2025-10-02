"""Universe drift and liquidity sanity checks"""
from pathlib import Path
import pandas as pd
import sys

UNI = Path("catalog/us_universe.parquet")
STATS = Path("catalog/stats.parquet")

if not UNI.exists():
    print("[FAIL] catalog/us_universe.parquet missing!")
    sys.exit(1)

if not STATS.exists():
    print("[FAIL] catalog/stats.parquet missing!")
    sys.exit(1)

u = pd.read_parquet(UNI)
s = pd.read_parquet(STATS)

n = len(u)
pct_adv = (s["adv_usd"].notna().sum() / len(s) * 100) if len(s) > 0 else 0
pct_spd = (s["avg_spread_bps"].notna().sum() / len(s) * 100) if len(s) > 0 else 0

fails = []
if n < 5000:
    fails.append(f"Universe shrank: {n} symbols (expected >5000)")
if pct_adv < 90:
    fails.append(f"ADV coverage low: {pct_adv:.1f}% (expected >90%)")
if pct_spd < 90:
    fails.append(f"Spread coverage low: {pct_spd:.1f}% (expected >90%)")

if fails:
    print("=" * 70)
    print("UNIVERSE GUARD: FAIL")
    print("=" * 70)
    for f in fails:
        print(f"  [!] {f}")
    print("=" * 70)
    sys.exit(1)

print("=" * 70)
print("UNIVERSE GUARD: PASS")
print("=" * 70)
print(f"  Universe: {n:,} symbols")
print(f"  ADV coverage: {pct_adv:.1f}%")
print(f"  Spread coverage: {pct_spd:.1f}%")
print("=" * 70)
sys.exit(0)

