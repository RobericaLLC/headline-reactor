# build_catalogs.py
from __future__ import annotations
import os, sys, math, json, time, csv
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Iterable, Tuple

import pandas as pd
import requests
from dateutil import tz
from tqdm import tqdm
import typer

# Bloomberg
try:
    import blpapi
except Exception as e:
    blpapi = None

app = typer.Typer(add_completion=False)
CATALOG_DIR = Path("catalog")
CATALOG_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------
# Bloomberg helpers (Request/Response)
# -------------------------------

def require_blp():
    if blpapi is None:
        typer.echo("blpapi not installed. Install Bloomberg Desktop API Python bindings.")
        raise typer.Exit(2)

def _open_session() -> blpapi.Session:
    host = os.getenv("BLP_HOST", "localhost")
    port = int(os.getenv("BLP_PORT", "8194"))
    opts = blpapi.SessionOptions()
    opts.setServerHost(host)
    opts.setServerPort(port)
    sess = blpapi.Session(opts)
    if not sess.start():
        raise RuntimeError("Failed to start Bloomberg session")
    return sess

def _open_service(sess: blpapi.Session, name: str) -> blpapi.Service:
    if not sess.openService(name):
        raise RuntimeError(f"Failed to open Bloomberg service: {name}")
    return sess.getService(name)

def _send_request(sess: blpapi.Session, service: blpapi.Service, request: blpapi.Request) -> List[blpapi.Message]:
    cid = blpapi.CorrelationId()
    sess.sendRequest(request, correlationId=cid)
    out: List[blpapi.Message] = []
    while True:
        ev = sess.nextEvent()
        for msg in ev:
            if msg.correlationIds() and msg.correlationIds()[0] == cid:
                out.append(msg)
        if ev.eventType() == blpapi.Event.RESPONSE:
            break
    return out

def bbg_refdata(securities: List[str], fields: List[str], overrides: Dict[str, Any] | None = None, chunk: int = 450) -> List[Dict[str, Any]]:
    """ReferenceDataRequest (//blp/refdata). Returns list of dicts with requested fields."""
    require_blp()
    sess = _open_session()
    try:
        ref = _open_service(sess, "//blp/refdata")
        out_rows: List[Dict[str, Any]] = []
        for i in range(0, len(securities), chunk):
            secs = securities[i:i+chunk]
            req = ref.createRequest("ReferenceDataRequest")
            e_secs = req.getElement("securities")
            for s in secs:
                e_secs.appendValue(s)
            e_flds = req.getElement("fields")
            for f in fields:
                e_flds.appendValue(f)
            if overrides:
                e_ovr = req.getElement("overrides")
                for k, v in overrides.items():
                    o = e_ovr.appendElement()
                    o.setElement("fieldId", k)
                    o.setElement("value", v)
            msgs = _send_request(sess, ref, req)
            # Parse
            for m in msgs:
                if not m.hasElement("securityData"): 
                    continue
                sd = m.getElement("securityData")
                for j in range(sd.numValues()):
                    rec = sd.getValueAsElement(j)
                    sec = rec.getElementAsString("security")
                    fd = rec.getElement("fieldData")
                    row = {"security": sec}
                    for f in fields:
                        if fd.hasElement(f):
                            val = fd.getElement(f)
                            row[f] = _bbg_any(val)
                    # Attach error if any
                    if rec.hasElement("securityError"):
                        row["_securityError"] = rec.getElement("securityError").toString()
                    out_rows.append(row)
        return out_rows
    finally:
        sess.stop()

