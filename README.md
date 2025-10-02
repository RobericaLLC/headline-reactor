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

**Single headline (copy/paste):**

```bash
headline-reactor suggest "SPAIN UPGRADED TO A BY FITCH"
# EWP BUY $1500 IOC TTL=30m (NEWS: ratings_up_spain)
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

* `SPAIN UPGRADED TO A BY FITCH` → `EWP BUY $1500 IOC TTL=30m (NEWS: ratings_up_spain)`
* `SUPREME COURT ...` → `NO ACTION (macro_ambiguous)`
* `ELECTRONIC ARTS NEAR ROUGHLY $50B DEAL` → `EA BUY $1500 IOC TTL=10m (NEWS: ma_rumor)`

## Architecture

### Deterministic Rules First
Regex patterns + playbooks give you reliable, auditable output in < 200 ms:
- `ratings_up_spain`: Spain ratings upgrades → EWP BUY
- `ratings_down_spain`: Spain ratings downgrades → EWP SELL
- `ma_confirmed`: Confirmed M&A deals → BUY
- `ma_rumor`: M&A rumors/talks → BUY
- `macro_ambiguous`: Fed/OPEC/broad macro → NO ACTION

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

## Extending Playbooks

Edit `newsreactor.yml` to add new rules:

```yaml
playbooks:
  your_new_rule:
    symbol: XYZ
    action: BUY
    equity_offset_px: 0.02
    ttl_sec: 1800
    notional_usd: 2000
```

Then add the regex pattern to `src/headline_reactor/rules.py`:

```python
RULES = [
    ("your_new_rule", re.compile(r"\bYOUR\b.*\bPATTERN\b")),
    # ... existing rules
]
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

