"""Import BEQS screens from CSV exports (workaround for API access limitations)"""
import pandas as pd
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)
CAT = Path("catalog")
CAT.mkdir(parents=True, exist_ok=True)

def normalize_ticker(ticker: str) -> str:
    """Normalize ticker to Bloomberg API format."""
    ticker = ticker.strip()
    
    # Already in correct format
    if ' Equity' in ticker or ' Index' in ticker or ' Comdty' in ticker:
        return ticker
    
    # Handle different Bloomberg CSV export formats
    # Examples: "AAPL", "AAPL US", "AAPL US Equity"
    if ' ' in ticker:
        # Has exchange code: "AAPL US" → "AAPL US Equity"
        return ticker + " Equity"
    else:
        # Just ticker: "AAPL" → "AAPL US Equity"
        return ticker + " US Equity"

@app.command()
def from_csv(common_csv: str = typer.Option(None, help="CSV export from US_COMMON_PRIMARY screen"),
             etf_csv: str = typer.Option(None, help="CSV export from US_ETF_PRIMARY screen"),
             adr_csv: str = typer.Option(None, help="CSV export from US_ADR_PRIMARY screen"),
             ticker_column: str = typer.Option("Security", help="Column name containing tickers"),
             out: str = typer.Option(str(CAT / "beqs_securities.parquet"))):
    """
    Import BEQS results from CSV exports.
    
    HOW TO EXPORT FROM BLOOMBERG TERMINAL:
    1. BEQS <GO>
    2. Open your screen (e.g., US_COMMON_PRIMARY)
    3. Actions → Export → Export All Results
    4. Save as CSV
    5. Repeat for each screen
    
    Then run:
      python import_beqs_csv.py from-csv --common-csv beqs_common.csv --etf-csv beqs_etf.csv --adr-csv beqs_adr.csv
    """
    all_secs = []
    
    def load_csv_file(filepath: str, label: str):
        """Load and normalize tickers from a CSV file."""
        if not filepath or not Path(filepath).exists():
            typer.echo(f"[SKIP] {label}: File not provided or doesn't exist")
            return []
        
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except:
            try:
                df = pd.read_csv(filepath, encoding='latin-1')
            except Exception as e:
                typer.echo(f"[ERROR] Could not read {filepath}: {e}")
                return []
        
        # Try multiple possible ticker column names
        ticker_col = None
        for col in [ticker_column, 'Security', 'Ticker', 'ticker', 'security', 'ID', 'Bloomberg ID', 'Name']:
            if col in df.columns:
                ticker_col = col
                break
        
        if not ticker_col:
            typer.echo(f"[WARN] Could not find ticker column in {filepath}")
            typer.echo(f"       Available columns: {list(df.columns)[:10]}")
            typer.echo(f"       Specify with --ticker-column parameter")
            return []
        
        tickers = df[ticker_col].dropna().astype(str).tolist()
        normalized = [normalize_ticker(t) for t in tickers if t and t.strip()]
        typer.echo(f"[OK] {label}: Loaded {len(normalized):,} from {filepath}")
        return normalized
    
    # Load each file
    all_secs.extend(load_csv_file(common_csv, "Common Stocks"))
    all_secs.extend(load_csv_file(etf_csv, "ETFs"))
    all_secs.extend(load_csv_file(adr_csv, "ADRs"))
    
    if not all_secs:
        typer.echo("\n[ERROR] No securities loaded. Check CSV files and column names.")
        raise typer.Exit(1)
    
    # Dedup and save
    unique_secs = list(dict.fromkeys(all_secs))
    df_out = pd.DataFrame({"bbg": unique_secs})
    df_out.to_parquet(out, index=False)
    
    typer.echo(f"\n{'='*70}")
    typer.echo(f"[SUCCESS] Wrote {out}")
    typer.echo(f"          {len(unique_secs):,} unique securities ready for enrichment")
    typer.echo(f"{'='*70}")
    typer.echo(f"\nNext steps:")
    typer.echo(f"  1. python us_universe_pipeline.py refdata-enrich")
    typer.echo(f"  2. python us_universe_pipeline.py stats-cmd")
    typer.echo(f"  3. python us_universe_pipeline.py etfs-cmd")
    typer.echo(f"\nOr run all at once:")
    typer.echo(f"  python us_universe_pipeline.py all-from-beqs")

@app.command()
def show_columns(csv_file: str):
    """Show column names in a CSV file to help identify the ticker column."""
    if not Path(csv_file).exists():
        typer.echo(f"File not found: {csv_file}")
        raise typer.Exit(1)
    
    try:
        df = pd.read_csv(csv_file, encoding='utf-8', nrows=5)
    except:
        df = pd.read_csv(csv_file, encoding='latin-1', nrows=5)
    
    typer.echo(f"\nColumns in {csv_file}:")
    for i, col in enumerate(df.columns):
        typer.echo(f"  {i+1}. {col}")
    
    typer.echo(f"\nFirst few rows:")
    typer.echo(df.head(3).to_string())
    
    typer.echo(f"\nUse --ticker-column '<column_name>' to specify which column has tickers")

if __name__ == "__main__":
    app()


