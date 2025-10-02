from __future__ import annotations
import time, hashlib
from pathlib import Path
import typer
from dotenv import load_dotenv
from .capture import find_news_window_rect, grab_topline
from .ocr import ocr_topline
from .rules import classify, map_ticker
from .planner import load_cfg, plans_from_headline
from .llm import suggest_with_llm

# Load environment variables from .env file
load_dotenv()

app = typer.Typer(add_completion=False)

@app.command()
def suggest(headline: str,
            config: str = typer.Option("newsreactor.yml"),
            whitelist: str = typer.Option("EWP,EA,SPY,FEZ,SMH,SOXX,EWY,AAPL,META"),
            llm: bool = typer.Option(False, help="Use LLM assist (requires OPENAI_API_KEY, LLM_ENABLED=1)")
            ):
    """Analyze a single headline and suggest trade actions."""
    headline = headline.upper()
    cfg = load_cfg(Path(config))
    wl = set([w.strip().upper() for w in whitelist.split(",") if w.strip()])
    label = classify(headline) or "macro_ambiguous"
    primary = map_ticker(headline, wl)
    plans = plans_from_headline(label, headline, primary, cfg, wl)
    
    # Optional LLM overlay for the first plan only (kept off by default)
    if llm and plans and plans[0].symbol in wl:
        llmres = suggest_with_llm(headline)
        if llmres.action_line:
            plans[0].line = llmres.action_line
    
    for p in plans:
        typer.echo(p.line)

@app.command()
def watch(config: str = typer.Option("newsreactor.yml"),
          window_title: str = typer.Option("Alert Catcher"),
          whitelist: str = typer.Option("EWP,EA,SPY,FEZ,SMH,SOXX,EWY,AAPL,META"),
          poll_ms: int = typer.Option(250),
          roi_top: int = typer.Option(115, help="Top px offset for first alert row"),
          roi_height: int = typer.Option(20, help="Row height in pixels"),
          llm: bool = typer.Option(False)):
    """Watch Bloomberg Alert Catcher and generate trade suggestions in real-time."""
    rect = find_news_window_rect(window_title)
    if not rect:
        typer.echo(f"Could not find '{window_title}' window; make it visible."); 
        raise typer.Exit(1)
    
    cfg = load_cfg(Path(config))
    wl = set([w.strip().upper() for w in whitelist.split(",") if w.strip()])
    seen: set[str] = set()
    
    typer.echo(f"Watching '{window_title}'... Ctrl+C to exit.")
    typer.echo(f"Whitelist: {', '.join(sorted(wl))}")
    typer.echo("")
    
    try:
        while True:
            img = grab_topline(rect, roi_top, roi_height)
            text = ocr_topline(img)
            if not text: 
                time.sleep(poll_ms/1000)
                continue
            
            h = hashlib.sha256(text.encode()).hexdigest()[:12]
            if h in seen: 
                time.sleep(poll_ms/1000)
                continue
            
            seen.add(h)
            text = text.upper()
            label = classify(text) or "macro_ambiguous"
            primary = map_ticker(text, wl)
            plans = plans_from_headline(label, text, primary, cfg, wl)
            
            if llm and plans and plans[0].symbol in wl:
                llmres = suggest_with_llm(text)
                if llmres.action_line:
                    plans[0].line = llmres.action_line
            
            typer.echo(f"[NEWS] {text}")
            for p in plans: 
                typer.echo(f" -> {p.line}")
            typer.echo("")
            
            time.sleep(poll_ms/1000)
    except KeyboardInterrupt:
        pass
