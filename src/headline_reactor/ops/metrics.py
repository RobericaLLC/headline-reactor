from __future__ import annotations
import socket
import time
from typing import Optional

class Statsd:
    """Minimal StatsD client for SLO metrics (optional - no-op if not configured)."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8125, ns: str = "reactor", enabled: bool = False):
        self.addr = (host, port)
        self.ns = ns
        self.enabled = enabled
        if self.enabled:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setblocking(False)
        else:
            self.sock = None

    def timing(self, key: str, ms: int):
        """Record timing metric."""
        if not self.enabled:
            return
        try:
            self.sock.sendto(f"{self.ns}.{key}:{ms}|ms".encode(), self.addr)
        except Exception:
            pass  # Non-blocking

    def incr(self, key: str, n: int = 1):
        """Increment counter."""
        if not self.enabled:
            return
        try:
            self.sock.sendto(f"{self.ns}.{key}:{n}|c".encode(), self.addr)
        except Exception:
            pass

    def gauge(self, key: str, val: float):
        """Set gauge value."""
        if not self.enabled:
            return
        try:
            self.sock.sendto(f"{self.ns}.{key}:{val}|g".encode(), self.addr)
        except Exception:
            pass

# Global metrics instance (configure with STATSD_ENABLED=1 in env)
import os
_enabled = os.getenv("STATSD_ENABLED", "0") == "1"
_host = os.getenv("STATSD_HOST", "127.0.0.1")
_port = int(os.getenv("STATSD_PORT", "8125"))

metrics = Statsd(host=_host, port=_port, ns="reactor", enabled=_enabled)

