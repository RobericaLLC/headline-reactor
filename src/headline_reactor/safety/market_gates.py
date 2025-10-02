from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import pandas_market_calendars as mcal
import pytz

ET = pytz.timezone("America/New_York")

@dataclass
class SessionInfo:
    is_open: bool
    minutes_to_close: int
    reason: str

class USMarketCalendar:
    """Market session calendar for US equities (NYSE/Nasdaq)."""
    
    def __init__(self):
        self.nyse = mcal.get_calendar("XNYS")

    def session_info(self, now: Optional[datetime] = None) -> SessionInfo:
        """Get current market session status."""
        now = now or datetime.now(ET)
        
        # Get schedule for today
        sched = self.nyse.schedule(
            start_date=(now.date() - timedelta(days=7)), 
            end_date=(now.date() + timedelta(days=7))
        )
        
        # Find today's session (handles holidays/early-closes)
        today = sched[sched.index.date == now.date()]
        if today.empty:
            return SessionInfo(False, 0, "holiday/closed")
        
        open_ts = ET.localize(today["market_open"].iloc[0].to_pydatetime().replace(tzinfo=None))
        close_ts = ET.localize(today["market_close"].iloc[0].to_pydatetime().replace(tzinfo=None))
        
        if now < open_ts:
            return SessionInfo(False, int((close_ts - open_ts).total_seconds() // 60), "pre-open")
        if now > close_ts:
            return SessionInfo(False, 0, "post-close")
        
        return SessionInfo(True, max(0, int((close_ts - now).total_seconds() // 60)), "open")
    
    def is_market_open(self, now: Optional[datetime] = None) -> bool:
        """Quick check if market is currently open."""
        return self.session_info(now).is_open

