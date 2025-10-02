# orats_fetch.py
from __future__ import annotations
import os
from pathlib import Path
from io import StringIO
import pandas as pd
import requests
import typer

app = typer.Typer(add_completion=False)
BASE = "https://api.orats.io/datav2"

def _token() -> str:
    t = os.getenv("ORATS_TOKEN")
    if not t:
        raise RuntimeError("Set ORATS_TOKEN env var")
    return t

def _csv_get(path: str, params: dict) -> pd.DataFrame:
    p = dict(params)
    p["token"] = _token()
    r = requests.get(f"{BASE}/{path}", params=p, timeout=30)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

@app.command()
def summaries(ticker: str, out: str = typer.Option(None, help="Optional CSV/Parquet to write")):
    """
    Live one-minute summaries (implied vols, slopes, implied earnings move, etc.)
    """
    df = _csv_get("live/one-minute/summaries", {"ticker": ticker})
    if out:
        _write(df, out)
    else:
        typer.echo(df.head().to_string(index=False))

@app.command()
def chain(ticker: str, out: str = typer.Option(None, help="Optional CSV/Parquet to write")):
    """
    Live one-minute strikes chain (calls + puts fields aggregated by strike).
    """
    df = _csv_get("live/one-minute/strikes/chain", {"ticker": ticker})
    if out:
        _write(df, out)
    else:
        typer.echo(df.head().to_string(index=False))

@app.command()
def option(opra: str, out: str = typer.Option(None)):
    """
    Live one-minute by OPRA code (e.g., AAPL24062100160000).
    """
    df = _csv_get("live/one-minute/strikes/option", {"ticker": opra})
    if out:
        _write(df, out)
    else:
        typer.echo(df.head().to_string(index=False))

def _write(df: pd.DataFrame, out: str):
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() == ".parquet":
        df.to_parquet(p, index=False)
    else:
        df.to_csv(p, index=False)
    typer.echo(f"Wrote {p} ({len(df):,} rows).")

if __name__ == "__main__":
    app()

