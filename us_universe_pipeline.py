# us_universe_pipeline.py
from __future__ import annotations
import os, math, time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import pandas as pd
import requests
from dateutil import tz
from tqdm import tqdm
import typer

# Bloomberg
try:
    import blpapi
except Exception:
    blpapi = None

app = typer.Typer(add_completion=False)
CAT = Path("catalog"); CAT.mkdir(parents=True, exist_ok=True)

# ---------- Bloomberg helpers ----------
def _require_blp():
    if blpapi is None:
        typer.echo("blpapi not installed. Install Bloomberg Desktop API Python bindings.")
        raise typer.Exit(2)

def _session() -> blpapi.Session:
    host, port = os.getenv("BLP_HOST", "localhost"), int(os.getenv("BLP_PORT", "8194"))
    opts = blpapi.SessionOptions(); opts.setServerHost(host); opts.setServerPort(port)
    s = blpapi.Session(opts)
    if not s.start(): raise RuntimeError("Failed to start Bloomberg session")
    return s

def _open(s: blpapi.Session, svc: str) -> blpapi.Service:
    if not s.openService(svc): raise RuntimeError(f"Failed to open {svc}")
    return s.getService(svc)

def _send(s: blpapi.Session, service: blpapi.Service, req: blpapi.Request) -> List[blpapi.Message]:
    cid = blpapi.CorrelationId(); s.sendRequest(req, correlationId=cid)
    out = []
    while True:
        ev = s.nextEvent()
        for msg in ev:
            if msg.correlationIds() and msg.correlationIds()[0] == cid:
                out.append(msg)
        if ev.eventType() == blpapi.Event.RESPONSE: break
    return out

# ---------- BEQS (Bloomberg Equity Screening) ----------
def beqs_list(screen_name: str, screen_type: str = "PRIVATE", max_results: int = 25000) -> List[str]:
    """
    Fetch securities from a saved BEQS screen with pagination. Returns list like ['AAPL US Equity', ...].
    Bloomberg BEQS has a 3,000 result limit per request - we need to paginate using overrides.
    """
    _require_blp()
    s = _session()
    try:
        ref = _open(s, "//blp/refdata")
        all_secs: List[str] = []
        offset = 0
        page_size = 3000
        
        while offset < max_results:
            req = ref.createRequest("BeqsRequest")
            
            # Set required screenName element
            req.getElement("screenName").setValue(screen_name)
            
            # Set optional screenType element (GLOBAL or PRIVATE)
            req.getElement("screenType").setValue(screen_type)
            
            # Add pagination overrides (START_POSITION and MAX_RESULTS)
            if offset > 0:
                ovr = req.getElement("overrides")
                o1 = ovr.appendElement()
                o1.setElement("fieldId", "START_POSITION")
                o1.setElement("value", str(offset))
            
            # Send request and collect response
            msgs = _send(s, ref, req)
            
            page_secs: List[str] = []
            for m in msgs:
                # Check for errors first
                if m.hasElement("responseError"):
                    err = m.getElement("responseError")
                    err_msg = err.getElementAsString("message") if err.hasElement("message") else "Unknown error"
                    typer.echo(f"    [ERROR] {err_msg}")
                    return all_secs  # Return what we have so far
                
                # Try data -> securityData -> security
                if m.hasElement("data"):
                    data = m.getElement("data")
                    
                    # Check for securityData at data level
                    if data.hasElement("securityData"):
                        sd = data.getElement("securityData")
                        for i in range(sd.numValues()):
                            sec_elem = sd.getValueAsElement(i)
                            
                            # Each element should have a 'security' field
                            if sec_elem.hasElement("security"):
                                sec = sec_elem.getElementAsString("security")
                                if sec:
                                    # Normalize to "TICKER EXCH Equity" format
                                    if not sec.endswith("Equity") and not sec.endswith("Index"):
                                        sec = sec + " Equity"
                                    page_secs.append(sec)
                
                # Direct securityData at message level
                if m.hasElement("securityData"):
                    sd = m.getElement("securityData")
                    for i in range(sd.numValues()):
                        sec_elem = sd.getValueAsElement(i)
                        if sec_elem.hasElement("security"):
                            sec = sec_elem.getElementAsString("security")
                            if sec:
                                # Normalize format
                                if not sec.endswith("Equity") and not sec.endswith("Index"):
                                    sec = sec + " Equity"
                                page_secs.append(sec)
            
            if not page_secs:
                typer.echo(f"    Page {offset//page_size + 1}: No more results")
                break
            
            all_secs.extend(page_secs)
            typer.echo(f"    Page {offset//page_size + 1}: Retrieved {len(page_secs)} securities (total: {len(all_secs)})")
            
            # If we got less than page_size, we're done
            if len(page_secs) < page_size:
                break
            
            offset += page_size
        
        # Dedup keeping order
        out, seen = [], set()
        for x in all_secs:
            if x not in seen:
                seen.add(x); out.append(x)
        
        typer.echo(f"    Total unique: {len(out)} securities from '{screen_name}'")
        return out
    finally:
        s.stop()

