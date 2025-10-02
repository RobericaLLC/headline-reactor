from __future__ import annotations
"""Utility helpers for headline-reactor."""

def format_ttl(seconds: int) -> str:
    """Format TTL seconds into human-readable string."""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    return f"{minutes}m"

