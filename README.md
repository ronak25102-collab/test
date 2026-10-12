# Beyond — Track A

Beyond investigates listed financial businesses from public evidence. The live
pipeline extracts source-bound facts, runs registered Decimal calculations,
generates hypotheses, searches supporting and opposing evidence, and independently
reviews every material statement before publishing the eight required fields.
It abstains when the evidence is inadequate.

## Current Windows demo setup

Start with [Windows transfer and demo instructions](docs/DEMO.md),
[measured live results](docs/LIVE-RESULTS.md), and [readiness](docs/READINESS.md).
The current source has unpushed fixes; transfer the local source archive rather
than assuming a remote clone contains them. No billing or paid services are enabled.

```powershell
.\scripts\setup.ps1 -InstallOCR
# Enter existing keys privately in .env, then:
.\.venv\Scripts\python.exe scripts/configure_free.py
.\.venv\Scripts\python.exe -m signal_research.cli universe refresh
.\scripts\local.ps1 start
```

The current `.env.example` uses free NVIDIA Nemotron Super for both roles and
Tavily advanced search within its included allowance. The eight-minute research
cap does not guarantee a successful discovery. SYNTHBANK remains synthetic.

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

NVIDIA, Gemini and OpenAI are supported. For NVIDIA configure `LLM_PROVIDER=nvidia`,
`NVIDIA_API_KEY`, `NVIDIA_MODEL_RESEARCH`, and `NVIDIA_MODEL_EXTRACT`. Both current roles
use `nvidia/nemotron-3-super-120b-a12b` on NVIDIA's hosted free prototype API. The adapter
requests JSON with a schema derived from Pydantic, generates Decimal values as
numbers to avoid unsupported regex syntax, and validates returned values against
the original model locally. Reasoning is disabled for structured extraction. Requests use the fixed
NVIDIA endpoint and are not retried or redirected implicitly.
Responses stream incrementally using NVIDIA's supported SSE transport, then are
validated only after the stream finishes. Partial JSON is never accepted as evidence.
The current `MODEL_REQUEST_TIMEOUT_SECONDS=90` allows up to 90 seconds per request; this bounds the whole request even if
the server keeps sending heartbeat chunks. A timeout remains an uncertain call
and is not resubmitted automatically. The error message identifies this limit.
Independent fact reviews have an exact verdict count and short explanations to
prevent runaway generation; duplicate or missing candidate indices are rejected.
The current free-only configuration targets `MAX_RUN_SECONDS=480` (eight minutes),
with a separate 90-second model timeout. A completed abstention is not a successful
discovery; see docs/LIVE-RESULTS.md and docs/READINESS.md. Longer research can be
configured explicitly but does not meet the provisional live-demo target.
Run `scripts/configure_free.py` to verify access and generate the private card
when using the [free NVIDIA Developer Program prototype API](https://docs.api.nvidia.com/nim/docs/run-anywhere).
The example card is illustrative; it does not establish your account entitlement.
Keep the rate card consistent with your account and `SEARCH_USD_PER_CREDIT`
consistent with your Tavily plan. Token, call, time and dollar limits still apply.

For Gemini configure `LLM_PROVIDER=gemini`,
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

Issuer index pages are followed to a bounded set of financial-report PDFs on
verified issuer domains. Explicit presentation cover dates can establish publication
timing; reporting-period labels and search-result dates cannot. Existing seeded
companies receive updated verified domains at startup for Axis, HDFC, ICICI, Kotak
and SBI, retaining their legacy domains and identity history. Domains are verified
per issuer; the `.bank.in` suffix alone never authorizes a source. Icon-only PDF
links use their filenames as leads, and formal document dates accept ordinal days
such as `18th July, 2026`. Signed financial results can also supply a city/date
dateline within a board or issuer signature block with an executive role.
Filenames, quarter labels, board-meeting references and balance dates never establish
publication timing. An undated document successfully fetched today can establish
public availability by today's cutoff through its timestamped receipt and content
hash; original publication date stays unknown. This cannot authorize historical
cutoffs before retrieval, and prevents a Strong label based on unknown dates. Bank discovery prioritizes shorter financial results before
large annual reports. Verified financial-results indexes provide direct leads even
when search returns no official-domain matches. Initial bank retrieval preserves
time for independent verification and stops when explicit comparable balance
columns are ready for review. Explicit comparative balance tables can bind deposits and
borrowings to their own dates and scope before mandatory independent source review.
`MODEL_REQUEST_TIMEOUT_SECONDS=90` allows structured generation more time than
document downloads (`SOURCE_REQUEST_TIMEOUT_SECONDS=25`), while the overall run
deadline still bounds every call. `PDF_PARSE_TIMEOUT_SECONDS=45` gives large annual
reports a separate parsing limit; reports over 80 pages use column-preserving text
extraction instead of exhaustive table detection, with glyph-aware extraction on
balance pages. ITFRupee, Rupee and RupeeForadian currency glyphs and explicit thousand-rupee units
are preserved and normalized. Extraction prioritizes comparative balance pages;
analysis receives cited issuer spans and bounded independent context rather than
the entire annual report. Initial extraction stops once multiple comparable
measures are verified so investigation and counterevidence retain a time allowance.
`GEMINI_MAX_ATTEMPTS=2` permits one delayed retry
for an explicit HTTP 503 response. Each attempt is durably recorded and reserves
its own token/cost allowance; unsuccessful reservations remain charged conservatively.
Set the value to `1` to disable retries. Timeouts, uncertain responses, authentication
errors and quota errors are not retried automatically; models are never switched
implicitly.

Copy `.env.example` to `.env` and enter your own `NVIDIA_API_KEY` and
`TAVILY_API_KEY`. The template uses NVIDIA, Tavily and local SQLite; other
settings use the defaults in `settings.py`. Share `.env.example` with friends;
keep your populated `.env` private.

Live runs now perform a secret-free configuration check before entering the queue.
The dashboard shows missing account configuration; the API returns HTTP 503 with
`LIVE_CONFIGURATION_INCOMPLETE`, and the CLI exits with an actionable message.
Inspect `http://127.0.0.1:8000/api/v1/health/configuration` for the same preflight.
Create the rate card with verified prices for your account; do not assume that
the NVIDIA free-rate example applies. Replay does not require provider credentials.

Research instructions and table parsing are shared by business type rather than
issuer. Company names and domains are reference identity data. New issuer domains
can be verified from dated exchange disclosures that identify the company and ISIN
and explicitly reference its website; search results alone do not authorize a domain.
Same-issuer investor-relations navigation is bounded. If identity or evidence cannot
be established, the run withholds a discovery rather than trusting a guessed source.

The offline suite includes the entire seeded 12-company roster with mocked search,
HTTP documents and model responses. It checks extraction, calculations and honest
abstention; it does not establish real-provider discovery quality. Before the finals,
run the real roster plus unseen companies and manually validate sources, novelty,
falsification, runtime and cost. For a ten-minute presentation, reserve presentation
time and select a measured research limit; the example 900-second limit is not a
demo readiness guarantee.

Create `config/model-rates.json` for your account. For the NVIDIA Developer
Program prototype API, copy `config/model-rates.nvidia-free.example.json` only
if its zero token rates apply to your account. Otherwise use
`config/model-rates.example.json` and enter the actual rates for your configured
models. Adjust `SEARCH_USD_PER_CREDIT` to your Tavily plan. Provider setup
instructions above cover switching to Gemini or OpenAI.

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
Install Tesseract for scanned-PDF OCR. The helper adds a portable installation
at `data/exports/local-runtime/tesseract` to the service PATH when present.
PDFium (a Python dependency) renders pages when Poppler is unavailable.
Alternatively set `PDFTOPPM_PATH` and
`TESSERACT_PATH` to absolute executable paths in `.env`; these work even when
the tools are absent from PATH. An optional `tesserocr` engine can replace the
system Tesseract executable: install the [Windows wheel recommended by tesserocr](https://github.com/sirfz/tesserocr#installation)
for your Python version and put [English trained data](https://github.com/tesseract-ocr/tessdata_fast/blob/main/eng.traineddata)
at `data/tessdata/eng.traineddata`. Rendering and OCR remain isolated subprocesses
with deadlines and a 95% numeric-confidence requirement. `doctor.py` reports OCR availability.

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

When a live investigation reaches its time, token, call or cost limit after work
has begun, it saves a partial report with independently verified facts and
reproducible calculations. Further provider work stops. Additional source
retrieval uses shorter PDF parse limits and leaves time for final verification.
A partial result does not publish an unsupported discovery. A verified partial
checkpoint can be saved after an interruption without extending its deadline.

Bank extraction prioritizes comparative issuer balance sheets and excludes
sponsored rural-bank and welfare-trust slides from issuer totals. Explicit
issuer SOLO/GROUP balance columns preserve standalone/consolidated scope; comparative
month-year headers with YoY labels are normalized to calendar month ends.
Supported comparative issuer tables and explicit dated balance tables bind raw
deposits and borrowings directly to their columns, then require independent source
review. Ambiguous scope, units and columns are withheld. Net advances are never relabelled as
gross advances. Model extraction keeps the original source passage and restricts
metric names and passage IDs. Stock balances have no duration start; flow metrics
require both dates. Registered metric period types are checked independently of
model review. Discovery generation is constrained to existing citation IDs and
still undergoes semantic and calculation verification.

See [implementation status](docs/implementation-status.md),
[configured Windows setup](docs/LOCAL_SETUP.md),
[fix handoff](docs/FIX_HANDOFF.md), [validation](docs/evaluation-report.md) and
[the product specification](docs/TRACK_A_PRD_AND_IMPLEMENTATION.md).
