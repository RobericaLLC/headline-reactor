from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import yaml, pandas as pd
from pathlib import Path

try:
    from .instrument_selector import select_candidates, Context
    from .symbology import load_universe
    UNIVERSE_AVAILABLE = True
except ImportError:
    UNIVERSE_AVAILABLE = False

@dataclass
class Plan:
    line: str
    reason: str
    label: str
    symbol: Optional[str] = None
    confidence: float = 0.5

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

# Confidence scores per rule type
_CONF = {
    "ma_confirmed": 0.95,
    "ma_rumor": 0.70,
    "country_ratings_up": 0.75,
    "country_ratings_down": 0.70,
    "supplier_pop_korea_semi": 0.65,
    "bigtech_pivot": 0.55,
    "macro_ambiguous": 0.0,
}

def _render_line(label: str, sym: str, action: str, cfg: dict) -> str:
    defaults = cfg.get("defaults", {})
    pbs = cfg.get("playbooks", {})
    pb = pbs.get(label, {})
    action = pb.get("action", action)
    offset = float(pb.get("equity_offset_px", defaults.get("equity_offset_px", 0.03)))
    notion = int(pb.get("notional_usd", defaults.get("notional_usd", 1500)))
    ttl = int(pb.get("ttl_sec", defaults.get("ttl_sec", 600)))
    return f"{sym} {action} ${notion} IOC TTL={ttl//60}m (NEWS: {label})"

def plans_from_headline(label: str, headline: str, primary: Optional[str], cfg: dict, wl: set[str]) -> List[Plan]:
    """Generate one or more ranked trade suggestions from a headline."""
    if label == "macro_ambiguous" or (primary is None and label not in ("supplier_pop_korea_semi","country_ratings_up","country_ratings_down")):
        return [Plan("NO ACTION (macro_ambiguous)", "Two-sided/macro", label, None, 0.0)]

    out: List[Plan] = []
    
    # Primary suggestion
    if primary:
        act = "BUY"
        if label in ("country_ratings_down","bigtech_pivot"): 
            act = "SELL"
        line = _render_line(label, primary, act, cfg)
        out.append(Plan(line=line, reason=f"rules:{label}", label=label, symbol=primary, confidence=_CONF.get(label, 0.5)))

    # Secondary sympathy ideas
    # supplier_pop_korea_semi → add SMH when EWY was primary or vice versa
    if label == "supplier_pop_korea_semi":
        if primary != "EWY" and "EWY" in wl:
            out.append(Plan(line=_render_line(label, "EWY", "BUY", cfg), reason="sympathy:korea", label=label, symbol="EWY", confidence=_CONF[label]-0.05))
        if primary != "SMH" and "SMH" in wl:
            out.append(Plan(line=_render_line(label, "SMH", "BUY", cfg), reason="sympathy:semis", label=label, symbol="SMH", confidence=_CONF[label]-0.05))

    # country ratings → pair trade vs regional benchmark
    if label in ("country_ratings_up","country_ratings_down"):
        if "FEZ" in wl and primary == "EWP":
            side = "LONG/SHORT" if label == "country_ratings_up" else "SHORT/LONG"
            pair = f"PAIR EWP/FEZ {side} $1000/$1000 IOC TTL=30m (NEWS: {label})"
            out.append(Plan(line=pair, reason="pair:country_vs_region", label=label, symbol=None, confidence=_CONF[label]-0.05))

    # Dedup identical lines, keep highest confidence
    dedup: dict[str, Plan] = {}
    for p in out:
        if p.line not in dedup or p.confidence > dedup[p.line].confidence:
            dedup[p.line] = p
    return sorted(dedup.values(), key=lambda p: p.confidence, reverse=True)

def plans_universe(label: str, headline: str, row_text: str, cfg: dict, universe_path: Path, wl: set[str]) -> List[Plan]:
    """Universe-aware planner: selects best instruments across all asset classes."""
    if not UNIVERSE_AVAILABLE:
        # Fallback to simple planner if universe modules not available
        return plans_from_headline(label, headline, row_text, cfg, wl)
    
    uni = load_universe(universe_path)
    ctx = Context(label=label, headline=headline, row_text=row_text, wl=wl, uni=uni)
    cands = select_candidates(ctx)
    out: List[Plan] = []
    for c in cands:
        out.append(Plan(
            line=c.instrument,  # already fully formatted
            reason=c.rationale, 
            label=label, 
            symbol=None, 
            confidence=c.score
        ))
    return out if out else [Plan("NO ACTION (macro_ambiguous)", "No tradeable instruments found", label, None, 0.0)]

# Legacy function for backwards compatibility
def plan_from_label(label: str, ticker: Optional[str], cfg: dict) -> Plan:
    """Single-plan legacy API. Use plans_from_headline for multi-output."""
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
