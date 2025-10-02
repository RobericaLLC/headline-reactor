from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path
import yaml

from .resolver import extract_entities, Secmaster
from .proxy_engine import Catalogs, build_proxies
from .liquidity import LqGuard, load_stats, stats_ok
from .options2 import atm_call, delta_put

@dataclass
class Candidate:
    line: str
    asset_class: str
    score: float
    rationale: str

def _cfg(path: Path) -> dict:
    """Load configuration."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def _load_fronts(cfg: dict) -> Dict[str, str]:
    """Get futures front contracts."""
    return cfg.get("futures_fronts", {})

def _order_defaults(cfg: dict) -> dict:
    """Get order defaults."""
    return cfg.get("order_defaults", {})

def _guardrails(cfg: dict) -> LqGuard:
    """Build liquidity guardrails from config."""
    g = cfg.get("guardrails", {})
    return LqGuard(
        min_adv_usd=float(g.get("min_adv_usd", 5_000_000)),
        max_spread_bps=float(g.get("max_spread_bps", 40)),
        max_quote_age_ms=int(g.get("max_quote_age_ms", 1500))
    )

def _macro_from_headline(headline: str, cfg: dict) -> List[Candidate]:
    """Generate futures/FX/crypto candidates from macro keywords."""
    H = headline.upper()
    fronts = _load_fronts(cfg)
    out: List[Candidate] = []
    
    def add_fut(root: str, why: str, score: float = 0.58):
        code = fronts.get(root)
        if code:
            notion = cfg["budgets"]["futures_usd"]
            ttl = cfg["order_defaults"]["ttl_sec"] // 60
            out.append(Candidate(
                f"{code} BUY ${notion} IOC TTL={ttl}m (NEWS: macro)",
                "FUT", score, why
            ))
    
    # Macro routing logic
    if any(k in H for k in ["OIL", "WTI", "OPEC", "CRUDE"]): 
        add_fut("CL", "oil proxy")
    if any(k in H for k in ["GOLD", "BULLION"]): 
        add_fut("GC", "gold proxy")
    if any(k in H for k in ["EURO", "EUR"]): 
        add_fut("6E", "EUR/USD proxy", 0.56)
    if any(k in H for k in ["YEN", "JPY"]): 
        add_fut("6J", "JPY/USD proxy", 0.56)
    
    # Crypto
    if "BITCOIN" in H or "BTC" in H:
        proxy = cfg.get("crypto", {}).get("spot_to_proxy", {}).get("BTCUSD", "BITO")
        notion = cfg["budgets"]["crypto_usd"]
        ttl = cfg["order_defaults"]["ttl_sec"] // 60
        out.append(Candidate(
            f"{proxy} BUY ${notion} IOC TTL={ttl}m (NEWS: macro)",
            "CRYPTO", 0.56, "BTC proxy"
        ))
    
    if "ETHEREUM" in H or " ETH " in H or H.endswith(" ETH"):
        proxy = cfg.get("crypto", {}).get("spot_to_proxy", {}).get("ETHUSD", "ETHE")
        notion = cfg["budgets"]["crypto_usd"]
        ttl = cfg["order_defaults"]["ttl_sec"] // 60
        out.append(Candidate(
            f"{proxy} BUY ${notion} IOC TTL={ttl}m (NEWS: macro)",
            "CRYPTO", 0.55, "ETH proxy"
        ))
    
    return out

def choose_side(label: str) -> str:
    """Determine BUY/SELL based on label."""
    down = {
        "guide_cut", "regulatory_probe", "downgrade", "halt_negative",
        "supply_shock_neg", "bigtech_pivot", "country_ratings_down"
    }
    return "SELL" if label in down else "BUY"

def select_candidates(label: str, headline: str, row_text: str, cfg_path: Path) -> List[Candidate]:
    """Select best tradeable instruments across all asset classes."""
    cfg = _cfg(cfg_path)
    
    # Load catalogs
    sec_path = Path(cfg["catalog_paths"]["secmaster"])
    etf_path = Path(cfg["catalog_paths"]["etf_catalog"])
    stats_path = Path(cfg["catalog_paths"]["stats"])
    
    cats = Catalogs(sec_path, etf_path)
    sec = Secmaster(sec_path)
    stats = load_stats(stats_path)
    guard = _guardrails(cfg)
    allow_local = bool(cfg.get("guardrails", {}).get("allow_foreign_local", False))
    side = choose_side(label)
    
    # Extract entities from headline
    entities = extract_entities(row_text)
    cands: List[Candidate] = []
    
    # For each entity → resolve → proxies → guard → format
    for ent in entities:
        if ent.kind == "MACRO":
            continue  # Handled by macro router
        
        rows = sec.resolve(ent)
        for r in rows:
            proxies = build_proxies(r, cats, allow_local=allow_local)
            
            # Filter by liquidity
            kept = []
            for p in proxies:
                if p.asset_class == "EQUITY":
                    if not stats_ok(p.instr, stats, guard):
                        continue
                kept.append(p)
            
            # Format top proxies
            for p in kept[:3]:
                ttlm = cfg["order_defaults"]["ttl_sec"] // 60
                notion = cfg["budgets"]["equity_usd"]
                
                cands.append(Candidate(
                    f"{p.instr} {side} ${notion} IOC TTL={ttlm}m (NEWS: {label})",
                    p.asset_class,
                    p.base_score,
                    p.why
                ))
                
                # Options overlay for single-names (event-aware)
                if p.asset_class == "EQUITY":
                    # Calls for M&A and positive pops
                    if label in ("ma_confirmed", "ma_rumor", "pop_positive", "supplier_pop_korea_semi"):
                        oi = atm_call(p.instr)
                        if oi:
                            cands.append(Candidate(
                                f"{oi.line} (NEWS: {label})",
                                "OPTION",
                                oi.score,
                                oi.rationale
                            ))
                    
                    # Puts for downgrades and guidance cuts
                    if side == "SELL" and label in ("guide_cut", "downgrade", "halt_negative", "supply_shock_neg"):
                        oi = delta_put(p.instr, 0.30)
                        if oi:
                            cands.append(Candidate(
                                f"{oi.line} (NEWS: {label})",
                                "OPTION",
                                oi.score,
                                oi.rationale
                            ))
    
    # Add macro candidates
    cands += _macro_from_headline(headline, cfg)
    
    # Dedup by line, keep highest score, return top 3
    dedup: Dict[str, Candidate] = {}
    for c in cands:
        if c.line not in dedup or c.score > dedup[c.line].score:
            dedup[c.line] = c
    
    ranked = sorted(dedup.values(), key=lambda x: x.score, reverse=True)
    return ranked[:3]

