from __future__ import annotations
import os, json
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI

@dataclass
class LLMResult:
    action_line: Optional[str]
    rationale: Optional[str]
    confidence: float

SYS = (
 "You are a fast, risk-aware trading headlines assistant. "
 "Given a SHORT market headline, output a JSON object with fields: "
 "`action_line` (one-line pasteable plan like 'EWP BUY $1500 IOC TTL=30m (NEWS: ratings_up_spain)'), "
 "`confidence` (0..1), and short `rationale`. "
 "If ambiguous/macro, set `action_line`='NO ACTION (macro_ambiguous)'. "
 "Never invent tickers; prefer EWP for 'SPAIN'."
)

def suggest_with_llm(headline: str, model: Optional[str] = None, temperature: float = 0.1) -> LLMResult:
    """Uses OpenAI Chat Completions API. Headline text only (no screenshots)."""
    if not int(os.getenv("LLM_ENABLED", "0")):
        return LLMResult(None, None, 0.0)

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    mdl = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    response = client.chat.completions.create(
        model=mdl,
        messages=[
            {"role": "system", "content": SYS},
            {"role": "user", "content": f"HEADLINE: {headline}"}
        ],
        response_format={"type": "json_object"},
        temperature=temperature,
    )
    
    data = json.loads(response.choices[0].message.content)
    return LLMResult(
        action_line=data.get("action_line"),
        rationale=data.get("rationale"),
        confidence=float(data.get("confidence", 0.0))
    )

