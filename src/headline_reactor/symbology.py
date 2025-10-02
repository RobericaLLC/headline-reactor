from __future__ import annotations
import re, yaml
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Dict

@dataclass
class Candidate:
    instrument: str     # e.g., AAPL, SMH, EWY, ESZ4, 6EZ4, BITO, "AAPL +C175 NEXT_FRI x1"
    asset_class: str    # EQUITY / ETF / OPTION / FUT / FX / CRYPTO
    rationale: str
    score: float        # relative ranking

RX_SEMICOLON_SPLIT = re.compile(r"\s*;\s*")
RX_EXCH_TK = re.compile(r"\b([A-Z0-9]{1,6})\s+([A-Z]{1,3})\b")
RX_US_TK   = re.compile(r"\b([A-Z]{1,5})\b")

def load_universe(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))

def extract_row_tokens(row_text: str) -> List[str]:
    """Returns tokens like ['000660 KS','005930 KS','AAPL','META', ...]"""
    row = row_text.replace(";", " ; ")  # normalize OCR anomalies
    out: List[str] = []
    for m in RX_EXCH_TK.finditer(row):
        out.append(f"{m.group(1)} {m.group(2)}")
    words_bad = {"NEWS","HOT","HEADLINES","SHARES","JUMP","SURGE","DEAL","SUPPLY","ON","BY","OF","AND","TO","SET","THE","FOR","IN","AT","IS","ARE","THAT","WITH"}
    for m in RX_US_TK.finditer(row):
        tk = m.group(1)
        if tk in words_bad: continue
        if not any(ch.isdigit() for ch in tk):
            out.append(tk)
    # Dedup preserving order
    dedup, seen = [], set()
    for tk in out:
        if tk not in seen:
            seen.add(tk); dedup.append(tk)
    return dedup

def map_foreign_to_country_etf(token: str, ex2etf: Dict[str,str]) -> Optional[str]:
    """'000660 KS' -> EWY; returns None if not recognized."""
    parts = token.split()
    if len(parts) == 2:
        exch = parts[1]
        return ex2etf.get(exch)
    return None

