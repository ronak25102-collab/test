# Implementation status

## Completed in this checkout

* Phase 0: monorepo scaffold, environment contract, Compose, health API and
  Vite dashboard.
* Phase 1: typed domain contracts, relational persistence, migrations,
  provenance chain and report validation.
* Phase 2: Indian-number parsing, units, periods, comparability and Decimal
  calculation registry.
* Phase 3/4: profile routing, source policy, bounded fetcher, HTML/PDF passage
  extraction and synthetic evidence provider.
* Phase 5/6: observation-first hypotheses, adaptive action records,
  counterevidence, falsification and publication/abstention gates.
* Phase 8/9: API, dashboard, print view, exports, cancellation, checkpoints,
  idempotent run creation and worker lease fields.

## Verification

`uv run pytest -q`: 18 passed. `ruff`: passed. Frontend TypeScript/Vite build:
passed. Playwright browser shell test: 1 passed after installing Chromium and
its Linux dependencies. Fresh SQLite Alembic migration: passed. CLI replay,
JSON export and offline evaluation: passed. See `evaluation-report.md` for
run IDs and measured commands.

Live checks require credentials and are opt-in via `make doctor-live`; no live
provider result is represented by the offline suite.

## Known operational limits

The live LLM/search path requires account-accessible model IDs and provider
keys. OCR is guarded but not enabled in the base image. A PostgreSQL-backed
deployment should be used for concurrent workers; SQLite is for local tests.

The current live path retrieves and parses source leads, but publication
continues to abstain until schema-validated facts, trustworthy publication
dates and two relevant origins pass the gate. Full all-constituent live
evaluation, curated public extraction accuracy, advanced OCR/XBRL and
concurrent-worker recovery remain required finals validation gates.
