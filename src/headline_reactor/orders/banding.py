from __future__ import annotations

def marketable_limit(side: str, bid: float, ask: float, offset_bps: int, max_slip_bps: int) -> float:
    """
    Calculate marketable limit price with offset and max slippage protection.
    
    Args:
        side: "BUY" or "SELL"
        bid: Current bid price
        ask: Current ask price
        offset_bps: Offset in basis points from near touch
        max_slip_bps: Maximum slippage allowed in basis points
    
    Returns:
        Limit price rounded to 4 decimals
    """
    # Calculate mid if both sides present
    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else (ask if side == "BUY" else bid)
    
    # Calculate band offset
    band = mid * (offset_bps / 10000.0)
    
    # Base price: cross the spread by offset
    px = (ask + band) if side == "BUY" else (bid - band)
    
    # Calculate worst acceptable price (max slippage cap)
    worst = mid * (1 + (max_slip_bps / 10000.0)) if side == "BUY" else mid * (1 - (max_slip_bps / 10000.0))
    
    # Return capped price
    if side == "BUY":
        return round(min(px, worst), 4)
    else:
        return round(max(px, worst), 4)

def format_price_band(symbol: str, side: str, bid: float, ask: float, 
                     offset_bps: int = 8, max_slip_bps: int = 40) -> str:
    """
    Format a price-banded order string.
    
    Returns:
        Formatted string like "AAPL BUY @ 255.60 (mid=255.45, band=+8bps, cap=40bps)"
    """
    limit_px = marketable_limit(side, bid, ask, offset_bps, max_slip_bps)
    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
    
    return f"{symbol} {side} @ {limit_px:.2f} (mid={mid:.2f}, band=+{offset_bps}bps, cap={max_slip_bps}bps)"