# ---------- Refdata / Static ----------
REF_FIELDS = [
    "SECURITY_NAME","TICKER","ID_ISIN","ID_RIC",
    "EXCH_CODE","PRIMARY_EXCHANGE_NAME","ID_MIC_PRIM_EXCH",
    "CNTRY_OF_DOMICILE","GICS_SECTOR_NAME","INDUSTRY_SECTOR",
    "CRNCY","ADR_FLAG","ADR_UNDL_TICKER","ADR_SH_PER_ADR","SECURITY_TYP","SECURITY_TYP2"
]
SNAP_FIELDS = ["BID","ASK","PX_LAST","VOLUME_AVG_30D","VOLUME_AVG_20D","CRNCY"]

EXCH_TO_MIC = {
    "US":None,"N":"XNYS","UN":"XNYS","UA":"ARCX","UW":"XNAS","UQ":"XNAS",
    "LN":"XLON","L":"XLON","FP":"XPAR","PA":"XPAR","GY":"XETR","DE":"XETR",
    "SM":"XMAD","MC":"XMAD","MI":"XMIL","IM":"XMIL","SW":"XSWX","VX":"XSWX",
    "T":"XTKS","JP":"XTKS","HK":"XHKG","KS":"XKRX","KQ":"XKOS","TT":"XTAI","TW":"XTAI",
    "SS":"XSHG","SZ":"XSHE"
}

def refdata(securities: List[str], fields: List[str]) -> pd.DataFrame:
    _require_blp()
    s = _session()
    try:
        ref = _open(s, "//blp/refdata")
        out_rows: List[Dict[str,Any]] = []
        CHUNK = 450
        for i in range(0,len(securities),CHUNK):
            req = ref.createRequest("ReferenceDataRequest")
            e_secs = req.getElement("securities")
            for sec in securities[i:i+CHUNK]: e_secs.appendValue(sec)
            e_flds = req.getElement("fields")
            for f in fields: e_flds.appendValue(f)

            for msg in _send(s, ref, req):
                if not msg.hasElement("securityData"): continue
                sd = msg.getElement("securityData")
                for j in range(sd.numValues()):
                    r = sd.getValueAsElement(j)
                    sec = r.getElementAsString("security")
                    fd = r.getElement("fieldData")
                    row = {"bbg": sec}
                    for f in fields:
                        if fd.hasElement(f):
                            row[f] = _elem(fd.getElement(f))
                    out_rows.append(row)
        return pd.DataFrame(out_rows)
    finally:
        s.stop()

def static_snap(securities: List[str], fields: List[str]) -> pd.DataFrame:
    _require_blp()
    s = _session()
    try:
        svc = _open(s, "//blp/staticmktdata")
        out_rows: List[Dict[str,Any]] = []
        CHUNK = 450
        for i in range(0,len(securities),CHUNK):
            req = svc.createRequest("StaticMarketDataRequest")
            e_secs = req.getElement("securities")
            for sec in securities[i:i+CHUNK]: e_secs.appendValue(sec)
            e_flds = req.getElement("fields")
            for f in fields: e_flds.appendValue(f)
            for msg in _send(s, svc, req):
                if not msg.hasElement("securityData"): continue
                sd = msg.getElement("securityData")
                for j in range(sd.numValues()):
                    r = sd.getValueAsElement(j)
                    sec = r.getElementAsString("security")
                    fd = r.getElement("fieldData")
                    row = {"bbg": sec}
                    for f in fields:
                        if fd.hasElement(f):
                            row[f] = _elem(fd.getElement(f))
                    out_rows.append(row)
        return pd.DataFrame(out_rows)
    finally:
        s.stop()

