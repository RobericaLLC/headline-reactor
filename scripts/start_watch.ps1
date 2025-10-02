# Launch watcher (local-only by default)
$env:LLM_ENABLED = "0"     # set to "1" to allow cloud LLM
$env:LLM_MODEL   = "gpt-5-fast"  # or your 'gpt5-high-fast'
headline-reactor watch --llm:$false

