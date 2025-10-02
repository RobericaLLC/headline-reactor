from __future__ import annotations
import re
from typing import Optional, List

# --- Classifier rules (expanded for tradeable events)
RULES = [
    ("country_ratings_up",   re.compile(r"\b(UPGRADED|RAISED TO|UPGRADE)\b.*\b(FITCH|MOODY'S|S&P)\b")),
    ("country_ratings_down", re.compile(r"\b(DOWNGRADED|CUT TO|DOWNGRADE)\b.*\b(FITCH|MOODY'S|S&P)\b")),
    ("supplier_pop_korea_semi", re.compile(r"\b(SAMSUNG|SK HYNIX)\b.*\b(SHARES (JUMP|SURGE|RISE)|DEAL|SUPPLY)\b")),
    ("bigtech_pivot",        re.compile(r"\b(APPLE|META|GOOGLE|MICROSOFT|AMAZON)\b.*\b(SHELVES|CANCELS|SCRAPS|DEPRIORITIZ)\w*\b")),
    ("ma_confirmed",         re.compile(r"\b(AGREES TO BE ACQUIRED|AGREED TO ACQUIRE|GOING PRIVATE|BUYOUT|TAKEOVER|ACQUIRED BY)\b")),
    ("ma_rumor",             re.compile(r"\b(NEAR DEAL|NEARS DEAL|IN TALKS|WEIGHING SALE|REPORTEDLY IN TALKS)\b")),
    ("macro_ambiguous",      re.compile(r"\b(SUPREME COURT|FED|CPI|OPEC|UN SECURITY COUNCIL)\b")),
]

# Optional explicit name → US ticker (expand as needed)
NAME_TO_TICKER = {
    "SPAIN": "EWP",
    "ELECTRONIC ARTS": "EA",
    "APPLE": "AAPL",
    "META": "META",
}

# Exchange suffix → country ETF proxy (fast US-listed placeholders)
EXCH_TO_ETF = {
    # Europe
    "ES": "EWP", "SM": "EWP",       # Spain
    "FR": "EWQ", "FP": "EWQ",       # France
    "DE": "EWG", "GR": "EWG",       # Germany
    "IT": "EWI",
    "GB": "EWU", "LN": "EWU",
    # Asia
    "JP": "EWJ", "T": "EWJ",
    "HK": "EWH",
    "KS": "EWY", "KQ": "EWY",       # Korea
    "TW": "EWT",
    "CN": "MCHI", "SS": "MCHI", "SZ": "MCHI",
}

# Company → sector for sympathy (maps to SMH/SOXX etc.)
COMPANY_TO_SECTOR = {
    "SAMSUNG": "SEMIS",
    "SK HYNIX": "SEMIS",
    "TSMC": "SEMIS",
}
SECTOR_TO_ETF = {
    "SEMIS": "SMH",   # or "SOXX" if you prefer
}

# --------- Ticker parsing from OCR row

_EXCH = "|".join(sorted(EXCH_TO_ETF.keys(), key=len, reverse=True))
# e.g., "000660 KS", "005930 KS", "AAPL", "META"
RX_EXCH_TK = re.compile(rf"\b([A-Z0-9]{{1,6}})\s+({_EXCH})\b")
RX_US_TK   = re.compile(r"\b([A-Z]{1,5})\b")

def extract_row_tickers(row_text: str) -> List[str]:
    """Returns tokens like ['000660 KS','005930 KS','AAPL','META'] in order."""
    row_text = row_text.replace(";", " ; ")  # make ';' a separator for OCR variants
    out: List[str] = []
    for m in RX_EXCH_TK.finditer(row_text):
        out.append(f"{m.group(1)} {m.group(2)}")
    # US 1-5 letter tickers (filter out obvious words)
    words_bad = {"NEWS","HOT","HEADLINES","SHARES","JUMP","DEAL","TO","ON","BY","OF","AND","SET","THE","FOR","IN","AT","IS","ARE","THAT","WITH"}
    for m in RX_US_TK.finditer(row_text):
        tk = m.group(1)
        if tk in words_bad: continue
        if not any(ch.isdigit() for ch in tk):
            out.append(tk)
    # Dedup preserving order
    dedup = []
    seen = set()
    for tk in out:
        if tk not in seen:
            seen.add(tk); dedup.append(tk)
    return dedup

def _map_exch_to_etf(token: str) -> Optional[str]:
    """'000660 KS' -> EWY; returns None if not recognized."""
    parts = token.split()
    if len(parts) == 2:
        exch = parts[1]
        return EXCH_TO_ETF.get(exch)
    return None

def _sector_proxy_from_headline(headline: str) -> Optional[str]:
    for co, sector in COMPANY_TO_SECTOR.items():
        if co in headline:
            etf = SECTOR_TO_ETF.get(sector)
            if etf: return etf
    return None

# --------- Public API used by CLI

def classify(headline: str) -> Optional[str]:
    for label, rx in RULES:
        if rx.search(headline): return label
    return None

def map_ticker(headline: str, whitelist: set[str]) -> Optional[str]:
    """
    Primary symbol selection:
    1) If row includes a US ticker in whitelist → return it.
    2) Else map the first foreign 'CODE EXCH' → country ETF (EXCH_TO_ETF).
    3) Else sector sympathy ETF from headline (e.g., SMH).
    4) Else NAME_TO_TICKER / text fallback.
    """
    row_tickers = extract_row_tickers(headline)
    # 1) US tickers present?
    for tk in row_tickers:
        if " " not in tk and tk in whitelist:
            return tk
    # 2) First foreign w/ exchange suffix → ETF
    for tk in row_tickers:
        if " " in tk:
            etf = _map_exch_to_etf(tk)
            if etf and etf in whitelist:
                return etf
    # 3) Sector sympathy (e.g., Samsung/Hynix → SMH)
    etf = _sector_proxy_from_headline(headline)
    if etf and etf in whitelist:
        return etf
    # 4) Fallback name map
    for name, tkr in NAME_TO_TICKER.items():
        if name in headline and tkr in whitelist:
            return tkr
    return None