def _elem(e: blpapi.Element):
    try:
        if e.datatype()==blpapi.DataType.STRING: return e.getValueAsString()
        if e.datatype() in (blpapi.DataType.FLOAT64, blpapi.DataType.FLOAT32): return float(e.getValueAsFloat64())
        if e.datatype() in (blpapi.DataType.INT32, blpapi.DataType.INT64): return int(e.getValueAsInteger())
        if e.datatype()==blpapi.DataType.BOOL: return bool(e.getValueAsBool())
        return e.toString()
    except Exception:
        return None

# ---------- Build steps ----------
def normalize_ref(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["symbol"]   = out.get("TICKER")
    out["exchange"] = out.get("EXCH_CODE")
    # MIC: prefer ID_MIC_PRIM_EXCH; else map EXCH_CODE
    out["mic"]      = out.get("ID_MIC_PRIM_EXCH")
    out.loc[out["mic"].isna(), "mic"] = out["exchange"].map(EXCH_TO_MIC)
    out["country"]  = out.get("CNTRY_OF_DOMICILE")
    out["name"]     = out.get("SECURITY_NAME")
    out["sector"]   = out.get("GICS_SECTOR_NAME").fillna(out.get("INDUSTRY_SECTOR"))
    out["isin"]     = out.get("ID_ISIN")
    out["ric"]      = out.get("ID_RIC")
    # tags - handle Series properly
    st = out["SECURITY_TYP"].fillna("").astype(str).str.upper() if "SECURITY_TYP" in out.columns else pd.Series([""] * len(out))
    st2 = out["SECURITY_TYP2"].fillna("").astype(str).str.upper() if "SECURITY_TYP2" in out.columns else pd.Series([""] * len(out))
    adrflag = (out["ADR_FLAG"]==True) if "ADR_FLAG" in out.columns else pd.Series([False] * len(out))
    out["is_adr"]   = adrflag.fillna(False)
    out["is_etf"]   = st.eq("ETF") | st.str.contains("ETF", na=False) | st2.str.contains("ETF|ETP", regex=True, na=False)
    out["is_common"]= (~out["is_etf"]) & (~out["is_adr"])
    keep = ["symbol","exchange","mic","country","sector","name","isin","ric","bbg","is_common","is_etf","is_adr"]
    out = out[keep].drop_duplicates(subset=["bbg"]).reset_index(drop=True)
    return out

def fx_needed(crncy: pd.Series) -> List[str]:
    pairs=set()
    for c in crncy.dropna().astype(str):
        if c.upper()!="USD": pairs.add(f"{c.upper()}USD Curncy")
    return sorted(pairs)

def fetch_fx(pairs: List[str]) -> Dict[str,float]:
    if not pairs: return {}
    df = refdata(pairs, ["PX_LAST"])
    fx = {}
    for _,r in df.iterrows():
        sec = r["bbg"]
        px  = r.get("PX_LAST")
        if px: fx[sec.split()[0].upper()] = float(px)
    return fx

def adv_spread(secmaster: pd.DataFrame) -> pd.DataFrame:
    # Snapshot
    snap = static_snap(secmaster["bbg"].tolist(), SNAP_FIELDS)
    if snap.empty: return pd.DataFrame(columns=["symbol","adv_usd","avg_spread_bps"])
    tmp = secmaster[["bbg","symbol"]].merge(snap, on="bbg", how="left")
    # FX → USD
    pairs = fx_needed(tmp["CRNCY"])
    fx_map= fetch_fx(pairs)
    def fx_to_usd(c):
        if not isinstance(c,str) or c.upper()=="USD": return 1.0
        return float(fx_map.get(c.upper()+"USD", 0.0)) or 0.0

    adv, spd = [], []
    for _,r in tmp.iterrows():
        v = r.get("VOLUME_AVG_30D") if pd.notna(r.get("VOLUME_AVG_30D")) else r.get("VOLUME_AVG_20D")
        px= r.get("PX_LAST"); cr=r.get("CRNCY")
        f = fx_to_usd(cr)
        adv.append(float(v)*float(px)*f if (pd.notna(v) and pd.notna(px) and f>0) else None)
        bid,ask = r.get("BID"), r.get("ASK")
        if pd.notna(bid) and pd.notna(ask) and bid>0 and ask>0:
            mid=0.5*(bid+ask); spd.append((ask-bid)/mid*10000.0)
        else:
            spd.append(None)
    out = pd.DataFrame({"symbol": tmp["symbol"], "adv_usd": adv, "avg_spread_bps": spd})
    out = out.groupby("symbol", as_index=False).agg({"adv_usd":"max","avg_spread_bps":"min"})
    return out

# ---------- ORATS coverage ----------
BASE_ORATS = "https://api.orats.io/datav2"
def _orats_token() -> str:
    tok = os.getenv("ORATS_TOKEN"); 
    if not tok: raise RuntimeError("Set ORATS_TOKEN env var")
    return tok

def _try_orats_symbol(sym: str) -> Tuple[Optional[str], bool]:
    """Probe a few symbol forms against the summaries endpoint to see what ORATS accepts."""
    import re
    forms = [sym,
             sym.replace("/", "."),         # BRK/B -> BRK.B
             sym.replace(".", ""),          # BRK.B -> BRKB
             re.sub(r'[^A-Z0-9]+','',sym)]  # strip punctuation
    hdr = {"Accept":"text/csv"}
    for f in dict.fromkeys(forms):
        url = f"{BASE_ORATS}/live/one-minute/summaries"
        try:
            r = requests.get(url, params={"ticker": f, "token": _orats_token()}, headers=hdr, timeout=10)
            if r.status_code==200 and "ticker,tradeDate" in r.text.splitlines()[0]:
                return f, True
        except Exception:
            pass
    return None, False

def check_orats_coverage(symbols: List[str], max_workers: int = 8) -> pd.DataFrame:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    rows=[]
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(_try_orats_symbol, s): s for s in symbols}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="ORATS probe"):
            s = futs[fut]
            orats_sym, ok = fut.result()
            rows.append({"symbol": s, "orats_symbol": orats_sym, "orats_ok": bool(ok), 
                         "last_checked_utc": datetime.utcnow().isoformat(timespec="seconds")})
    return pd.DataFrame(rows)