def bbg_static(securities: List[str], fields: List[str], chunk: int = 450) -> List[Dict[str, Any]]:
    """StaticMarketDataRequest (//blp/staticmktdata) for snapshot bid/ask, etc."""
    require_blp()
    sess = _open_session()
    try:
        svc = _open_service(sess, "//blp/staticmktdata")
        out_rows: List[Dict[str, Any]] = []
        for i in range(0, len(securities), chunk):
            secs = securities[i:i+chunk]
            req = svc.createRequest("StaticMarketDataRequest")
            e_secs = req.getElement("securities")
            for s in secs:
                e_secs.appendValue(s)
            e_flds = req.getElement("fields")
            for f in fields:
                e_flds.appendValue(f)
            msgs = _send_request(sess, svc, req)
            for m in msgs:
                if not m.hasElement("securityData"): 
                    continue
                sd = m.getElement("securityData")
                for j in range(sd.numValues()):
                    rec = sd.getValueAsElement(j)
                    sec = rec.getElementAsString("security")
                    fd = rec.getElement("fieldData")
                    row = {"security": sec}
                    for f in fields:
                        if fd.hasElement(f):
                            val = fd.getElement(f)
                            row[f] = _bbg_any(val)
                    out_rows.append(row)
        return out_rows
    finally:
        sess.stop()

def bbg_bulk(security: str, bulk_field: str) -> List[Dict[str, Any]]:
    """Request bulk field for a single security (e.g., INDX_MEMBERS, FUT_CHAIN)."""
    require_blp()
    sess = _open_session()
    try:
        ref = _open_service(sess, "//blp/refdata")
        req = ref.createRequest("ReferenceDataRequest")
        req.getElement("securities").appendValue(security)
        req.getElement("fields").appendValue(bulk_field)
        msgs = _send_request(sess, ref, req)
        out: List[Dict[str, Any]] = []
        for m in msgs:
            sd = m.getElement("securityData")
            for j in range(sd.numValues()):
                rec = sd.getValueAsElement(j)
                fd = rec.getElement("fieldData")
                if fd.hasElement(bulk_field):
                    blk = fd.getElement(bulk_field)
                    for r in range(blk.numValues()):
                        el = blk.getValueAsElement(r)
                        out.append(_bbg_bulk_row(el))
        return out
    finally:
        sess.stop()

def _bbg_any(el: blpapi.Element):
    if el.isArray():
        return [ _bbg_any(el.getValueAsElement(i)) if el.isArray() else el.getValue(i) for i in range(el.numValues()) ]
    t = el.datatype()
    try:
        if t == blpapi.DataType.STRING:
            return el.getValueAsString()
        if t == blpapi.DataType.FLOAT64 or t == blpapi.DataType.FLOAT32:
            return float(el.getValueAsFloat64())
        if t == blpapi.DataType.INT32 or t == blpapi.DataType.INT64:
            return int(el.getValueAsInteger())
        if t == blpapi.DataType.BOOL:
            return bool(el.getValueAsBool())
        if t == blpapi.DataType.DATE or t == blpapi.DataType.DATETIME:
            return str(el.getValue())
        if el.isComplexType():
            # Return dict of sub-elements
            return { el.getElementDefinition(i).name(): _bbg_any(el.getElement(i)) for i in range(el.numElements()) }
    except Exception:
        try:
            return el.getValue()
        except Exception:
            return None
    return el.toString()

def _bbg_bulk_row(el: blpapi.Element) -> Dict[str, Any]:
    row = {}
    for i in range(el.numElements()):
        name = el.getElementDefinition(i).name()
        row[name] = _bbg_any(el.getElement(i))
    return row

# -------------------------------
# Catalog builders
# -------------------------------

# Common fields for secmaster
REF_FIELDS = [
    "SECURITY_NAME",
    "TICKER",
    "ID_ISIN",
    "ID_RIC",
    "EXCH_CODE",
    "PRIMARY_EXCHANGE_NAME",
    "ID_MIC_PRIM_EXCH",      # if available
    "CNTRY_OF_DOMICILE",
    "GICS_SECTOR_NAME",      # fallback to INDUSTRY_SECTOR if missing
    "INDUSTRY_SECTOR",
    "CRNCY",
    "ADR_FLAG",
    "ADR_UNDL_TICKER",
    "ADR_SH_PER_ADR"
]

# Snapshot fields for stats
SNAP_FIELDS = ["BID", "ASK", "PX_LAST", "VOLUME_AVG_30D", "VOLUME_AVG_20D", "EQY_SH_OUT", "CRNCY"]

