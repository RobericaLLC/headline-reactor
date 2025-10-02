from __future__ import annotations
import time, hashlib
from pathlib import Path
import typer
from dotenv import load_dotenv
from .capture import find_news_window_rect, grab_topline
from .ocr import ocr_topline
from .rules import classify, map_ticker
from .planner import load_cfg, plans_from_headline, plans_universe
from .llm import suggest_with_llm

# Load environment variables from .env file
load_dotenv()

app = typer.Typer(add_completion=False)

@app.command()
def suggest(headline: str,
            config: str = typer.Option("newsreactor.yml"),
            universe: str = typer.Option("universe.yml"),
            whitelist: str = typer.Option("SPY,QQQ,IWM,EWP,EWY,EWJ,EWG,EWH,SMH,SOXX,AAPL,MSFT,META,NVDA,EA,BITO,ETHE"),
            llm: bool = typer.Option(False, help="Use LLM assist (requires OPENAI_API_KEY, LLM_ENABLED=1)"),
            use_universe: bool = typer.Option(True, help="Use universe-aware cross-asset planner")
            ):
    """Analyze a single headline and suggest trade actions across all asset classes."""
    headline = headline.upper()
    cfg = load_cfg(Path(config))
    wl = set([w.strip().upper() for w in whitelist.split(",") if w.strip()])
    label = classify(headline) or "macro_ambiguous"
    
    # Use universe-aware planner if available and enabled
    if use_universe and Path(universe).exists():
        plans = plans_universe(label, headline, headline, cfg, Path(universe), wl)
    else:
        # Fallback to simple planner
        primary = map_ticker(headline, wl)
        plans = plans_from_headline(label, headline, primary, cfg, wl)
    
    # Optional LLM overlay for the first plan only (kept off by default)
    if llm and plans:
        llmres = suggest_with_llm(headline)
        if llmres.action_line:
            plans[0].line = llmres.action_line
    
    for p in plans:
        typer.echo(p.line)

@app.command()
def watch(config: str = typer.Option("newsreactor.yml"),
          universe: str = typer.Option("universe.yml"),
          window_title: str = typer.Option("Alert Catcher"),
          whitelist: str = typer.Option("SPY,QQQ,IWM,EWP,EWY,EWJ,EWG,EWH,SMH,SOXX,AAPL,MSFT,META,NVDA,EA,BITO,ETHE"),
          poll_ms: int = typer.Option(250),
          roi_top: int = typer.Option(115, help="Top px offset for first alert row"),
          roi_height: int = typer.Option(20, help="Row height in pixels"),
          llm: bool = typer.Option(False),
          use_universe: bool = typer.Option(True, help="Use universe-aware cross-asset planner")):
    """Watch Bloomberg Alert Catcher and generate trade suggestions in real-time."""
    rect = find_news_window_rect(window_title)
    if not rect:
        typer.echo(f"Could not find '{window_title}' window; make it visible."); 
        raise typer.Exit(1)
    
    cfg = load_cfg(Path(config))
    wl = set([w.strip().upper() for w in whitelist.split(",") if w.strip()])
    seen: set[str] = set()
    
    mode = "universe-aware" if use_universe and Path(universe).exists() else "simple"
    typer.echo(f"Watching '{window_title}' ({mode} mode)... Ctrl+C to exit.")
    typer.echo(f"Whitelist: {', '.join(sorted(wl))}")
    typer.echo("")
    
    try:
        while True:
            img = grab_topline(rect, roi_top, roi_height)
            row_text = ocr_topline(img)
            if not row_text: 
                time.sleep(poll_ms/1000)
                continue
            
            h = hashlib.sha256(row_text.encode()).hexdigest()[:12]
            if h in seen: 
                time.sleep(poll_ms/1000)
                continue
            
            seen.add(h)
            row_text = row_text.upper()
            label = classify(row_text) or "macro_ambiguous"
            
            # Use universe-aware planner if enabled
            if use_universe and Path(universe).exists():
                plans = plans_universe(label, row_text, row_text, cfg, Path(universe), wl)
            else:
                primary = map_ticker(row_text, wl)
                plans = plans_from_headline(label, row_text, primary, cfg, wl)
            
            if llm and plans:
                llmres = suggest_with_llm(row_text)
                if llmres.action_line:
                    plans[0].line = llmres.action_line
            
            typer.echo(f"[NEWS] {row_text}")
            for p in plans: 
                typer.echo(f" -> {p.line}")
            typer.echo("")
            
            time.sleep(poll_ms/1000)
    except KeyboardInterrupt:
        pass
