from __future__ import annotations
import re
from typing import Optional

RULES = [
    ("ratings_up_spain",   re.compile(r"\bSPAIN\b.*\b(UPGRADED|RAISED TO|UPGRADE)\b.*\b(FITCH|MOODY'S|S&P)\b")),
    ("ratings_down_spain", re.compile(r"\bSPAIN\b.*\b(DOWNGRADED|CUT TO|DOWNGRADE)\b.*\b(FITCH|MOODY'S|S&P)\b")),
    ("ma_confirmed",       re.compile(r"\b(AGREES TO BE ACQUIRED|AGREED TO ACQUIRE|GOING PRIVATE|BUYOUT|TAKEOVER|ACQUIRED BY)\b")),
    ("ma_rumor",           re.compile(r"\b(NEAR DEAL|NEARS DEAL|IN TALKS|WEIGHING SALE|REPORTEDLY IN TALKS)\b")),
    ("macro_ambiguous",    re.compile(r"\b(SUPREME COURT|FED|CPI|OPEC|UN SECURITY COUNCIL)\b")),
]

NAME_TO_TICKER = { "SPAIN":"EWP", "ELECTRONIC ARTS":"EA" }

def classify(headline: str) -> Optional[str]:
    for label, rx in RULES:
        if rx.search(headline): return label
    return None

def map_ticker(headline: str, whitelist: set[str]) -> Optional[str]:
    # explicit names
    for name, tkr in NAME_TO_TICKER.items():
        if name in headline and tkr in whitelist: return tkr
    # short tickers present
    for tok in re.findall(r"\b[A-Z]{1,5}\b", headline):
        if tok in whitelist: return tok
    return None