EXCH_TO_MIC_FALLBACK = {
    # US
    "US": None, "N":"XNYS", "UN":"XNYS", "UA":"ARCX", "UW":"XNAS", "UQ":"XNAS",
    # Europe
    "LN":"XLON", "L":"XLON", "FP":"XPAR", "PA":"XPAR", "NA":"XAMS", "AS":"XAMS", "BR":"XBRU",
    "GY":"XETR", "DE":"XETR", "SM":"XMAD", "MC":"XMAD", "MI":"XMIL", "IM":"XMIL",
    "SW":"XSWX", "VX":"XSWX",
    # APAC
    "T":"XTKS", "JP":"XTKS", "HK":"XHKG", "KS":"XKRX", "KQ":"XKOS", "TT":"XTAI", "TW":"XTAI",
    "SS":"XSHG", "SZ":"XSHE"
}

def normalize_equity(security: str) -> str:
    s = security.strip()
    if " " in s and not s.upper().endswith(("EQUITY","INDEX","COMDTY")):
        return s + " Equity"
    if s.isalpha() and len(s)<=6:
        return f"{s} US Equity"
    return s

def expand_index_members(index_ticker: str) -> List[str]:
    """
    Attempts to pull index members via bulk field.
    Common bulk fields:
      - INDX_MEMBERS (newer)
      - INDX_MEMBERS (same string; Bloomberg variations exist)
    """
    bulk_field = "INDX_MEMBERS"
    try:
        rows = bbg_bulk(index_ticker, bulk_field)
    except Exception:
        # some indices use "INDX_MEMBERS" with a different schema; try alternate
        rows = []
    out = []
    for r in rows:
        # Typical key: "Member Ticker And Exchange Code" (string like "AAPL US")
        for k in ("Member Ticker And Exchange Code", "Member Ticker and Exchange Code", "Member Ticker"):
            if k in r and isinstance(r[k], str):
                out.append(normalize_equity(r[k]))
                break
    return list(dict.fromkeys(out))  # dedup keep order

def _fx_pairs_needed(candidates: Iterable[Tuple[str,str]]) -> List[str]:
    """Return FX tickers like EURUSD Curncy for non-USD conversions."""
    pairs = set()
    for crncy, _ in candidates:
        if crncy and crncy.upper() != "USD":
            pairs.add(f"{crncy.upper()}USD Curncy")
    return sorted(pairs)

def _get_fx(sessionless: bool, pairs: List[str]) -> Dict[str, float]:
    if not pairs:
        return {}
    # Use refdata PX_LAST
    rows = bbg_refdata(pairs, ["PX_LAST"])
    out = {}
    for r in rows:
        sec = r.get("security")
        px = r.get("PX_LAST")
        if px: out[sec.split()[0].upper()] = float(px)  # "EURUSD Curncy" -> "EURUSD": px
    return out