# ---------- Build steps ----------
def refdata(securities: List[str], fields: List[str]) -> pd.DataFrame:
    _require_blp()
    s = _session()
    try:
        ref = _open(s, "//blp/refdata")
        out_rows: List[Dict[str,Any]] = []
        CHUNK = 450
        for i in range(0,len(securities),CHUNK):
            req = ref.createRequest("ReferenceDataRequest")
            e_secs = req.getElement("securities")
            for sec in securities[i:i+CHUNK]: e_secs.appendValue(sec)
            e_flds = req.getElement("fields")
            for f in fields: e_flds.appendValue(f)

            for msg in _send(s, ref, req):
                if not msg.hasElement("securityData"): continue
                sd = msg.getElement("securityData")
                for j in range(sd.numValues()):
                    r = sd.getValueAsElement(j)
                    sec = r.getElementAsString("security")
                    fd = r.getElement("fieldData")
                    row = {"bbg": sec}
                    for f in fields:
                        if fd.hasElement(f):
                            row[f] = _elem(fd.getElement(f))
                    out_rows.append(row)
        return pd.DataFrame(out_rows)
    finally:
        s.stop()

def static_snap(securities: List[str], fields: List[str]) -> pd.DataFrame:
    _require_blp()
    s = _session()
    try:
        svc = _open(s, "//blp/staticmktdata")
        out_rows: List[Dict[str,Any]] = []
        CHUNK = 450
        for i in range(0,len(securities),CHUNK):
            req = svc.createRequest("StaticMarketDataRequest")
            e_secs = req.getElement("securities")
            for sec in securities[i:i+CHUNK]: e_secs.appendValue(sec)
            e_flds = req.getElement("fields")
            for f in fields: e_flds.appendValue(f)
            for msg in _send(s, svc, req):
                if not msg.hasElement("securityData"): continue
                sd = msg.getElement("securityData")
                for j in range(sd.numValues()):
                    r = sd.getValueAsElement(j)
                    sec = r.getElementAsString("security")
                    fd = r.getElement("fieldData")
                    row = {"bbg": sec}
                    for f in fields:
                        if fd.hasElement(f):
                            row[f] = _elem(fd.getElement(f))
                    out_rows.append(row)
        return pd.DataFrame(out_rows)
    finally:
        s.stop()

