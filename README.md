# headline-reactor

Local-only Bloomberg *News Alerts* to trade-action suggester (rules-first; optional LLM assist).

## What it does

* **Captures** just the **top line** of the *News Alerts* window (no feed scraping).
* **OCR** locally (Tesseract).
* **Classifies** with deterministic **regex playbooks** (e.g., `ratings_up_spain`, `ma_rumor`).
* **Maps** to symbols/ETFs (e.g., `SPAIN → EWP`, `ELECTRONIC ARTS → EA`).
* **Emits a one-liner** you can paste anywhere, e.g.:

  ```
  EWP BUY $1500 IOC TTL=30m (NEWS: ratings_up_spain)
  EA BUY $1500 IOC TTL=10m (NEWS: ma_rumor)
  NO ACTION (macro_ambiguous)
  ```
* **Optional LLM assist** (`--llm`): given only the **text headline**, the model returns a structured suggestion (side, instrument, confidence, rationale). (Stays off by default to respect "local-only".)

## Install

1) **Install Tesseract** (Windows). Add `tesseract.exe` to PATH.
   - Download from: https://github.com/UB-Mannheim/tesseract/wiki
   
2) **Python 3.11+**:
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
```

## Config

* `newsreactor.yml` – playbooks, offsets, notional, TTL, whitelist.
* `data/name_map.csv` – extend NAME→TICKER.
* `.env` – environment variables (API keys, LLM settings). Copy from `.env.example` and customize.

## Usage

### V2 System (Universe-Wide, No Whitelist)

**Recommended:** Use V2 commands for full cross-asset coverage without whitelist gating.

**Single headline:**
```bash
headline-reactor suggest-v2 "AIR FP AIRBUS WINS ORDER FROM EMIRATES"
# Output: EADSY BUY $2000 IOC TTL=10m (US ADR)
#         EWQ BUY $2000 IOC TTL=10m (country ETF: FR)
```

**Live watch:**
```bash
headline-reactor watch-v2
# Watches Bloomberg Alert Catcher in universe-wide mode
```

**Supports:**
- Any symbology: `AAPL US`, `NVDA.O`, `005930 KS`, `2330 TT`, `AIR FP`, `NESN SW`
- Foreign stocks → ADR or ETF proxies automatically
- Futures for macro (CLX4, GCZ4, 6EZ4, 6JZ4)
- Crypto proxies (BITO, ETHE)

### V1 System (Whitelist-Based)

**Single headline (copy/paste):**

```bash
headline-reactor suggest "SPAIN UPGRADED TO A BY FITCH"
# EWP BUY $1500 IOC TTL=30m (NEWS: country_ratings_up)
```

**Live watch (local OCR):**

```bash
headline-reactor watch
```

**Enable LLM assist (off by default):**

Create a `.env` file in the project root (copy from `.env.example`):

```bash
OPENAI_API_KEY=sk-your-actual-key
LLM_ENABLED=1
LLM_MODEL=gpt-5-fast
```

Then use the `--llm` flag:

```bash
headline-reactor suggest --llm "ELECTRONIC ARTS NEAR ROUGHLY $50B DEAL"

# Or use the launcher script
.\scripts\start_watch.ps1
```

The `.env` file is automatically loaded when you run any `headline-reactor` command.

> Uses the **OpenAI Responses API** under the hood via the official Python SDK (`client.responses.create(...)`). See [OpenAI Python SDK](https://github.com/openai/openai-python) for details.

## Compliance

* Screenshots and OCR happen **locally**.
* The LLM receives only the **headline text** and only if `LLM_ENABLED=1` or `--llm` is passed.
* You are responsible for ensuring your Bloomberg contract carve-out permits local OCR and any cloud use of derived text.

## Example outputs

**Korea Semiconductor Supplier News:**
```
Input:  "000660 KS;005930 KS SAMSUNG, SK HYNIX SHARES JUMP ON OPENAI'S STARGATE SUPPLY DEAL"
Output: EWY BUY $1500 IOC TTL=10m (NEWS: supplier_pop_korea_semi)
        SMH BUY $1500 IOC TTL=10m (NEWS: supplier_pop_korea_semi)