def build_secmaster(seeds: List[str], expand_indices: bool = True) -> pd.DataFrame:
    """Build or extend secmaster from a seed universe."""
    # Expand indices to members if asked
    securities: List[str] = []
    for s in seeds:
        if s.upper().endswith("INDEX"):
            securities += expand_index_members(s)
        else:
            securities.append(normalize_equity(s))
    securities = list(dict.fromkeys(securities))
    if not securities:
        return pd.DataFrame()

    # Fetch reference data
    rows = bbg_refdata(securities, REF_FIELDS)
    df = pd.DataFrame(rows)
    # Choose sector col (prefer GICS)
    if "GICS_SECTOR_NAME" in df and df["GICS_SECTOR_NAME"].notna().any():
        df["sector"] = df["GICS_SECTOR_NAME"]
    else:
        df["sector"] = df.get("INDUSTRY_SECTOR")
    # Exchange/MIC
    if "ID_MIC_PRIM_EXCH" in df and df["ID_MIC_PRIM_EXCH"].notna().any():
        df["mic"] = df["ID_MIC_PRIM_EXCH"]
    else:
        df["mic"] = df["EXCH_CODE"].map(EXCH_TO_MIC_FALLBACK).fillna(df["EXCH_CODE"])
    # Country
    df["country"] = df.get("CNTRY_OF_DOMICILE")
    # Name
    df["name"] = df.get("SECURITY_NAME")
    # Symbol + Exchange code
    df["symbol"] = df.get("TICKER")
    df["exchange"] = df.get("EXCH_CODE")
    # ADR link (US ADR symbol if any)
    adr_flag = df.get("ADR_FLAG")
    if adr_flag is not None:
        # If this row IS an ADR, we also want the US ticker (already in 'symbol')
        # If it's a foreign local with an ADR, ADR_UNDL_TICKER is often the local root; keep what we can.
        pass
    # RIC / ISIN / BBG security string
    df["isin"] = df.get("ID_ISIN")
    df["ric"]  = df.get("ID_RIC")
    df["bbg"]  = df.get("security")

    # Only keep essentials
    keep = ["symbol","exchange","mic","country","sector","name","isin","ric","bbg"]
    # Add a best-effort ADR column: When the row itself is a US listing or ADR, 'adr_us' = symbol if CNTRY_OF_DOMICILE != 'US' or ADR_FLAG==True
    df["adr_us"] = None
    if "ADR_FLAG" in df.columns:
        df.loc[df["ADR_FLAG"]==True, "adr_us"] = df["symbol"]
    # If it's a US listing with non-US domicile, treat as ADR-like
    if "CNTRY_OF_DOMICILE" in df.columns:
        df.loc[(df["CNTRY_OF_DOMICILE"].notna()) & (df["CNTRY_OF_DOMICILE"].str.upper()!="US") & (df["exchange"].isin(["US","N","UN","UW","UQ"])), "adr_us"] = df["symbol"]

    out = df[keep + ["adr_us"]].copy()
    out.drop_duplicates(subset=["bbg"], inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out

def build_stats(secmaster: pd.DataFrame) -> pd.DataFrame:
    """Compute ADV (USD) and snapshot spread bps from Bloomberg static market data."""
    secs = secmaster["bbg"].tolist()
    snap = pd.DataFrame(bbg_static(secs, SNAP_FIELDS))
    if snap.empty:
        return pd.DataFrame(columns=["symbol","adv_usd","avg_spread_bps"])

    # Merge on security string
    tmp = secmaster[["bbg","symbol","exchange","mic","country"]].merge(snap, how="left", left_on="bbg", right_on="security")
    # FX conversions
    needed = []
    for _, r in tmp.iterrows():
        cur = r.get("CRNCY")
        if isinstance(cur, str) and cur.upper()!="USD":
            needed.append((cur, r["symbol"]))
    fx_map = _get_fx(False, _fx_pairs_needed(needed))
    def fx_to_usd(crncy: str) -> float:
        if not isinstance(crncy, str) or crncy.upper()=="USD":
            return 1.0
        pair = (crncy.upper()+"USD")
        return float(fx_map.get(pair, 0.0)) or 0.0

    # ADV candidates: VOLUME_AVG_30D or VOLUME_AVG_20D
    vol = tmp.get("VOLUME_AVG_30D")
    if vol is None or vol.isna().all():
        vol = tmp.get("VOLUME_AVG_20D")
    px = tmp.get("PX_LAST")
    cr = tmp.get("CRNCY")

    adv_usd = []
    for i, r in tmp.iterrows():
        v = r.get("VOLUME_AVG_30D")
        if v is None or (isinstance(v,float) and math.isnan(v)):
            v = r.get("VOLUME_AVG_20D")
        price = r.get("PX_LAST")
        fxv = fx_to_usd(r.get("CRNCY"))
        if v and price and fxv:
            adv_usd.append(float(v) * float(price) * float(fxv))
        else:
            adv_usd.append(None)

    # Spread bps from snapshot bid/ask
    spreads = []
    for _, r in tmp.iterrows():
        bid, ask = r.get("BID"), r.get("ASK")
        if bid and ask and bid>0 and ask>0:
            mid = 0.5*(bid+ask)
            bps = (ask - bid)/mid * 10000.0
            spreads.append(max(bps, 0.0))
        else:
            spreads.append(None)

    out = pd.DataFrame({
        "symbol": tmp["symbol"],
        "adv_usd": adv_usd,
        "avg_spread_bps": spreads
    })
    # de-dup on symbol (keep max ADV if multiple lines)
    out = out.groupby("symbol", as_index=False).agg({"adv_usd":"max","avg_spread_bps":"min"})
    return out

def write_parquet(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)

# -------------------------------
# ETF catalog (seed + editable)
# -------------------------------

SECTOR_ETFS = [
    ("XLB","Basic Materials"), ("XLE","Energy"), ("XLF","Financials"), ("XLI","Industrials"),
    ("XLK","Information Technology"), ("XLP","Consumer Staples"), ("XLU","Utilities"),
    ("XLV","Health Care"), ("XLY","Consumer Discretionary"), ("XLC","Communication Services"),
    ("SMH","Semiconductors"), ("SOXX","Semiconductors"), ("XBI","Biotech"),
    ("KBE","Banks"), ("XOP","Oil & Gas"), ("IGV","Software")
]

COUNTRY_ETFS = [
    ("SPY","US"), ("QQQ","US"), ("IWM","US"),
    ("EWJ","JP"), ("EWG","DE"), ("EWQ","FR"), ("EWU","GB"),
    ("EWP","ES"), ("EWI","IT"), ("EWL","CH"), ("EWN","NL"),
    ("EWA","AU"), ("EWC","CA"), ("EWZ","BR"), ("EWT","TW"),
    ("EWY","KR"), ("EWH","HK"), ("MCHI","CN"), ("FXI","CN"),
    ("EWW","MX"), ("EZA","ZA"), ("EPI","IN"), ("INDA","IN")
]

def build_etf_catalog() -> pd.DataFrame:
    rows = []
    for etf, sector in SECTOR_ETFS:
        rows.append({"etf": etf, "type":"sector", "sector":sector, "country":None, "name":f"{etf} {sector}"})
    for etf, ctry in COUNTRY_ETFS:
        rows.append({"etf": etf, "type":"country", "sector":None, "country":ctry, "name":f"{etf} {ctry}"})
    return pd.DataFrame(rows)

# -------------------------------
# Futures front helper (optional)
# -------------------------------

DEFAULT_ROOTS = ["ES","NQ","CL","GC","ZN","6E","6J"]

def try_futures_fronts(roots: List[str]) -> Dict[str,str]:
    """Best effort: query Bloomberg FUT_CHAIN bulk to choose next tradable."""
    fronts: Dict[str,str] = {}
    today = datetime.utcnow().date()
    for root in roots:
        # Bloomberg chain security naming differs by asset; commonly "<ROOT> <Cmdty>"
        sec = f"{root} Comdty"
        try:
            chain = bbg_bulk(sec, "FUT_CHAIN")
        except Exception:
            chain = []
        # chain rows often include fields like "Futures Ticker", "Last Trade Date"
        chosen = None
        for r in chain:
            ft = r.get("Futures Ticker") or r.get("security") or ""
            ldt = r.get("Last Trade Date") or r.get("Last Tradeable Date") or r.get("Last Tradeable Dt")
            try:
                dt = datetime.strptime(str(ldt)[:10], "%Y-%m-%d").date()
            except Exception:
                dt = None
            if ft and dt and dt > today:
                # Prefer the nearest eligible contract not inside delivery (very rough)
                chosen = ft.split()[0]  # e.g., "ESZ5"
                break
        if chosen:
            fronts[root] = chosen
    return fronts

# -------------------------------
# CLI
# -------------------------------

@app.command()
def secmaster(seed_file: Optional[str] = typer.Option(None, help="Text file with one security per line (e.g., 'AAPL US Equity', '005930 KS Equity', 'SPX Index')"),
              seeds: Optional[str] = typer.Option(None, help="Comma-separated tickers or indices"),
              add_indices: str = typer.Option("SPX Index,NDX Index,RTY Index,SX5E Index,DAX Index,CAC Index,UKX Index", help="Index tickers to expand (comma-separated)"),
              out: str = typer.Option(str(CATALOG_DIR / "secmaster.parquet"))):
    """
    Build/extend catalog/secmaster.parquet from Bloomberg.
    """
    if blpapi is None:
        typer.echo("blpapi not installed; cannot build secmaster.")
        raise typer.Exit(2)

    seed_list: List[str] = []
    if seed_file:
        seed_list += [line.strip() for line in Path(seed_file).read_text().splitlines() if line.strip()]
    if seeds:
        seed_list += [s.strip() for s in seeds.split(",") if s.strip()]
    # Always include some core ETFs so proxies are present
    seed_list += [f"{etf} US Equity" for etf,_ in SECTOR_ETFS] + [f"{etf} US Equity" for etf,_ in COUNTRY_ETFS]
    # Add index expansion
    if add_indices:
        seed_list += [s.strip() for s in add_indices.split(",") if s.strip()]
    seed_list = list(dict.fromkeys(seed_list))

    typer.echo(f"Resolving ~{len(seed_list)} seeds via Bloomberg...")
    df = build_secmaster(seed_list, expand_indices=True)
    if df.empty:
        typer.echo("No rows returned; check entitlements and seeds.")
        raise typer.Exit(1)
    write_parquet(df, Path(out))
    typer.echo(f"Wrote {out} with {len(df):,} rows.")

@app.command()
def stats(secmaster_path: str = typer.Option(str(CATALOG_DIR / "secmaster.parquet")),
          out: str = typer.Option(str(CATALOG_DIR / "stats.parquet"))):
    """
    Build/refresh catalog/stats.parquet using Bloomberg snapshot fields (BID/ASK, ADV).
    """
    if blpapi is None:
        typer.echo("blpapi not installed; cannot build stats.")
        raise typer.Exit(2)

    if not Path(secmaster_path).exists():
        typer.echo("secmaster.parquet not found. Run `secmaster` first.")
        raise typer.Exit(2)

    sm = pd.read_parquet(secmaster_path)
    typer.echo(f"Fetching snapshot stats for {len(sm):,} securities...")
    st = build_stats(sm)
    write_parquet(st, Path(out))
    typer.echo(f"Wrote {out} with {len(st):,} rows.")

@app.command()
def etfs(out: str = typer.Option(str(CATALOG_DIR / "etf_catalog.parquet"))):
    """
    Write a minimal ETF map (sector + country). Edit this file freely to add more.
    """
    df = build_etf_catalog()
    write_parquet(df, Path(out))
    typer.echo(f"Wrote {out} with {len(df):,} ETFs.")

@app.command()
def futures_roll(out: str = typer.Option(str(CATALOG_DIR / "futures_roll.yml")),
                 roots: str = typer.Option(",".join(DEFAULT_ROOTS), help="Comma-separated futures roots (ES,NQ,CL,GC,ZN,6E,6J)"),
                 pin_only: bool = typer.Option(False, help="Write pinned defaults only (skip auto chain lookup)")):
    """
    Attempt to compute/pin current front contracts for common roots.
    """
    m = {}
    if not pin_only and blpapi is not None:
        try:
            m.update(try_futures_fronts([r.strip().upper() for r in roots.split(",") if r.strip()]))
        except Exception:
            pass
    # If any missing, pin sensible defaults (edit as you like)
    defaults = {"ES":"ESZ4","NQ":"NQZ4","CL":"CLX4","GC":"GCZ4","ZN":"ZNZ4","6E":"6EZ4","6J":"6JZ4"}
    for k,v in defaults.items():
        m.setdefault(k,v)
    text = "fronts:\n" + "\n".join([f"  {k}: {v}" for k,v in sorted(m.items())]) + "\n"
    Path(out).write_text(text)
    typer.echo(f"Wrote {out}:\n{text}")

if __name__ == "__main__":
    app()

