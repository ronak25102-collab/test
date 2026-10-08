# Signal Research — Track A

An auditable, profile-driven research application for the Track A banking,
NBFC and financial-services challenge. The implementation lives in this
directory; the supplied product specification remains in `../Prompt/`.

The first release is deliberately useful without provider credentials:

* `replay` mode runs a labelled synthetic evidence case through the same
  planning, calculations, challenge, verification and report pipeline.
* `live` mode requires configured providers and never substitutes replay data.
* Every displayed number is a verified fact or a registered calculation.
* A report can abstain when the independent evidence gate is not satisfied.

## Quick start without Docker

```bash
cd bits
uv sync --extra dev
uv run signal-research research --company SYNTHBANK --as-of 2026-10-08 --mode replay
uv run signal-research status RUN_ID
uv run uvicorn signal_research.main:app --reload
```

Open <http://127.0.0.1:8000/docs> for the API. The Vite dashboard is in
`frontend/` and can be started with `npm install && npm run dev`.

For browser tests, run `npx playwright install --with-deps chromium` once in
`frontend/`, then `npm run test:e2e`. If using `.env` locally, set
`DATABASE_URL=sqlite:///./data/signal.db`; the example's PostgreSQL hostname
is intended for Compose.

## Docker / PostgreSQL

```bash
cp .env.example .env
docker compose build
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose up -d api worker web
```

The host binds only to loopback. `DATABASE_URL` defaults to PostgreSQL in
Compose and can be set to `sqlite:///./data/signal.db` for a local no-Docker
run. SQLite is a development fallback; the worker lease and relational schema
are designed for PostgreSQL 16.

## Commands

```bash
make doctor              # local tools, config and database checks
make test                # deterministic unit tests
make test-integration    # repository/API tests when dependencies are present
make lint
make verify
make doctor-live         # explicitly opt-in provider checks
```

The CLI uses the same domain service as the API:

```bash
signal-research universe refresh
signal-research research --company HDFCBANK --as-of 2026-10-08
signal-research research --company SYNTHBANK --mode replay
signal-research status RUN_ID
signal-research cancel RUN_ID
signal-research resume RUN_ID
signal-research export RUN_ID --format json --out output/result.json
signal-research evaluate --suite tests/evaluation/cases.yaml --offline
```

See `docs/decisions.md`, `docs/implementation-status.md`,
`docs/source-policy.md`, `docs/evaluation-report.md` and
`docs/demo-runbook.md` for operational notes and measured offline checks.
