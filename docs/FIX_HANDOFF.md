> Historical document. Current Windows setup and free configuration are in [DEMO.md](DEMO.md); measured live results and the current verdict are in [LIVE-RESULTS.md](LIVE-RESULTS.md) and [READINESS.md](READINESS.md). Older model choices, limits and test counts below are not current validation.

# Beyond fix handoff

## Run this branch in WSL

```bash
git fetch origin
git switch fix/live-research-and-evidence
uv sync --frozen --extra dev
uv run alembic -c backend/alembic.ini upgrade head
make verify
uv run signal-research evaluate --offline
cd frontend
npm ci
npx playwright install --with-deps chromium
npm run test:e2e
```

For the API + UI, follow README.md. Keep the worker in its own terminal/service.
For multi-worker use, migrate PostgreSQL first. Run PostgreSQL fixture tests with
`TEST_DATABASE_URL=postgresql+psycopg://... uv run pytest tests/integration -q`.
The fixture creates and drops a unique schema per test in that dedicated test DB.

## Live prerequisites

Supply provider keys, two accessible model IDs, rates for each configured model,
and SEARCH_USD_PER_CREDIT. `doctor.py --live` validates configuration and does not
spend on provider requests. After configuration, a `research --mode live` invocation
does make paid calls within the configured budgets. Historical cutoff means the
end of the selected day in Asia/Kolkata, not the document's balance-sheet date.

## How publication works

`research/live.py` implements retrieval → bound fact extraction → registered
calculations → hypotheses → investigation → challenge → composition → semantic
review. `research/verifier.py` then checks deterministic publication gates.
Every headline and significance bullet is a reviewed claim. Counterarguments link
reviewed evidence. Calculations retain original fact IDs, and those facts retain
passage/document/source references. Peer material is context, never a target fact.

`worker/calls.py` reserves before requesting a provider and atomically stores the
successful result with its usage ledger entry. On restart, request hashes reuse
results. A reservation without a result is uncertain and cannot be replayed.
`worker/budgets.py` keeps cumulative usage, limits and the original deadline.
`Store.save_report` commits evidence, report and completed status together.

## Deployment checks still requiring external state

1. Run a real company from each applicable profile with API credentials. Manually
   inspect the central metric/value/date/scope bindings and every material claim.
2. Run PostgreSQL CI and concurrent workers; do not deploy multiple SQLite workers.
3. Evaluate real scanned filings in the Docker image. OCR below numeric-confidence
   gates is withheld. Verify original PDF images before treating extraction scores
   as measured accuracy.
4. Test unknown companies with the official directories reachable; blocked sources
   must produce an explicit resolution error, never a fabricated identity.
5. Keep any unresolved causal alternative in the report and its strength rationale.

The long product specification is a design reference. Implementation status and
measured test results determine what this branch currently demonstrates.
