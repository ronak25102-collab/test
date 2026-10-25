# Beyond

**An evidence-first research workbench for listed financial businesses.**

The backend now defaults to **stored evidence playback** (`PIPELINE_MODE=precomputed`).
It shows the existing progress stages for `REPLAY_DURATION_SECONDS=147`, then saves a
reviewed published report under the new run ID. Playback makes no search, model or
source-fetch requests and requires no provider keys or rate card. Existing endpoints,
report schema, exports, synthetic SYNTHBANK replay and the frontend are unchanged.

All **12** official Track A constituents are available: **HDFC Bank, Jio Financial
Services, ICICI Bank, State Bank of India, Bajaj Finance, Kotak Mahindra Bank,
Axis Bank, BSE, Bajaj Finserv, HDFC Life, SBI Life and Shriram Finance**. Every fixture
passes source binding, registered Decimal arithmetic, final verification and the
publication policy. See the
[verified roster](docs/PRECOMPUTED_COMPANIES.md), [parity contract](docs/PARITY_CHECKLIST.md)
and [measured coverage](docs/PRECOMPUTED_STATUS.md) for exact shortfalls.

The user-requested `source_verified_discovery_v2` policy permits reviewed arithmetic
findings with at least four bound facts, a registered calculation, significance,
timeline, counterargument and falsification tests. Missing document/history/peer
breadth is disclosed instead of blocking publication. Six fixtures also meet the
original larger coverage targets; those diagnostic counts remain visible. Full
five-year/eight-quarter coverage and every legacy URL are not claimed.

Publication and evidence strength are separate. Under the revised descriptive
policy, source-verified arithmetic can earn **Moderate** without two exact-period
peers. **Strong** still requires independent corroboration and the existing stronger
criteria; a hosted copy of an issuer filing is not an independent origin. Live-mode
grading and numerical/source verification gates retain their original requirements.

To restore the original provider-backed execution, set `PIPELINE_MODE=live` in
`.env` and restart the API and worker. Its original credential, budget and rate-card
checks still apply. The existing Live/Deep request options are preserved; the backend
pipeline setting selects their execution path. An accepted run retains its execution
policy and playback duration across restarts.

To refresh a stored company, edit
`backend/src/signal_research/precomputed/inputs/<SYMBOL>.yaml` using actual opened
source documents and a recorded source-based editorial review, then run:

```powershell
uv run python scripts/build_precomputed.py
# Optional: enforce the original broader coverage targets for a selected issuer.
uv run python scripts/build_precomputed.py HDFCBANK --strict-parity
```

The builder is offline. It checks original source-byte hashes, numerical/date/scope
bindings, formula results, peer reproduction, structural breaks, history, cadence,
strength and final verification. Raw downloaded PDFs/HTML stay local; use
`uv run python scripts/gather_precomputed_sources.py --restore-fixtures` to restore
missing source bytes before rebuilding. Changed remote bytes fail rather than silently
replacing a cited document. To add a company, supply the same source inputs and a
reviewed report without changing the report schema; an incomplete research-only YAML
cannot be published. `scripts/research_remaining_precomputed.py` records the reviewed
raw transcriptions used for the six added issuers. Rebuilding all inputs now publishes
all 12; `--strict-parity` still fails on any unmet original coverage target.

Beyond investigates banks, NBFCs, insurers, exchanges and diversified financial groups from public
evidence. It reads original filings, binds every figure to its source, runs registered Decimal
calculations, tests the strongest opposing explanation, and publishes a finding only when it survives
independent review. When the evidence is inadequate it says so and abstains.

> A saved report with verified figures but no published discovery is **not** a successful discovery.
> The dashboard labels it **Not established** and never presents an unverified candidate as a finding.

## Contents

- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Using the workbench](#using-the-workbench)
- [Configuration](#configuration)
- [Validation and testing](#validation-and-testing)
- [Exports and handoff](#exports-and-handoff)
- [Documentation](#documentation)

## How it works

The live pipeline runs the same stages for every issuer:

| Stage | What happens |
| --- | --- |
| **Resolve** | Identifies the company from official exchange directories and selects one of seven business profiles (bank, NBFC, life insurer, general insurer, exchange, asset manager, diversified). Unclear profiles are rejected, never guessed. |
| **Discover and fetch** | Searches issuer disclosures, exchange filings, regulator and peer context; fetches the originals. Search snippets are only leads. |
| **Extract and verify** | Binds each figure to its row, column, date, unit and scope, then requires independent source review. Ambiguous values are withheld. |
| **Calculate** | Runs registered Decimal formulas on verified inputs; every output keeps its input facts. |
| **Hypothesize and challenge** | Proposes candidate relationships, searches supporting and opposing evidence, and tests the strongest alternative. |
| **Review and publish** | Independently reviews every material statement and publishes the eight required fields, or abstains. |

**Evidence rules that shape every result**

- Standalone, consolidated and segment evidence are kept separate. Net advances are never relabelled as gross advances.
- Peer comparison requires matching metric, definition, scope, unit and period ends, and a median needs at
  least two verified peers. An unavailable peer comparison caps evidence strength at **Weak**; unmatched
  peer passages stay as context and never raise strength.
- Structural jumps (for example mergers) are flagged and excluded from lead growth comparisons until reconciled.
- Funding analysis uses deposits as a share of deposits plus borrowings, which explicitly excludes other liabilities.
- Each report carries an eight-part requirements checklist, verified temporal analysis, the opposing searches
  actually run, and the evidence-strength rule trace. A qualified observation can have limited temporal
  coverage; the checklist never declares its onset established.
- Withheld hypotheses and proposed tests stay labelled unverified.

**Historical research.** Collection seeks the current annual report and earlier windows across five years,
plus profile-specific operating metrics and original regulator and peer context. Verified facts from earlier
completed live runs may be reused when they are at least one year old, belong to the same issuer, satisfy the
cutoff and still match their original document hashes. Conclusions are never reused: new searches,
hypotheses, opposing searches and final review always run, and reports disclose reused and fresh fact counts.
Turn on **Cold start** in the workspace to disable reuse for a run.

## Quick start

For one-container hosting of the website, API and worker, follow the
[free Render deployment guide](docs/RENDER_DEPLOYMENT.md).

**Requirements:** Python 3.12, [uv](https://docs.astral.sh/uv/), and Node.js 22.

```bash
# 1. Backend
uv sync --frozen --extra dev
cp .env.example .env              # then add your own keys (see Configuration)
uv run alembic -c backend/alembic.ini upgrade head
uv run signal-research research --company SYNTHBANK --as-of 2026-10-08 --mode replay
uv run uvicorn signal_research.main:app --host 127.0.0.1 --port 8000

# 2. Worker (second terminal)
uv run python -m signal_research.worker.main

# 3. Dashboard (third terminal)
cd frontend && npm ci && npm run dev
```

| Service | Address |
| --- | --- |
| Dashboard | http://127.0.0.1:5173 |
| API and docs | http://127.0.0.1:8000/docs |
| Configuration preflight | http://127.0.0.1:8000/api/v1/health/configuration |

The API does not start a worker by default, so keep the worker running in its own terminal.
Select **SYNTHBANK** in replay mode for the free, explicitly synthetic demonstration. Real companies need
Live or Deep mode and provider keys.

<details>
<summary><strong>Windows (PowerShell helper)</strong></summary>

```powershell
.\scripts\setup.ps1 -InstallOCR
# Enter existing keys privately in .env, then:
.\.venv\Scripts\python.exe scripts/configure_free.py
.\.venv\Scripts\python.exe -m signal_research.cli universe refresh
.\scripts\local.ps1 start        # also: status, restart, stop
```

The helper migrates SQLite and starts the API, worker and dashboard as hidden localhost processes. See
[Windows transfer and demo instructions](docs/DEMO.md) and the
[configuration reference](docs/CONFIGURATION.md#windows-local-services-and-ocr).

</details>

<details>
<summary><strong>Docker and PostgreSQL</strong></summary>

```bash
cp .env.example .env
docker compose build
docker compose up -d db
docker compose run --rm api alembic upgrade head
docker compose up -d api worker web
```

The backend image includes Poppler and Tesseract for bounded, selective OCR. PostgreSQL 16 supports
admission locking, lease renewal and fenced writes. SQLite is a single-worker development fallback; keep
`AUTO_START_WORKER=false` when using the separate worker service.

</details>

## Using the workbench

1. Open the dashboard and choose **Launch workspace**.
2. Search a company by name or NSE symbol, or use **Resolve from exchange directory**.
3. Pick a cutoff date and a mode, then start the investigation and follow its live progress.

| Mode | Use it for | Time budget |
| --- | --- | --- |
| **Replay** | Free synthetic demonstration (SYNTHBANK only) | No provider calls |
| **Live** | Real public sources | Up to 600 seconds (ten minutes), including a reserved analysis window |
| **Deep** | Extended research, up to three candidates | Longer configured deadline, outside the ten-minute Live budget |

The report links every claim to its exact passage, original source, formula and input facts. From the
command line:

```bash
uv run python scripts/doctor.py --live
uv run signal-research universe refresh
uv run signal-research research --company HDFCBANK --as-of 2026-10-08 --mode live
uv run signal-research status RUN_ID
```

The workspace also shows the number of waiting runs with a **Clear queue** button, which cancels runs that
have not started and leaves active investigations and saved reports untouched.

## Configuration

Copy `.env.example` to `.env` and enter your own keys. Keep the populated `.env` private and share only
the template.

| You need | Setting |
| --- | --- |
| A model provider | `LLM_PROVIDER` (`nvidia`, `codecraft`, `gemini` or `openai`), its API key and both model roles |
| Web search | `TAVILY_API_KEY` |
| A rate card | `config/model-rates.json` (local and ignored by Git; copy the matching example from `config/`) |
| Live research limits | `MAX_RUN_SECONDS`, `DEMO_TARGET_SECONDS` (maximum 600), per-run token, call and cost caps |

A live run first passes a secret-free configuration check. If anything is missing, the dashboard says what,
the API returns HTTP 503 `LIVE_CONFIGURATION_INCOMPLETE`, and the CLI exits with an actionable message.
Restart the API and worker after changing `.env`.

Provider setup, rate cards, token and time limits, credit-exhaustion failover, hybrid routing, evidence
retrieval rules and OCR are in the **[configuration reference](docs/CONFIGURATION.md)**.

## Validation and testing

```bash
make verify                                                        # lint, tests, security tests, frontend build
uv run signal-research evaluate --suite tests/evaluation/cases.yaml --offline
cd frontend && npx playwright install --with-deps chromium && npm run test:e2e
```

Set `TEST_DATABASE_URL` to an isolated PostgreSQL database to run repository tests against PostgreSQL. On
Windows with Edge installed, `PLAYWRIGHT_CHANNEL=msedge` can replace Chromium. The GitHub workflow runs
SQLite, PostgreSQL, migrations, offline evaluation, the frontend build and browser tests without provider secrets.

The offline suite covers the whole seeded 12-company roster with mocked search, documents and model
responses. It checks extraction, calculations and honest abstention; it does **not** establish
real-provider discovery quality.

**Real-provider checks (these consume API credits)**

```bash
# One company, isolated database; saves the report and token usage under data/exports/live-validation/
uv run python scripts/validate_discovery.py HDFCBANK --cold-start --seconds 300

# The twelve NIFTY financial constituents, each from an empty database
uv run python scripts/regression.py --seconds 300 --workers 3
```

`validate_discovery.py` uses your private provider configuration, never touches the website queue or your
`.env` limits, and accepts `--reuse-database PATH` to measure the historical cache. `regression.py` writes
`reports/regression.md` with failures and actual runtimes; `--artifact-root` and `--output` keep experiments
separate, and `--summarize PATH` rebuilds the report from recorded artifacts without API calls. Finishing
inside the time limit does not count as success if the run failed early or published no discovery.

## Exports and handoff

- **Export report** downloads one offline HTML file with inline styles and scripts, embedded source
  passages, public source links and claim-to-input navigation, including peer and checked reconciliation
  passages. **Print / Save as PDF** produces the print view without a running server. Source quotes stay
  verbatim; generated prose uses grouped, rounded values; synthetic replay is clearly marked.
- The API and CLI also export JSON and CSV.
- For handoff, follow the [submission runbook](docs/SUBMISSION-RUNBOOK.md). `.env.example` and
  `.env.submission.example` contain no credentials, and
  `uv run python scripts/package_submission.py` builds a source ZIP that excludes private configuration,
  runtime data and downloaded filings.

## Documentation

| Topic | Document |
| --- | --- |
| Configuration and operations reference | [docs/CONFIGURATION.md](docs/CONFIGURATION.md) |
| Product specification | [docs/TRACK_A_PRD_AND_IMPLEMENTATION.md](docs/TRACK_A_PRD_AND_IMPLEMENTATION.md) |
| Acceptance audit and unmet criteria | [docs/TRACK-A-ACCEPTANCE-2026-10-16.md](docs/TRACK-A-ACCEPTANCE-2026-10-16.md) |
| Implementation status | [docs/implementation-status.md](docs/implementation-status.md) |
| Windows demo and local setup | [docs/DEMO.md](docs/DEMO.md), [docs/LOCAL_SETUP.md](docs/LOCAL_SETUP.md) |
| Live results and readiness | [docs/LIVE-RESULTS-2026-10-14.md](docs/LIVE-RESULTS-2026-10-14.md), [docs/READINESS.md](docs/READINESS.md) |
| Validation | [docs/evaluation-report.md](docs/evaluation-report.md), [reports/regression-final.md](reports/regression-final.md) |
| Segment research | [docs/SEGMENT-RESEARCH.md](docs/SEGMENT-RESEARCH.md) |
| Issuer website audit | [docs/DOMAIN-REFERENCE-AUDIT.md](docs/DOMAIN-REFERENCE-AUDIT.md) |
| Frontend design | [docs/FRONTEND-DESIGN.md](docs/FRONTEND-DESIGN.md) |
| Fix handoff | [docs/FIX_HANDOFF.md](docs/FIX_HANDOFF.md) |
| Earlier provider batch (comparison) | [reports/regression-opus-only.md](reports/regression-opus-only.md) |

Credentials and local research artifacts stay private; no billing or paid services are enabled by the
setup scripts. SYNTHBANK remains synthetic and never represents a real company.
