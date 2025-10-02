from __future__ import annotations
from collections import deque
from dataclasses import dataclass

@dataclass
class CircuitState:
    """Circuit breaker configuration."""
    rolling_ms: int = 60_000      # 1 minute rolling window
    max_errors: int = 3            # Max errors before degrading
    max_timeouts: int = 2          # Max timeouts before degrading
    max_wide_spreads: int = 2      # Max wide-spread events

class Circuit:
    """Circuit breaker for operational safety during market stress."""
    
    def __init__(self, cfg: CircuitState):
        self.cfg = cfg
        self.err = deque()      # error timestamps (ms)
        self.to  = deque()      # timeout timestamps (ms)
        self.wide= deque()      # wide-spread event timestamps (ms)

    def _prune(self, now_ms: int):
        """Remove events outside rolling window."""
        w = self.cfg.rolling_ms
        for q in (self.err, self.to, self.wide):
            while q and now_ms - q[0] > w:
                q.popleft()

    def record_error(self, now_ms: int):
        """Record an error event."""
        self.err.append(now_ms)
    
    def record_timeout(self, now_ms: int):
        """Record a timeout event."""
        self.to.append(now_ms)
    
    def record_wide_spread(self, now_ms: int):
        """Record a wide-spread event."""
        self.wide.append(now_ms)

    def should_degrade(self, now_ms: int) -> bool:
        """Check if we should degrade to safe mode."""
        self._prune(now_ms)
        return (len(self.err) >= self.cfg.max_errors or
                len(self.to) >= self.cfg.max_timeouts or
                len(self.wide) >= self.cfg.max_wide_spreads)

    def next_mode(self, now_ms: int) -> str:
        """Get recommended operating mode."""
        return "ETF_ONLY" if self.should_degrade(now_ms) else "FULL"
    
    def reset(self):
        """Reset all circuit breaker state."""
        self.err.clear()
        self.to.clear()
        self.wide.clear()

