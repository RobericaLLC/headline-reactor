"""Merge ORATS coverage mapping into universe catalog"""
from pathlib import Path
import pandas as pd

UNI = Path("catalog/us_universe.parquet")
ORA = Path("catalog/orats_coverage.parquet")
OUT = Path("catalog/us_universe_with_orats.parquet")

if not UNI.exists():
    print(f"[ERROR] {UNI} not found")
    exit(1)

u = pd.read_parquet(UNI)
print(f"Universe: {len(u):,} symbols")

if ORA.exists():
    o = pd.read_parquet(ORA)
    # Keep most recent check per symbol
    keep = o.sort_values("last_checked_utc").drop_duplicates("symbol", keep="last")
    u = u.merge(keep[["symbol","orats_symbol","orats_ok"]], on="symbol", how="left")
    ok_count = u["orats_ok"].sum()
    print(f"ORATS: {ok_count:,} symbols with options coverage")
else:
    print(f"[WARN] {ORA} not found - skipping ORATS mapping")
    u["orats_symbol"] = None
    u["orats_ok"] = False

u.to_parquet(OUT, index=False)
print(f"[OK] Wrote {OUT} ({len(u):,} rows with ORATS mapping)")