def _elem(e: blpapi.Element):
    try:
        if e.datatype()==blpapi.DataType.STRING: return e.getValueAsString()
        if e.datatype() in (blpapi.DataType.FLOAT64, blpapi.DataType.FLOAT32): return float(e.getValueAsFloat64())
        if e.datatype() in (blpapi.DataType.INT32, blpapi.DataType.INT64): return int(e.getValueAsInteger())
        if e.datatype()==blpapi.DataType.BOOL: return bool(e.getValueAsBool())
        return e.toString()
    except Exception:
        return None

def normalize_ref(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["symbol"]   = out.get("TICKER")
    out["exchange"] = out.get("EXCH_CODE")
    # MIC: prefer ID_MIC_PRIM_EXCH; else map EXCH_CODE
    out["mic"]      = out.get("ID_MIC_PRIM_EXCH")
    out.loc[out["mic"].isna(), "mic"] = out["exchange"].map(EXCH_TO_MIC)
    out["country"]  = out.get("CNTRY_OF_DOMICILE")
    out["name"]     = out.get("SECURITY_NAME")
    out["sector"]   = out.get("GICS_SECTOR_NAME").fillna(out.get("INDUSTRY_SECTOR"))
    out["isin"]     = out.get("ID_ISIN")
    out["ric"]      = out.get("ID_RIC")
    # tags - handle Series properly
    st = out["SECURITY_TYP"].fillna("").astype(str).str.upper() if "SECURITY_TYP" in out.columns else pd.Series([""] * len(out))
    st2 = out["SECURITY_TYP2"].fillna("").astype(str).str.upper() if "SECURITY_TYP2" in out.columns else pd.Series([""] * len(out))
    adrflag = (out["ADR_FLAG"]==True) if "ADR_FLAG" in out.columns else pd.Series([False] * len(out))
    out["is_adr"]   = adrflag.fillna(False)
    out["is_etf"]   = st.eq("ETF") | st.str.contains("ETF", na=False) | st2.str.contains("ETF|ETP", regex=True, na=False)
    out["is_common"]= (~out["is_etf"]) & (~out["is_adr"])
    keep = ["symbol","exchange","mic","country","sector","name","isin","ric","bbg","is_common","is_etf","is_adr"]
    out = out[keep].drop_duplicates(subset=["bbg"]).reset_index(drop=True)
    return out

def fx_needed(crncy: pd.Series) -> List[str]:
    pairs=set()
    for c in crncy.dropna().astype(str):
        if c.upper()!="USD": pairs.add(f"{c.upper()}USD Curncy")
    return sorted(pairs)

def fetch_fx(pairs: List[str]) -> Dict[str,float]:
    if not pairs: return {}
    df = refdata(pairs, ["PX_LAST"])
    fx = {}
    for _,r in df.iterrows():
        sec = r["bbg"]
        px  = r.get("PX_LAST")
        if px: fx[sec.split()[0].upper()] = float(px)
    return fx

# ---------- CLI commands ----------
@app.command()
def beqs(common: str = typer.Option("US_COMMON_PRIMARY"),
         etf:    str = typer.Option("US_ETF_PRIMARY"),
         adr:    str = typer.Option("US_ADR_PRIMARY"),
         screen_type: str = typer.Option("PRIVATE"),
         out: str = typer.Option(str(CAT / "beqs_securities.parquet"))):
    """Pull securities from saved BEQS screens (stocks, ETFs, ADRs)."""
    typer.echo(f"Fetching from BEQS screens:")
    typer.echo(f"  Common stocks: {common}")
    typer.echo(f"  ETFs: {etf}")
    typer.echo(f"  ADRs: {adr}")
    
    secs=[]
    try:
        typer.echo(f"\nPulling {common}...")
        secs += beqs_list(common, screen_type)
        typer.echo(f"  Found {len(secs)} securities")
    except Exception as e:
        typer.echo(f"  [WARN] Could not fetch {common}: {e}")
    
    try:
        typer.echo(f"\nPulling {etf}...")
        etfs = beqs_list(etf, screen_type)
        secs += etfs
        typer.echo(f"  Found {len(etfs)} ETFs")
    except Exception as e:
        typer.echo(f"  [WARN] Could not fetch {etf}: {e}")
    
    try:
        typer.echo(f"\nPulling {adr}...")
        adrs = beqs_list(adr, screen_type)
        secs += adrs
        typer.echo(f"  Found {len(adrs)} ADRs")
    except Exception as e:
        typer.echo(f"  [WARN] Could not fetch {adr}: {e}")
    
    if not secs:
        typer.echo("\n[ERROR] No securities retrieved. Check screen names exist in Terminal.")
        raise typer.Exit(1)
    
    df = pd.DataFrame({"bbg": list(dict.fromkeys(secs))})
    df.to_parquet(out, index=False)
    typer.echo(f"\n[OK] Wrote {out} ({len(df):,} unique securities).")

@app.command()
def refdata_enrich(beqs_path: str = typer.Option(str(CAT / "beqs_securities.parquet")),
                   out: str = typer.Option(str(CAT / "us_universe.parquet"))):
    """Enrich BEQS with refdata; write us_universe.parquet."""
    if not Path(beqs_path).exists(): 
        typer.echo("Missing BEQS list. Run `beqs` first."); raise typer.Exit(2)
    b = pd.read_parquet(beqs_path)
    typer.echo(f"Enriching {len(b):,} securities with Bloomberg refdata...")
    rdf = refdata(b["bbg"].tolist(), REF_FIELDS)
    if rdf.empty:
        typer.echo("No refdata rows returned; check entitlements."); raise typer.Exit(1)
    norm = normalize_ref(rdf)
    norm.to_parquet(out, index=False)
    typer.echo(f"[OK] Wrote {out} ({len(norm):,} rows).")
    typer.echo(f"     Common stocks: {norm['is_common'].sum()}")
    typer.echo(f"     ETFs: {norm['is_etf'].sum()}")
    typer.echo(f"     ADRs: {norm['is_adr'].sum()}")

@app.command()
def stats_cmd(out: str = typer.Option(str(CAT / "stats.parquet")),
          universe_path: str = typer.Option(str(CAT / "us_universe.parquet"))):
    """Build liquidity stats (ADV $ and spread bps)."""
    if not Path(universe_path).exists():
        typer.echo("Missing us_universe.parquet. Run `refdata-enrich` first."); raise typer.Exit(2)
    sm = pd.read_parquet(universe_path)
    typer.echo(f"Fetching snapshot stats for {len(sm):,} securities...")
    st = adv_spread(sm)
    st.to_parquet(out, index=False)
    typer.echo(f"[OK] Wrote {out} ({len(st):,} rows).")

@app.command()
def orats_cmd(universe_path: str = typer.Option(str(CAT / "us_universe.parquet")),
          out: str = typer.Option(str(CAT / "orats_coverage.parquet")),
          max_workers: int = typer.Option(8)):
    """Probe ORATS coverage & canonical symbol forms."""
    if not Path(universe_path).exists():
        typer.echo("Missing us_universe.parquet. Run `refdata-enrich` first."); raise typer.Exit(2)
    sm = pd.read_parquet(universe_path)
    # Focus first on common stocks + ETFs (most optionable); ADRs optional
    symbols = sm["symbol"].dropna().astype(str).unique().tolist()
    typer.echo(f"Checking ORATS coverage for {len(symbols):,} symbols...")
    df = check_orats_coverage(symbols, max_workers=max_workers)
    df.to_parquet(out, index=False)
    ok_count = df['orats_ok'].sum()
    typer.echo(f"[OK] Wrote {out} ({len(df):,} symbols checked, {ok_count:,} available on ORATS).")

@app.command()
def etfs_cmd(out: str = typer.Option(str(CAT / "etf_catalog.parquet"))):
    """Seed sector/country ETF map for sympathy proxies (edit freely)."""
    rows=[]
    sector = [("XLB","Basic Materials"),("XLE","Energy"),("XLF","Financials"),("XLI","Industrials"),
              ("XLK","Information Technology"),("XLP","Consumer Staples"),("XLU","Utilities"),
              ("XLV","Health Care"),("XLY","Consumer Discretionary"),("XLC","Communication Services"),
              ("SMH","Semiconductors"),("SOXX","Semiconductors"),("XBI","Biotech"),("KBE","Banks"),("XOP","Oil & Gas")]
    country = [("SPY","US"),("QQQ","US"),("IWM","US"),("EWJ","JP"),("EWG","DE"),("EWQ","FR"),
               ("EWU","GB"),("EWP","ES"),("EWI","IT"),("EWL","CH"),("EWN","NL"),
               ("EWA","AU"),("EWC","CA"),("EWZ","BR"),("EWT","TW"),("EWY","KR"),("EWH","HK"),
               ("MCHI","CN"),("FXI","CN"),("EWW","MX"),("EZA","ZA"),("INDA","IN"),("EPI","IN")]
    for etf, sec in sector: rows.append({"etf":etf,"type":"sector","sector":sec,"country":None})
    for etf, c  in country: rows.append({"etf":etf,"type":"country","sector":None,"country":c})
    pd.DataFrame(rows).to_parquet(out, index=False)
    typer.echo(f"[OK] Wrote {out} ({len(rows)} ETFs).")

@app.command()
def all_cmd(common: str = typer.Option("US_COMMON_PRIMARY"),
            etf: str = typer.Option("US_ETF_PRIMARY"),
            adr: str = typer.Option("US_ADR_PRIMARY"),
            screen_type: str = typer.Option("PRIVATE"),
            skip_orats: bool = typer.Option(False, help="Skip ORATS coverage check (faster)")):
    """Run end-to-end: BEQS -> Refdata -> Stats -> ETF map (optionally ORATS)."""
    typer.echo("=" * 70)
    typer.echo("US UNIVERSE PIPELINE - FULL BUILD")
    typer.echo("=" * 70)
    
    # Step 1: BEQS
    typer.echo("\n[1/5] Fetching BEQS universes...")
    typer.echo(f"  Common stocks: {common}")
    typer.echo(f"  ETFs: {etf}")
    typer.echo(f"  ADRs: {adr}")
    
    secs = []
    try:
        typer.echo(f"\nPulling {common}...")
        secs += beqs_list(common, screen_type)
        typer.echo(f"  Found {len(secs)} securities")
    except Exception as e:
        typer.echo(f"  [WARN] Could not fetch {common}: {e}")
    
    try:
        typer.echo(f"\nPulling {etf}...")
        etfs_list = beqs_list(etf, screen_type)
        secs += etfs_list
        typer.echo(f"  Found {len(etfs_list)} ETFs")
    except Exception as e:
        typer.echo(f"  [WARN] Could not fetch {etf}: {e}")
    
    try:
        typer.echo(f"\nPulling {adr}...")
        adrs_list = beqs_list(adr, screen_type)
        secs += adrs_list
        typer.echo(f"  Found {len(adrs_list)} ADRs")
    except Exception as e:
        typer.echo(f"  [WARN] Could not fetch {adr}: {e}")
    
    if not secs:
        typer.echo("\n[ERROR] No securities retrieved. Check screen names exist in Terminal.")
        raise typer.Exit(1)
    
    beqs_path = CAT / "beqs_securities.parquet"
    pd.DataFrame({"bbg": list(dict.fromkeys(secs))}).to_parquet(beqs_path, index=False)
    typer.echo(f"\n[OK] Wrote {beqs_path} ({len(set(secs)):,} unique securities).")
    
    # Step 2: Refdata
    typer.echo("\n[2/5] Enriching with Bloomberg refdata...")
    b = pd.read_parquet(beqs_path)
    rdf = refdata(b["bbg"].tolist(), REF_FIELDS)
    if rdf.empty:
        typer.echo("No refdata rows returned; check entitlements."); raise typer.Exit(1)
    norm = normalize_ref(rdf)
    universe_path = CAT / "us_universe.parquet"
    norm.to_parquet(universe_path, index=False)
    typer.echo(f"[OK] Wrote {universe_path} ({len(norm):,} rows).")
    typer.echo(f"     Common stocks: {norm['is_common'].sum()}")
    typer.echo(f"     ETFs: {norm['is_etf'].sum()}")
    typer.echo(f"     ADRs: {norm['is_adr'].sum()}")
    
    # Step 3: Stats (use refdata since static market data not available)
    typer.echo("\n[3/5] Computing liquidity stats via refdata...")
    sm = pd.read_parquet(universe_path)
    typer.echo(f"    Fetching stats for {len(sm):,} securities...")
    snap_fields = ["PX_LAST", "VOLUME_AVG_30D", "VOLUME_AVG_20D", "BID", "ASK", "CRNCY"]
    snap_df = refdata(sm["bbg"].tolist(), snap_fields)
    
    # Merge and compute
    tmp = sm[["bbg","symbol"]].merge(snap_df, on="bbg", how="left")
    
    # ADV USD
    adv_usd = []
    for _, r in tmp.iterrows():
        v = r.get("VOLUME_AVG_30D") if pd.notna(r.get("VOLUME_AVG_30D")) else r.get("VOLUME_AVG_20D")
        px = r.get("PX_LAST")
        # Assuming USD for simplicity (FX conversion would add time)
        if pd.notna(v) and pd.notna(px) and v > 0 and px > 0:
            adv_usd.append(float(v) * float(px))
        else:
            adv_usd.append(None)
    
    # Spread bps
    spreads = []
    for _, r in tmp.iterrows():
        bid, ask = r.get("BID"), r.get("ASK")
        if pd.notna(bid) and pd.notna(ask) and bid > 0 and ask > 0:
            mid = 0.5 * (bid + ask)
            bps = (ask - bid) / mid * 10000.0
            spreads.append(max(bps, 0.0))
        else:
            spreads.append(None)
    
    st = pd.DataFrame({"symbol": tmp["symbol"], "adv_usd": adv_usd, "avg_spread_bps": spreads})
    st = st.groupby("symbol", as_index=False).agg({"adv_usd":"max","avg_spread_bps":"min"})
    
    stats_path = CAT / "stats.parquet"
    st.to_parquet(stats_path, index=False)
    typer.echo(f"[OK] Wrote {stats_path} ({len(st):,} rows).")
    
    # Step 4: ETFs
    typer.echo("\n[4/5] Creating ETF catalog...")
    rows=[]
    sector = [("XLB","Basic Materials"),("XLE","Energy"),("XLF","Financials"),("XLI","Industrials"),
              ("XLK","Information Technology"),("XLP","Consumer Staples"),("XLU","Utilities"),
              ("XLV","Health Care"),("XLY","Consumer Discretionary"),("XLC","Communication Services"),
              ("SMH","Semiconductors"),("SOXX","Semiconductors"),("XBI","Biotech"),("KBE","Banks"),("XOP","Oil & Gas")]
    country = [("SPY","US"),("QQQ","US"),("IWM","US"),("EWJ","JP"),("EWG","DE"),("EWQ","FR"),
               ("EWU","GB"),("EWP","ES"),("EWI","IT"),("EWL","CH"),("EWN","NL"),
               ("EWA","AU"),("EWC","CA"),("EWZ","BR"),("EWT","TW"),("EWY","KR"),("EWH","HK"),
               ("MCHI","CN"),("FXI","CN"),("EWW","MX"),("EZA","ZA"),("INDA","IN"),("EPI","IN")]
    for e, sec in sector: rows.append({"etf":e,"type":"sector","sector":sec,"country":None})
    for e, c  in country: rows.append({"etf":e,"type":"country","sector":None,"country":c})
    etf_path = CAT / "etf_catalog.parquet"
    pd.DataFrame(rows).to_parquet(etf_path, index=False)
    typer.echo(f"[OK] Wrote {etf_path} ({len(rows)} ETFs).")
    
    # Step 5: ORATS (optional)
    if not skip_orats:
        typer.echo("\n[5/5] Checking ORATS coverage...")
        symbols = sm["symbol"].dropna().astype(str).unique().tolist()
        df_orats = check_orats_coverage(symbols, max_workers=8)
        orats_path = CAT / "orats_coverage.parquet"
        df_orats.to_parquet(orats_path, index=False)
        ok_count = df_orats['orats_ok'].sum()
        typer.echo(f"[OK] Wrote {orats_path} ({len(df_orats):,} symbols checked, {ok_count:,} available on ORATS).")
    else:
        typer.echo("\n[5/5] Skipped ORATS coverage check")
    
    typer.echo("\n" + "=" * 70)
    typer.echo("CATALOG BUILD COMPLETE")
    typer.echo("=" * 70)
    typer.echo("\nFiles created:")
    typer.echo("  catalog/us_universe.parquet")
    typer.echo("  catalog/stats.parquet")
    typer.echo("  catalog/etf_catalog.parquet")
    if not skip_orats:
        typer.echo("  catalog/orats_coverage.parquet")
    typer.echo("\nReady to use with: headline-reactor suggest-v2 / watch-v2")

if __name__ == "__main__":
    app()
