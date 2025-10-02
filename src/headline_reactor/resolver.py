from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
import pandas as pd

@dataclass
class Entity:
    """A real-world thing we might trade or proxy."""
    raw: str
    kind: str            # EQUITY/INDEX/CRYPTO/FX/MACRO
    symbol: Optional[str] = None  # native symbol if obvious (AAPL, 005930)
    exch: Optional[str] = None    # short ex code (US, O, N, KS, TT, HK, SS, SZ, L, FP, GY, SW, IM, AU, etc)
    isin: Optional[str] = None
    ric: Optional[str] = None
    name: Optional[str] = None

RX_ISIN = re.compile(r'\b([A-Z]{2}[A-Z0-9]{9}\d)\b')
# Common headline token patterns
RX_BBG = re.compile(r'\b([A-Z0-9\.\-]{1,15})\s+(US|LN|FP|GY|SW|IM|AU|HK|KS|KQ|TT|TW|T|JP|CN|SS|SZ|ES|SM|PA|DE|L)\b')
RX_RIC = re.compile(r'\b([A-Z0-9]{1,15})\.(?:O|N|KQ|KS|HK|SS|SZ|L|PA|DE|SW|MI|VX|TO)\b')
RX_LOCAL = re.compile(r'\b(\d{1,6}|[A-Z]{1,6})\s+(KS|KQ|TT|TW|HK|SS|SZ|L|FP|GY|SW|IM|AU|PA|DE|SM)\b')
RX_US = re.compile(r'\b([A-Z]{1,6})(?:\s+US)?\b')

def extract_entities(text: str) -> List[Entity]:
    """Extract all tradeable entities from headline text."""
    T = text.upper()
    out: List[Entity] = []
    
    # ISINs
    for m in RX_ISIN.finditer(T):
        out.append(Entity(raw=m.group(1), kind="EQUITY", isin=m.group(1)))
    
    # BBG-like (AAPL US, SIE GY, AIR FP)
    for m in RX_BBG.finditer(T):
        out.append(Entity(raw=m.group(0), kind="EQUITY", symbol=m.group(1), exch=m.group(2)))
    
    # RIC-like (NVDA.O, 2330.TW)
    for m in RX_RIC.finditer(T):
        out.append(Entity(raw=m.group(0), kind="EQUITY", symbol=m.group(1), ric=m.group(0)))
    
    # Local code (005930 KS, 2330 TT, AIR FP)
    for m in RX_LOCAL.finditer(T):
        out.append(Entity(raw=m.group(0), kind="EQUITY", symbol=m.group(1), exch=m.group(2)))
    
    # Bare US tickers (filter common words)
    BAD = {"ON","AND","THE","SET","CUT","CUTS","RAISES","SAYS","NEW","IPO","ETF","SEC","FED","ECB","BOJ","NEWS","HOT"}
    for m in RX_US.finditer(T):
        tk = m.group(1)
        if tk in BAD: continue
        if any(c.isdigit() for c in tk): continue
        out.append(Entity(raw=tk, kind="EQUITY", symbol=tk, exch="US"))
    
    # Crypto & Macro cues
    if "BITCOIN" in T or "BTC" in T: 
        out.append(Entity(raw="BTCUSD", kind="CRYPTO", symbol="BTCUSD"))
    if "ETHEREUM" in T or "ETH " in T or T.endswith(" ETH"): 
        out.append(Entity(raw="ETHUSD", kind="CRYPTO", symbol="ETHUSD"))
    if any(k in T for k in ["OIL","WTI","OPEC","CRUDE","BRENT"]): 
        out.append(Entity(raw="OIL", kind="MACRO"))
    if any(k in T for k in ["GOLD","BULLION"]): 
        out.append(Entity(raw="GOLD", kind="MACRO"))
    if any(k in T for k in ["DOLLAR","USD INDEX","DXY"]): 
        out.append(Entity(raw="DOLLAR", kind="MACRO"))
    if any(k in T for k in ["YEN","JPY"]): 
        out.append(Entity(raw="YEN", kind="MACRO"))
    if any(k in T for k in ["EURO","EUR "]): 
        out.append(Entity(raw="EURO", kind="MACRO"))
    
    # Dedup by raw token order
    seen, dedup = set(), []
    for e in out:
        if e.raw not in seen:
            seen.add(e.raw)
            dedup.append(e)
    return dedup

class Secmaster:
    """Resolve entities to tradeable rows using secmaster catalog."""
    
    def __init__(self, path: Path):
        self.ok = False
        self.df = None
        if path.exists():
            try:
                df = pd.read_parquet(path)
                # must have at least symbol, exchange/mic, country, sector
                need = {"symbol","exchange","mic","country","sector","name","adr_us"}
                if need.issubset(set(df.columns)):
                    self.df = df
                    self.ok = True
            except Exception:
                pass

    def resolve(self, ent: Entity) -> List[Dict]:
        """Return zero or more tradeable rows for an entity (local, ADR, US)."""
        if not self.ok: 
            # best effort—assume US ticker if exch==US or bare
            if ent.kind == "EQUITY" and (ent.exch in (None, "US") and ent.symbol):
                return [dict(
                    symbol=ent.symbol, 
                    mic="XNMS", 
                    exchange="US", 
                    country="US", 
                    sector=None, 
                    name=ent.symbol, 
                    adr_us=None
                )]
            return []
        
        df = self.df
        q = None
        
        # Try multiple resolution strategies
        if ent.isin:
            q = df[df["isin"] == ent.isin]
        elif ent.ric:
            q = df[df["ric"].str.upper() == ent.ric.upper()]
        elif ent.symbol and ent.exch:
            q = df[(df["symbol"].str.upper() == ent.symbol.upper()) & 
                   (df["exchange"].str.upper() == ent.exch.upper())]
        elif ent.symbol:
            q = df[df["symbol"].str.upper() == ent.symbol.upper()]
        
        if q is None or q.empty:
            return []
        
        return q.to_dict("records")