```

**Big Tech Product Pivot:**
```
Input:  "AAPL;META APPLE SHELVES HEADSET REVAMP TO PRIORITIZE META-LIKE AI GLASSES"
Output: AAPL SELL $1500 IOC TTL=10m (NEWS: bigtech_pivot)
```

**Country Ratings:**
```
Input:  "SPAIN UPGRADED TO A BY FITCH"
Output: EWP BUY $1500 IOC TTL=30m (NEWS: country_ratings_up)
        PAIR EWP/FEZ LONG/SHORT $1000/$1000 IOC TTL=30m (NEWS: country_ratings_up)
```

**M&A Rumor:**
```
Input:  "EA ELECTRONIC ARTS NEAR DEAL WITH MICROSOFT"
Output: EA BUY $1500 IOC TTL=10m (NEWS: ma_rumor)
```

**Macro Events (No Action):**
```
Input:  "SUPREME COURT UPHOLDS ..."
Output: NO ACTION (macro_ambiguous)
```

## Architecture

### Deterministic Rules First
Regex patterns + playbooks give you reliable, auditable output in < 200 ms:

**Tradeable Events:**
- `supplier_pop_korea_semi`: Samsung/SK Hynix news → EWY + SMH (multi-output)
- `bigtech_pivot`: Apple/Meta product cancellations → AAPL/META SELL
- `country_ratings_up/down`: Sovereign ratings → Country ETF + Pair trade
- `ma_confirmed`: Confirmed M&A deals → BUY
- `ma_rumor`: M&A rumors/talks → BUY
- `macro_ambiguous`: Fed/OPEC/broad macro → NO ACTION

**Smart Ticker Extraction:**
- Parses tickers directly from Alert Catcher row (e.g., `000660 KS`, `AAPL`)
- Maps foreign exchange codes to US ETFs (KS→EWY, ES→EWP, JP→EWJ)
- Generates sympathy trades (Samsung news → both EWY and SMH)
- Outputs multiple ranked suggestions per headline

### LLM Optional Overlay
Easy overlay for edge cases; disabled by default to respect local-only operation. When enabled, the LLM receives only the text headline (no screenshots) and returns structured suggestions.

### Paste-Ready Lines
Zero coupling to any broker UI; you can paste into EMSX, IB TWS, or call your execution daemon directly.

## Project Structure

```
headline-reactor/
  README.md
  .gitignore
  pyproject.toml
  newsreactor.yml            # config (playbooks, offsets, notional, etc.)
  data/
    name_map.csv             # NAME→TICKER mapping seed (extend)
  src/
    headline_reactor/
      __init__.py
      cli.py                 # Typer CLI
      capture.py             # find window + crop first row
      ocr.py                 # Tesseract wrapper
      rules.py               # regex classifiers + mapping
      planner.py             # rules → action line
      llm.py                 # optional OpenAI Responses API
      util.py                # helpers
  scripts/
    start_watch.ps1          # one-click watcher (Windows)
```

## Extending the System

### Add New Rules

Edit `newsreactor.yml` to add playbook parameters:

```yaml
playbooks:
  your_new_rule:
    action: BUY
    equity_offset_px: 0.02
    ttl_sec: 1800
    notional_usd: 2000
```

Add the regex pattern to `src/headline_reactor/rules.py`:

```python
RULES = [
    ("your_new_rule", re.compile(r"\bYOUR\b.*\bPATTERN\b")),
    # ... existing rules
]
```

### Add Exchange Mappings

Map foreign exchange codes to US ETFs in `rules.py`:

```python
EXCH_TO_ETF = {
    "XX": "ETYF",  # Your exchange → Your ETF
    # ... existing mappings
}
```

### Customize Watch Parameters

```powershell
headline-reactor watch `
  --window-title "Alert Catcher" `
  --roi-top 115 `
  --roi-height 20 `
  --whitelist "EWY,SMH,AAPL,META,EA,EWP,FEZ" `
  --poll-ms 250
```

## Future Enhancements

- Add a `--pair` flag to auto-render `EWP/FEZ` pair for ratings headlines.
- Push the one-liner directly to your trading-stack intent queue.
- Add a **cool-down** window per symbol/playbook to avoid duplicate fires on clustered wires.
- Support additional windows/feeds beyond Bloomberg News Alerts.

## License

MIT (or your preferred license)

## Disclaimer

This tool is for informational purposes only. You are responsible for:
- Compliance with your Bloomberg Terminal agreement
- All trading decisions and risk management
- Proper testing before any live trading use

