# Configuration and operations reference

This is the detailed reference behind the [README](../README.md): provider setup, rate cards,
limits, failover, evidence retrieval rules and local operations. Restart the API and worker after
changing `.env`; new runs use the new values, while durable request plans of existing runs stay unchanged.

## Contents

- [Settings at a glance](#settings-at-a-glance)
- [Providers](#providers): [CodeCraft](#codecraft), [NVIDIA](#nvidia), [Gemini](#gemini)
- [Rate cards and cost caps](#rate-cards-and-cost-caps)
- [Response, token and time limits](#response-token-and-time-limits)
- [Credit-exhaustion failover](#credit-exhaustion-failover)
- [Hybrid routing](#hybrid-routing)
- [Preflight check and run queue](#preflight-check-and-run-queue)
- [Evidence retrieval and extraction rules](#evidence-retrieval-and-extraction-rules)
- [Issuer identity and domains](#issuer-identity-and-domains)
- [Windows local services and OCR](#windows-local-services-and-ocr)
- [Validation expectations](#validation-expectations)

## Settings at a glance

Defaults come from `backend/src/signal_research/settings.py`. The values in `.env.example` are the
extended profile for real research; they are ceilings, not target usage.

| Setting | Code default | `.env.example` |
| --- | ---: | ---: |
| `MAX_RUN_SECONDS` | 600 | 600 |
| `DEMO_TARGET_SECONDS` (maximum 600) | 600 | 600 |
| `MODEL_REQUEST_TIMEOUT_SECONDS` (maximum 900) | 90 | 900 |
| `SOURCE_REQUEST_TIMEOUT_SECONDS` | 25 | 45 |
| `PDF_PARSE_TIMEOUT_SECONDS` (maximum 300) | 90 | 180 |
| `MAX_MODEL_OUTPUT_TOKENS_PER_CALL` | 16384 | 65536 |
| `MAX_INPUT_TOKENS` per run | 150000 | 5000000 |
| `MAX_OUTPUT_TOKENS` per run | 20000 | 5000000 |
| `MAX_MODEL_CALLS` | 50 | 200 |
| `MAX_SEARCH_CALLS` | 30 | 100 |
| `MAX_FETCH_DOCUMENTS` | 30 | 100 |
| `MAX_OCR_PAGES` | 8 | 50 |
| `MAX_RUN_COST_USD` | 5.0 | 0 (with `FREE_SERVICES_ONLY=true`) |

Live mode caps its target at 600 seconds (ten minutes), including a reserved analysis window.
Deep mode uses the full `MAX_RUN_SECONDS` and is explicitly outside that budget. These are maximum
allowances, not promised usage or provider entitlements. Account credits, rate limits, context
windows and access errors still apply, and raising a local limit cannot bypass them.

## Providers

Beyond supports CodeCraft, NVIDIA, Gemini and OpenAI through `LLM_PROVIDER`. Every adapter sends
the original Pydantic schema's constraints and then validates the returned values locally; no
adapter silently changes models or repeats an uncertain request.

### CodeCraft

Set `LLM_PROVIDER=codecraft`, `CODECRAFT_API_KEY`, `CODECRAFT_MODEL_RESEARCH` and
`CODECRAFT_MODEL_EXTRACT`. Use the exact model IDs returned by your authenticated catalog.

- The adapter uses the fixed `https://www.codecraftapi.com/v1/chat/completions` endpoint and its
  documented JSON mode. The original schema and evidence gates validate the result locally.
- It does not follow redirects or retry uncertain requests.
- Input and completion token usage is recorded, including completed responses rejected by schema
  validation. Reported completion tokens already include reasoning tokens.
- CodeCraft raises output limits below 2048, so Beyond stops before requesting a response when its
  remaining output budget cannot cover that minimum.
- CodeCraft requires `FREE_SERVICES_ONLY=false` and a positive `MAX_RUN_COST_USD` (for example 100).

### NVIDIA

Set `LLM_PROVIDER=nvidia`, `NVIDIA_API_KEY`, `NVIDIA_MODEL_RESEARCH` and `NVIDIA_MODEL_EXTRACT`.
`.env.example` defaults to `nvidia/nemotron-3-super-120b-a12b`; the 14 October local validation used
`nvidia/nemotron-3.5-lightning-30b-a3b` for both roles.

- Requests use a JSON schema derived from Pydantic, with Decimal values generated as numbers to
  avoid unsupported regex syntax. Returned values are validated against the original model.
- Reasoning is disabled for structured extraction. The fixed NVIDIA endpoint is used, with no
  implicit redirect or retry.
- Responses stream incrementally over NVIDIA's SSE transport and are validated only after the
  stream finishes. Partial JSON is never accepted as evidence.
- `MODEL_REQUEST_TIMEOUT_SECONDS` bounds the whole request, even if the server keeps sending
  heartbeat chunks. A timeout is an uncertain call and is not resubmitted automatically; the error
  message identifies the limit.
- Independent fact reviews require an exact verdict count and short explanations, which prevents
  runaway generation. Duplicate or missing candidate indices are rejected.
- Run `scripts/configure_free.py` to verify access and generate the private rate card when using the
  [free NVIDIA Developer Program prototype API](https://docs.api.nvidia.com/nim/docs/run-anywhere).
  The example card is illustrative and does not establish your account entitlement.

### Gemini

Set `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL_RESEARCH` and `GEMINI_MODEL_EXTRACT`.
Both roles may use `gemini-3.8-flash`; verify that your AI Studio project has sufficient quota.

- `GEMINI_THINKING_LEVEL=low` bounds reasoning effort. Reasoning tokens are included in the usage ledger.
- The adapter uses stateless `generateContent` with a native structured schema derived from Pydantic.
- `GEMINI_MAX_ATTEMPTS=2` permits one delayed retry for an explicit HTTP 503 response. Each attempt is
  durably recorded and reserves its own token and cost allowance; unsuccessful reservations remain
  charged conservatively. Set it to `1` to disable retries.
- Timeouts, uncertain responses, authentication errors and quota errors are never retried automatically.
- For a free-tier project, copy `config/model-rates.gemini-free.example.json` to
  `config/model-rates.json`, set `SEARCH_USD_PER_CREDIT=0` only while using Tavily's free credit
  allocation, and set `MAX_RUN_COST_USD=0` to reject configured paid rates. Free providers still
  impose account quotas and capacity limits. Neither the application nor its setup scripts enable billing.

## Rate cards and cost caps

Create `config/model-rates.json` for your account. It is local and ignored by Git, so `.env` alone is
not enough when moving to another computer.

- NVIDIA Developer Program prototype API: copy `config/model-rates.nvidia-free.example.json` only if
  its zero token rates apply to your account.
- Otherwise copy `config/model-rates.example.json` and enter the actual rates for your models.
- CodeCraft Gemini Flash with the NVIDIA Lightning fallback: copy the credential-free snapshot
  `config/model-rates.codecraft.example.json`. It covers `gemini-3.7-flash` and
  `nvidia/nemotron-3.5-lightning-30b-a3b`, so keep the model IDs consistent with `.env`. It records
  the shared demo account's pricing snapshot, not universal provider prices; check rates if you use
  another account.

```powershell
Copy-Item .\config\model-rates.codecraft.example.json .\config\model-rates.json -Force
.\scripts\local.ps1 restart
```

On macOS, Linux or WSL: `cp config/model-rates.codecraft.example.json config/model-rates.json`, then
restart the API and worker.

If the UI says "The rate card provider does not match LLM_PROVIDER", the top-level `provider` in the
rate card differs from the provider selected in `.env`. Copy the matching complete rate card rather
than only renaming its provider: prices and primary/fallback model IDs must match too. The
configuration endpoint `http://127.0.0.1:8000/api/v1/health/configuration` checks this without
provider calls.

Keep `SEARCH_USD_PER_CREDIT` consistent with your Tavily plan. Do not assume the NVIDIA free-rate
example applies to your account. `ALLOW_UNKNOWN_COST=true` explicitly permits testing with hard call,
token and time caps when prices are unavailable; the USD invoice cap cannot be guaranteed in that mode.
No model is selected silently, and live mode never substitutes fixtures. Replay needs no provider credentials.

## Response, token and time limits

- `MAX_MODEL_OUTPUT_TOKENS_PER_CALL` controls every model response, including extraction and
  independent review. `MAX_OUTPUT_TOKENS` is the separate total allowance for a run. Requests still
  preserve the final verification reserve and respect cost, time and provider limits.
- Raising a maximum does not force the model to use all those tokens, but longer responses can
  consume more credits. No finite cap guarantees completion.
- When a model response is cut off at its output limit, Beyond discards it and re-reads that page as two
  narrower metric requests. Each part is a complete structured answer and passes the same validation and
  independent review. Other invalid responses are withheld and recorded as evidence gaps; the pipeline
  moves on to other sources without resubmitting the failed request.
- On 15 October 2026 a live JSON check accepted `max_tokens=65536` for the configured CodeCraft model
  (424 input and 331 output tokens reported). This confirms the parameter was accepted, not that a full
  65536-token response completes or that the provider has no upstream maximum. CodeCraft's catalog
  does not currently report an output cap for the model.
- `MODEL_REQUEST_TIMEOUT_SECONDS` allows structured generation more time than document downloads
  (`SOURCE_REQUEST_TIMEOUT_SECONDS`); the overall run deadline still bounds every call.
- When a live investigation reaches its time, token, call or cost limit after work has begun, it saves a
  partial report with independently verified facts and reproducible calculations, and further provider
  work stops. A partial result never publishes an unsupported discovery. A verified partial checkpoint
  can be saved after an interruption without extending its deadline.

## Credit-exhaustion failover

Set `CODECRAFT_SECONDARY_API_KEYS` to a JSON array of backup keys in your private `.env`, ordered by
preference. Set `CODECRAFT_NVIDIA_FALLBACK=true` to use the existing `NVIDIA_API_KEY` and both
`NVIDIA_MODEL_*` settings after all CodeCraft keys explicitly reject work with HTTP 402.

- The rate card must cover the NVIDIA models too. Backup CodeCraft keys keep the configured CodeCraft
  model; NVIDIA uses its own configured models.
- Keys from one account may share its allowance, so adding keys does not guarantee additional credits.
- HTTP 429 throttling, authentication errors, timeouts and invalid model output never trigger key rotation.
- An HTTP 402 rejection releases the rejected request's token and cost reservation but keeps its call count.
- All routes share the original run budget and deadline. Exhausted keys are remembered within a run,
  while each pending request stays pinned to its original route, so a restart cannot duplicate uncertain work.
- New runs recheck the primary key; start a new run after changing the credential order.
- Switching is visible in run events, and the successful providers and models are recorded in the report
  metadata and the call ledger.
- If every provider fails, the application stops and preserves verified evidence when available.
- Tavily search quota is separate and is not increased by LLM fallback credentials.
- `CODECRAFT_KEY_ROUTING=balanced` caps one in-flight request per key and never rotates on 429;
  `sequential` uses keys in order.

## Hybrid routing

For NVIDIA extraction and planning with a CodeCraft review, set `NVIDIA_PLANNING=true`, configure both
NVIDIA model roles, and keep `LLM_PROVIDER=codecraft` with the desired review model. Extraction and
hypothesis planning use NVIDIA; composition, challenge and final verification use the configured provider
first. With `CODECRAFT_NVIDIA_FALLBACK=true`, a definitive CodeCraft credit rejection may switch any
remaining stage, including final review, to the configured NVIDIA model; the event and the actual model
are recorded. All participating models must appear in the private rate card, and provider receipts
record the actual models.

## Preflight check and run queue

- Live runs perform a secret-free configuration check before entering the queue. The dashboard shows
  missing account configuration, the API returns HTTP 503 with `LIVE_CONFIGURATION_INCOMPLETE`, and the
  CLI exits with an actionable message. `GET /api/v1/health/configuration` exposes the same preflight.
- The workspace shows the number of waiting runs and a **Clear queue** button, refreshed every five
  seconds. Clearing cancels all runs still waiting when the request is applied, leaves active
  investigations and completed reports untouched, and retains saved work for resume.
- The API exposes `GET /api/v1/runs/queue` and `POST /api/v1/runs/queue/clear`. The latter returns
  `cancelled_count` and the affected `run_ids` and records a cancellation event for each run. Repeating
  it against an empty queue has no effect.
- Cancellation and resume preserve durable outputs, reservations, the original deadline and limits.
  An uncertain paid request is never replayed automatically; start a new run when its result cannot
  be recovered. A completed verification checkpoint can be resumed after a save failure without
  resending provider requests.

## Evidence retrieval and extraction rules

**Discovery and sources**

- Issuer index pages are followed to a bounded set of financial-report PDFs on verified issuer domains.
  Verified financial-results indexes provide direct leads even when search returns no official-domain
  matches. Icon-only PDF links use their filenames as leads.
- When issuer pages are inaccessible, bounded, company-specific exchange searches seek NSE integrated
  filings before weaker PDF leads. These use Tavily advanced search and reserve its two-credit cost.
- Exchange table parsing preserves each column's explicit interval, scope, INR scale and original labels,
  along with filing notes for counterevidence review. Exact issuer-name and symbol cells establish
  ownership on a trusted exchange host, and an exact issuer signature also identifies an exchange PDF.
  Literal table candidates still pass source validation and independent model review. Historical
  collection seeks earlier exchange filings when those structured tables are available.
- Bank discovery prioritizes shorter financial results before large annual reports. Initial retrieval
  preserves time for independent verification and stops when explicit comparable balance columns are ready.
- Repeated identical PDF spans are deduplicated during parsing and evidence saving; conflicting content
  with a reused passage ID rolls publication back.
- The UI separates documents available by the cutoff, official issuer filings and documents actually
  supporting verified facts. A retrieved page is not a verified finding.

**Publication timing**

- Explicit presentation cover dates, formal document dates (including ordinal days such as
  `18th July, 2026`) and signed financial-results datelines within an executive signature block can
  establish publication timing.
- Filenames, quarter labels, board-meeting references, reporting-period labels, balance dates and
  search-result dates never do.
- An undated document successfully fetched today can establish public availability by today's cutoff
  through its timestamped receipt and content hash; its original publication date stays unknown. This
  cannot authorize historical cutoffs before retrieval, and it prevents a Strong label based on unknown dates.

**Parsing and extraction**

- `PDF_PARSE_TIMEOUT_SECONDS` gives large annual reports a separate parsing limit. Reports over 80 pages
  use column-preserving text extraction instead of exhaustive table detection, with glyph-aware
  extraction on balance pages. `ITFRupee`, `Rupee` and `RupeeForadian` currency glyphs and explicit
  thousand-rupee units are preserved and normalized.
- Extraction prioritizes comparative balance pages, and analysis receives cited issuer spans and bounded
  independent context rather than the entire annual report. Initial extraction stops once multiple
  comparable measures are verified, so investigation and counterevidence keep a time allowance.
- Bank extraction prioritizes comparative issuer balance sheets and excludes sponsored rural-bank and
  welfare-trust slides from issuer totals. Explicit issuer SOLO/GROUP balance columns preserve
  standalone and consolidated scope, and comparative month-year headers with YoY labels are normalized
  to calendar month ends.
- Supported comparative issuer tables and explicit dated balance tables bind raw deposits and borrowings
  directly to their columns, then require independent source review. Ambiguous scope, units and columns
  are withheld. Net advances are never relabelled as gross advances.
- Model extraction keeps the original source passage and restricts metric names and passage IDs. Stock
  balances have no duration start; flow metrics require both dates. Registered metric period types are
  checked independently of model review. Discovery generation is constrained to existing citation IDs and
  still undergoes semantic and calculation verification.
- Research instructions and table parsing are shared by business type rather than by issuer. Company
  names and domains are reference identity data only.

## Issuer identity and domains

- Domains are verified per issuer; the `.bank.in` suffix alone never authorizes a source. Seeded
  companies receive updated verified domains at startup for Axis, HDFC, ICICI, Kotak and SBI, retaining
  their legacy domains and identity history.
- Issuer website references are checked against their own company context. Startup quarantines legacy
  domains without current ownership proof and retains a private backup. See the
  [issuer website audit](DOMAIN-REFERENCE-AUDIT.md) for local, hash-verified reference recovery.
- New issuer domains can be verified from dated exchange disclosures that identify the company and ISIN
  and explicitly reference its website. Search results alone never authorize a domain.
- Same-issuer investor-relations navigation is bounded. If identity or evidence cannot be established,
  the run withholds a discovery rather than trusting a guessed source.
- Company resolution can refresh the official NIFTY directory and the NSE listed-equity directory.
  Listing identity and NIFTY membership remain distinct, and unclear business profiles are rejected
  rather than guessed.

## Windows local services and OCR

After configuring `.env`, run from the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe scripts\doctor.py --live
.\scripts\local.ps1 start
.\scripts\local.ps1 status
.\scripts\local.ps1 restart
.\scripts\local.ps1 stop
```

The helper migrates SQLite and starts the API, worker and dashboard as hidden background processes
bound to localhost. Logs and PID records are under `data/exports/local-runtime`. It only stops
processes it started, preserves the database, and refuses to reuse occupied ports. Restart after
changing `.env`.

**OCR for scanned PDFs**

- Install Tesseract. The helper adds a portable installation at `data/exports/local-runtime/tesseract`
  to the service `PATH` when present. PDFium (a Python dependency) renders pages when Poppler is unavailable.
- Alternatively set `PDFTOPPM_PATH` and `TESSERACT_PATH` to absolute executable paths in `.env`; these
  work even when the tools are absent from `PATH`.
- An optional `tesserocr` engine can replace the system Tesseract executable: install the
  [Windows wheel recommended by tesserocr](https://github.com/sirfz/tesserocr#installation) for your
  Python version and place the [English trained data](https://github.com/tesseract-ocr/tessdata_fast/blob/main/eng.traineddata)
  at `data/tessdata/eng.traineddata`.
- Rendering and OCR remain isolated subprocesses with deadlines and a 95% numeric-confidence
  requirement. `doctor.py` reports OCR availability.

## Validation expectations

The offline suite includes the entire seeded 12-company roster with mocked search, HTTP documents and
model responses. It checks extraction, calculations and honest abstention; it does not establish
real-provider discovery quality. Before relying on results, run the real roster plus unseen companies and
manually validate sources, novelty, falsification, runtime and cost. Live runs are capped at ten minutes,
so reserve presentation time and choose a measured research limit.
