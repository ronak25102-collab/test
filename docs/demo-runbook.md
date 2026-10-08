# Demo runbook

1. `cp .env.example .env` and start the API with `uvicorn
   signal_research.main:app --reload`.
2. Run `signal-research research --company SYNTHBANK --mode replay` and copy
   the returned run ID.
3. Open the dashboard, inspect the discovery, click a number into its
   calculation and passage, then open the counterargument and falsification.
4. Export JSON and CSV from the result page.
5. For a real company, configure the provider keys, use `mode=live`, and keep
   the Live banner. Never present replay as fresh research.
