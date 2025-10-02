from __future__ import annotations
import time, hashlib, sys
from pathlib import Path
import typer
from .capture import find_news_window_rect, grab_topline
from .ocr import ocr_topline
from .rules import classify, map_ticker
from .planner import load_cfg, plan_from_label
from .llm import suggest_with_llm

app = typer.Typer(add_completion=False)

@app.command()
def suggest(headline: str,
            config: str = typer.Option("newsreactor.yml"),
            whitelist: str = typer.Option("EWP,EA,SPY,FEZ"),
            llm: bool = typer.Option(False, help="Use LLM assist (requires OPENAI_API_KEY, LLM_ENABLED=1)")
            ):
    headline = headline.upper()
    cfg = load_cfg(Path(config))
    wl = set([w.strip().upper() for w in whitelist.split(",") if w.strip()])
    label = classify(headline) or "macro_ambiguous"
    ticker = map_ticker(headline, wl)
    plan = plan_from_label(label, ticker, cfg)
    # optional LLM overlay
    if llm:
        llmres = suggest_with_llm(headline)
        if llmres.action_line:
            plan.line = llmres.action_line
            plan.reason += f"; llm({llmres.confidence:.2f})"
    typer.echo(plan.line)

@app.command()
def watch(config: str = typer.Option("newsreactor.yml"),
          window_title: str = typer.Option("News Alerts"),
          whitelist: str = typer.Option("EWP,EA,SPY,FEZ"),
          poll_ms: int = typer.Option(250),
          llm: bool = typer.Option(False)):
    rect = find_news_window_rect(window_title)
    if not rect:
        typer.echo("Could not find News Alerts window; make it visible."); raise typer.Exit(1)
    cfg = load_cfg(Path(config))
    wl = set([w.strip().upper() for w in whitelist.split(",") if w.strip()])
    seen: set[str] = set()
    typer.echo("Watching top headline... Ctrl+C to exit.")
    try:
        while True:
            img = grab_topline(rect)
            text = ocr_topline(img)
            if not text: 
                time.sleep(poll_ms/1000); continue
            h = hashlib.sha256(text.encode()).hexdigest()[:12]
            if h in seen: 
                time.sleep(poll_ms/1000); continue
            seen.add(h)
            label = classify(text) or "macro_ambiguous"
            ticker = map_ticker(text, wl)
            plan = plan_from_label(label, ticker, cfg)
            if llm:
                llmres = suggest_with_llm(text)
                if llmres.action_line:
                    plan.line = llmres.action_line
            typer.echo(f"[NEWS] {text}\n → {plan.line}\n")
            time.sleep(poll_ms/1000)
    except KeyboardInterrupt:
        pass

