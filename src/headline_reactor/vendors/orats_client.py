# src/headline_reactor/vendors/orats_client.py
from __future__ import annotations
import os, time, json, hashlib
from pathlib import Path
from typing import Dict, Optional
import requests

BASE = "https://api.orats.io/datav2"
CACHE = Path("data/cache/orats")
CACHE.mkdir(parents=True, exist_ok=True)
TOKEN = os.getenv("ORATS_TOKEN")

class OratsClient:
    """Resilient ORATS client with TTL cache and exponential backoff."""
    
    def __init__(self, ttl_sec: int = 15):
        assert TOKEN, "Set ORATS_TOKEN environment variable"
        self.ttl = ttl_sec
        self.s = requests.Session()
        self.s.headers.update({"Accept": "text/csv"})

    def _cache_path(self, endpoint: str, params: Dict[str,str]) -> Path:
        """Generate cache file path from endpoint and params."""
        key = json.dumps([endpoint, sorted(params.items())], separators=(",",":"))
        h = hashlib.sha1(key.encode()).hexdigest()
        return CACHE / f"{endpoint.replace('/','_')}_{h}.csv"

    def _get(self, endpoint: str, params: Dict[str,str]) -> str:
        """Get data with TTL cache and retry logic."""
        params = dict(params)
        params["token"] = TOKEN
        
        # Check cache first
        p = self._cache_path(endpoint, params)
        if p.exists() and (time.time() - p.stat().st_mtime) < self.ttl:
            return p.read_text()
        
        # Fetch with retry and exponential backoff for 429/5xx
        url = f"{BASE}/{endpoint}"
        for i in range(4):
            try:
                r = self.s.get(url, params=params, timeout=8)
                if r.status_code == 200:
                    # Cache successful response
                    p.write_text(r.text)
                    return r.text
                
                # Retry on rate limit or server errors
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(0.3 * (2**i))
                    continue
                
                r.raise_for_status()
            except requests.exceptions.Timeout:
                if i < 3:
                    time.sleep(0.3 * (2**i))
                    continue
                raise
        
        # Final attempt
        r.raise_for_status()
        return r.text

    def summaries(self, ticker: str) -> str:
        """Get live one-minute summaries for a ticker."""
        return self._get("live/one-minute/summaries", {"ticker": ticker})

    def chain(self, ticker: str) -> str:
        """Get live one-minute options chain for a ticker."""
        return self._get("live/one-minute/strikes/chain", {"ticker": ticker})

    def option(self, opra: str) -> str:
        """Get live one-minute data for a specific option (OPRA code)."""
        return self._get("live/one-minute/strikes/option", {"ticker": opra})

