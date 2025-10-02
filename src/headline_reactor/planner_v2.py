from __future__ import annotations
from dataclasses import dataclass
from typing import List
from pathlib import Path
from .instrument_selector_v2 import select_candidates

@dataclass
class Plan:
    """A trade plan with confidence score."""
    line: str
    reason: str
    label: str
    confidence: float

def plans_universe_v2(label: str, headline: str, row_text: str, cfg_path: str = "universe_v2.yml") -> List[Plan]:
    """Generate universe-wide trade plans (v2 architecture)."""
    cands = select_candidates(label, headline, row_text, Path(cfg_path))
    
    return [
        Plan(
            line=c.line,
            reason=c.rationale,
            label=label,
            confidence=c.score
        )
        for c in cands
    ]

