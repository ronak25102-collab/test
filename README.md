# Beyond — Track A

Beyond investigates listed financial businesses from public evidence. The live
pipeline extracts source-bound facts, runs registered Decimal calculations,
generates hypotheses, searches supporting and opposing evidence, and independently
reviews every material statement before publishing the eight required fields.
It abstains when the evidence is inadequate.

## Local setup / WSL

Python 3.12, uv and Node.js 22 are required. From the repository root:

```bash
uv sync --frozen --extra dev
uv run alembic -c backend/alembic.ini upgrade head
uv run signal-research research --company SYNTHBANK --as-of 2026-10-08 --mode replay
uv run uvicorn signal_research.main:app --host 127.0.0.1 --port 8000
```

In a second terminal run `uv run python -m signal_research.worker.main`. In a third:

```bash
cd frontend
npm ci
npm run dev
```

The dashboard defaults to live mode. Select SYNTHBANK and replay for the free,
explicitly synthetic demonstration. Real companies require live/deep mode.
The API is at http://127.0.0.1:8000/docs and the dashboard at http://127.0.0.1:5173.
The API does not start an extra worker by default.

## Live configuration

Gemini and OpenAI are supported. For Gemini configure `LLM_PROVIDER=gemini`,
`GEMINI_API_KEY`, `GEMINI_MODEL_RESEARCH`, and `GEMINI_MODEL_EXTRACT`.
`GEMINI_THINKING_LEVEL=low` bounds reasoning effort. Both roles may use
`gemini-3.8-flash`; verify that your AI Studio project has sufficient quota.
The adapter uses stateless `generateContent` with a native structured schema
derived from Pydantic; the original Pydantic schema validates the returned values.
Reasoning tokens are included in the usage ledger. The provider
does not silently change models or repeat an uncertain request.

Copy `config/model-rates.gemini-free.example.json` to `config/model-rates.json`
for a Gemini free-tier project. Set `SEARCH_USD_PER_CREDIT=0` only while using
Tavily's free credit allocation, and `MAX_RUN_COST_USD=0` to reject configured
paid rates. Free providers still impose account quotas and capacity limits.
Neither the application nor its setup scripts enable billing.

Copy `.env.example` to `.env`. For local development set
`DATABASE_URL=sqlite:///./data/signal.db`. Configure `OPENAI_API_KEY`,
`TAVILY_API_KEY`, and account-accessible `OPENAI_MODEL_RESEARCH` and
`OPENAI_MODEL_EXTRACT` IDs. Copy `config/model-rates.example.json` to
`config/model-rates.json`, filling the actual input/output USD rates for **both**
configured models (one entry is enough if both roles use the same model).
Set `SEARCH_USD_PER_CREDIT` for your Tavily plan.

### Windows local services

After configuring `.env`, run from the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe scripts\doctor.py --live
.\scripts\local.ps1 start
.\scripts\local.ps1 status
.\scripts\local.ps1 restart
.\scripts\local.ps1 stop
```

The helper migrates SQLite and starts the API, worker and dashboard as hidden
background processes bound to localhost. Logs and PID records are under
`data/exports/local-runtime`. Restart after changing `.env`. It only stops
processes it started, preserves the database, and refuses to reuse occupied ports.
Install Tesseract for scanned-PDF OCR. The helper includes a portable installation
at `data/exports/local-runtime/tesseract` in the service PATH when present;
Poppler must also be on PATH. Alternatively set `PDFTOPPM_PATH` and
`TESSERACT_PATH` to absolute executable paths in `.env`; these work even when
the tools are absent from PATH. `doctor.py` reports both OCR dependencies.

`ALLOW_UNKNOWN_COST=true` explicitly permits testing with hard call/token/time
caps when prices are unavailable; in that mode the USD invoice cap cannot be
guaranteed. No model is selected silently and live mode never substitutes fixtures.

```bash
uv run python scripts/doctor.py --live
uv run signal-research universe refresh
uv run signal-research research --company HDFCBANK --as-of 2026-10-08 --mode live
uv run signal-research status RUN_ID
```

Company resolution can refresh the official NIFTY directory and NSE listed-equity
directory. Listing identity and NIFTY membership remain distinct. Unclear business
profiles are rejected rather than guessed. Deep mode investigates up to three
candidates; it retains the same configured spending/time caps.

## Docker / PostgreSQL

```bash
cp .env.example .env
docker compose build
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose up -d api worker web
```

The backend image includes Poppler and Tesseract for bounded, selective OCR.
PostgreSQL 16 supports admission locking, lease renewal and fenced writes.
SQLite is a single-worker development fallback. Keep `AUTO_START_WORKER=false`
when using the separate worker service.

## Verification and exports

```bash
make verify
uv run signal-research evaluate --suite tests/evaluation/cases.yaml --offline
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
```

Use `TEST_DATABASE_URL` with an isolated PostgreSQL test database to run repository
tests against PostgreSQL. The GitHub workflow runs SQLite, PostgreSQL, migrations,
offline evaluation, the frontend build and browser tests without provider secrets.
On Windows with installed Edge, `PLAYWRIGHT_CHANNEL=msedge` can replace Chromium.

The dashboard links claims to exact passages, original sources, formulas and
input facts. Print view includes the timeline and evidence URLs. The API and CLI
export JSON and CSV. Cancellation and resume preserve durable outputs, reservations,
the original deadline and limits. An uncertain paid request is never replayed
automatically; start a new run when its result cannot be recovered.

See [implementation status](docs/implementation-status.md),
[configured Windows setup](docs/LOCAL_SETUP.md),
[fix handoff](docs/FIX_HANDOFF.md), [validation](docs/evaluation-report.md) and
[the product specification](docs/TRACK_A_PRD_AND_IMPLEMENTATION.md).
