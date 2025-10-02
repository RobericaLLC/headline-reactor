from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import yaml, pandas as pd
from pathlib import Path

@dataclass
class Plan:
    line: str
    reason: str
    label: str
    symbol: Optional[str] = None

def load_cfg(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def last_close(symbol: str, live_root: Path = Path("data/live")) -> Optional[float]:
    days = sorted([p for p in live_root.glob("*") if p.is_dir()])
    if not days: return None
    p = days[-1] / f"bars1s_{symbol}.parquet"
    if not p.exists(): return None
    df = pd.read_parquet(p)
    if df.empty: return None
    return float(df["close"].iloc[-1])

def plan_from_label(label: str, ticker: Optional[str], cfg: dict) -> Plan:
    defaults = cfg.get("defaults", {})
    pbs = cfg.get("playbooks", {})
    # macro / unknown
    if label == "macro_ambiguous" or not ticker:
        return Plan("NO ACTION (macro_ambiguous)", "Two-sided/macro headline", label, ticker)

    pb = pbs.get(label, {})
    action = pb.get("action", "BUY")
    sym = pb.get("symbol", ticker)
    offset = float(pb.get("equity_offset_px", defaults.get("equity_offset_px", 0.03)))
    notion = int(pb.get("notional_usd", defaults.get("notional_usd", 1500)))
    ttl = int(pb.get("ttl_sec", defaults.get("ttl_sec", 600)))
    line = f"{sym} {action} ${notion} IOC TTL={ttl//60}m (NEWS: {label})"
    return Plan(line=line, reason=f"rules:{label}", label=label, symbol=sym)

