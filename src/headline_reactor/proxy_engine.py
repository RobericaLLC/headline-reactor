from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path
import pandas as pd

@dataclass
class Proxy:
    """A tradeable proxy for an underlying entity."""
    instr: str
    asset_class: str  # EQUITY/ETF/FUT/FX/CRYPTO
    why: str
    base_score: float

class Catalogs:
    """Manage ETF and secmaster catalogs."""
    
    def __init__(self, sec_path: Path, etf_path: Path):
        self.secmaster = None
        self.etfs = None
        
        if sec_path.exists():
            try:
                self.secmaster = pd.read_parquet(sec_path)
            except Exception:
                pass
        
        if etf_path.exists():
            try:
                self.etfs = pd.read_parquet(etf_path)
            except Exception:
                pass

    def adr_for(self, row: Dict) -> Optional[str]:
        """Get US ADR ticker for a foreign stock."""
        adr = row.get("adr_us")
        return adr if isinstance(adr, str) and adr else None

    def sector_etf(self, sector: Optional[str]) -> Optional[str]:
        """Get sector ETF for a given sector."""
        if self.etfs is None or not sector: 
            return None
        try:
            r = self.etfs[(self.etfs["type"] == "sector") & 
                         (self.etfs["sector"].str.upper() == sector.upper())]
            if r.empty: 
                return None
            return r["etf"].iloc[0]
        except Exception:
            return None

    def country_etf(self, country: Optional[str]) -> Optional[str]:
        """Get country ETF for a given country."""
        if self.etfs is None or not country: 
            return None
        try:
            r = self.etfs[(self.etfs["type"] == "country") & 
                         (self.etfs["country"].str.upper() == country.upper())]
            if r.empty: 
                return None
            return r["etf"].iloc[0]
        except Exception:
            return None

def build_proxies(row: Dict, cats: Catalogs, allow_local: bool) -> List[Proxy]:
    """Build proxy waterfall: single-name → ADR → sector ETF → country ETF."""
    out: List[Proxy] = []
    sym, ctry, sect = row.get("symbol"), row.get("country"), row.get("sector")
    exch = row.get("exchange", "").upper()
    
    # 1) Single-name US (preferred)
    if exch in ("US", "NYSE", "NASDAQ", "N", "O", "UQ", "XNYS", "XNAS"):
        out.append(Proxy(sym, "EQUITY", "US listing", 0.95))
    
    # 2) ADR if available
    adr = cats.adr_for(row)
    if adr: 
        out.append(Proxy(adr, "EQUITY", "US ADR", 0.85))
    
    # 3) Local line (if explicitly allowed)
    if allow_local and exch not in ("US", "N", "O", "UQ", "XNYS", "XNAS"):
        out.append(Proxy(sym, "EQUITY", f"Local line {exch}", 0.75))
    
    # 4) Sector ETF (sympathy)
    se = cats.sector_etf(sect)
    if se: 
        out.append(Proxy(se, "ETF", f"Sector ETF ({sect})", 0.65))
    
    # 5) Country ETF
    ce = cats.country_etf(ctry)
    if ce: 
        out.append(Proxy(ce, "ETF", f"Country ETF ({ctry})", 0.60))
    
    return out

