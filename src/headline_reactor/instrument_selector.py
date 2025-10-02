from __future__ import annotations
from typing import List, Dict, Optional
from dataclasses import dataclass
from .symbology import Candidate, extract_row_tokens, map_foreign_to_country_etf
from .options import atm_call

@dataclass
class Context:
    label: str
    headline: str
    row_text: str
    wl: set[str]
    uni: dict

def _budget(uni: dict, key: str, default: int) -> int:
    return int(uni.get("budgets", {}).get(key, default))

def _render_equity(symbol: str, uni: dict, label: str, action: str, score: float, why: str) -> Candidate:
    notion = _budget(uni, "equity_usd", 1500)
    ttl = int(uni.get("defaults", {}).get("ttl_sec", 600))
    return Candidate(f"{symbol} {action} ${notion} IOC TTL={ttl//60}m (NEWS: {label})", "EQUITY", why, score)

def _render_etf(symbol: str, uni: dict, label: str, action: str, score: float, why: str) -> Candidate:
    notion = _budget(uni, "equity_usd", 1500)
    ttl = int(uni.get("defaults", {}).get("ttl_sec", 600))
    return Candidate(f"{symbol} {action} ${notion} IOC TTL={ttl//60}m (NEWS: {label})", "ETF", why, score)

def _render_future(code: str, uni: dict, label: str, action: str, score: float, why: str) -> Candidate:
    notion = _budget(uni, "futures_usd", 2000)
    ttl = int(uni.get("defaults", {}).get("ttl_sec", 600))
    return Candidate(f"{code} {action} ${notion} IOC TTL={ttl//60}m (NEWS: {label})", "FUT", why, score)

def _render_fx(code: str, uni: dict, label: str, action: str, score: float, why: str) -> Candidate:
    notion = _budget(uni, "fx_usd", 2000)
    ttl = int(uni.get("defaults", {}).get("ttl_sec", 600))
    return Candidate(f"{code} {action} ${notion} IOC TTL={ttl//60}m (NEWS: {label})", "FX", why, score)

def _render_crypto(proxy: str, uni: dict, label: str, action: str, score: float, why: str) -> Candidate:
    notion = _budget(uni, "crypto_usd", 1500)
    ttl = int(uni.get("defaults", {}).get("ttl_sec", 600))
    return Candidate(f"{proxy} {action} ${notion} IOC TTL={ttl//60}m (NEWS: {label})", "CRYPTO", why, score)

def select_candidates(ctx: Context) -> List[Candidate]:
    """Select best tradeable instruments across all asset classes."""
    uni, wl, headline, label = ctx.uni, ctx.wl, ctx.headline, ctx.label
    ex2etf = uni.get("proxies", {}).get("EXCH_TO_ETF", {})
    sect2etf = uni.get("proxies", {}).get("SECTOR_TO_ETF", {})
    co2sect = uni.get("proxies", {}).get("COMPANY_TO_SECTOR", {})
    fut_front = uni.get("futures", {}).get("fronts", {})
    ccy_etf = uni.get("fx", {}).get("currency_to_etf", {})
    crypto_proxy = uni.get("crypto", {}).get("spot_to_proxy", {})

    tokens = extract_row_tokens(ctx.row_text)
    out: List[Candidate] = []

    # 1) Direct US tickers (highest priority)
    for tk in tokens:
        if " " not in tk and tk in wl:
            act = "BUY"
            if label in ("country_ratings_down","bigtech_pivot"): 
                act = "SELL"
            out.append(_render_equity(tk, uni, label, act, 0.95 if label.startswith("ma_") else 0.75, "direct US ticker"))

            # Option quick idea for single-names on M&A/rumor only
            if label in ("ma_confirmed","ma_rumor"):
                oi = atm_call(tk)
                if oi:
                    out.append(Candidate(f"{oi.line} (NEWS: {label})", "OPTION", oi.rationale, 0.60))

    # 2) Foreign tickers → country ETF
    for tk in tokens:
        if " " in tk:
            etf = map_foreign_to_country_etf(tk, ex2etf)
            if etf and etf in wl:
                out.append(_render_etf(etf, uni, label, "BUY", 0.70, "country ETF proxy"))

    # 3) Company → sector sympathy ETF (e.g., Samsung/Hynix → SMH)
    for name, sector in co2sect.items():
        if name in headline:
            etf = sect2etf.get(sector)
            if etf and etf in wl:
                out.append(_render_etf(etf, uni, label, "BUY", 0.65, f"sector sympathy: {sector}"))

    # 4) Macro keywords → futures/FX/crypto proxies (only if explicitly present)
    H = headline
    if any(k in H for k in ["OIL", "OPEC", "WTI", "CRUDE"]):
        code = fut_front.get("CL")
        if code: out.append(_render_future(code, uni, label, "BUY", 0.60, "oil proxy"))
    if any(k in H for k in ["GOLD", "BULLION"]):
        code = fut_front.get("GC")
        if code: out.append(_render_future(code, uni, label, "BUY", 0.55, "gold proxy"))
    if "EURO" in H or "EUR" in H:
        code = fut_front.get("6E")
        if code: out.append(_render_fx(code, uni, label, "BUY", 0.55, "EUR/USD proxy"))
    if "YEN" in H or "JPY" in H:
        code = fut_front.get("6J")
        if code: out.append(_render_fx(code, uni, label, "BUY", 0.55, "JPY/USD proxy"))
    if "BITCOIN" in H or "BTC" in H:
        proxy = crypto_proxy.get("BTCUSD", "BITO")
        out.append(_render_crypto(proxy, uni, label, "BUY", 0.55, "BTC proxy"))
    if "ETHEREUM" in H or "ETH" in H:
        proxy = crypto_proxy.get("ETHUSD", "ETHE")
        out.append(_render_crypto(proxy, uni, label, "BUY", 0.55, "ETH proxy"))

    # Rank by score, dedup identical instruments keeping highest score
    dedup: dict[str, Candidate] = {}
    for c in out:
        if c.instrument not in dedup or c.score > dedup[c.instrument].score:
            dedup[c.instrument] = c
    return sorted(dedup.values(), key=lambda x: x.score, reverse=True)[:3]

