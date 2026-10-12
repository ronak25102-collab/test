> Historical document. Current Windows setup and free configuration are in [DEMO.md](DEMO.md); measured live results and the current verdict are in [LIVE-RESULTS.md](LIVE-RESULTS.md) and [READINESS.md](READINESS.md). Older model choices, limits and test counts below are not current validation.

# Beyond local setup — 9 October 2026

The Windows checkout is configured with SQLite, a separate API and worker, and the
Vite dashboard. Both provider credentials are stored only in the ignored `.env`.
No secrets are included in this document or the Git-tracked source files.

## Active providers

- `LLM_PROVIDER=gemini`.
- Both model roles use `gemini-3.5-flash`, which passed an authenticated structured
  extraction check. Gemini 3.8 and 3.7 returned HTTP 503 high-demand responses during
  setup. The chosen model is explicit; the application has no hidden model fallback.
- Tavily authentication passed. The account reported the Researcher plan with
  1,000 monthly credits before validation requests. Issuer-domain searches use the
  general index to retrieve filings; independent context uses the finance index.
- The local rate card contains zero Gemini rates and `SEARCH_USD_PER_CREDIT=0`.
  These values apply to free allocations only. Google/Tavily account billing and
  quotas remain controlled by those services; the setup does not enable billing.

## Limits and dependencies

Each new run is capped at 12 searches, 12 document fetches, 30 model calls,
150,000 reserved input tokens, 30,000 output tokens including thinking, eight OCR
pages, and 900 seconds. One worker processes one run at a time. The configured
per-request output allowance is 8,192 tokens, bounded by the remaining run allowance.
The original 3,000-token request limit truncated a real financial extraction and
was increased without permitting partial responses or weakening validation. The
USD-estimate cap is zero; update the rate card before intentionally using a paid tier.

Tesseract 5.4 is installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`.
The bundled Poppler executable and Tesseract executable are configured explicitly
in `.env`, so OCR works without depending on an interactive terminal's PATH.
A synthetic PDF OCR check recovered its numeric value successfully. This is a
dependency check, not a measured extraction-accuracy benchmark on real filings.

## Start, restart, inspect, and stop

Run these commands from the repository root in PowerShell:

```powershell
.venv\Scripts\python.exe scripts\doctor.py --live
.\scripts\local.ps1 start
.\scripts\local.ps1 status
.\scripts\local.ps1 restart
.\scripts\local.ps1 stop
```

Use `restart` when the services are already running or after changing `.env`.
The helper tracks process creation timestamps, stops only its own process trees,
migrates the database, and starts hidden services on localhost. Logs and the service
manifest are in `data/exports/local-runtime`. The database is preserved across restarts.

- Dashboard: <http://127.0.0.1:5173/>
- API documentation: <http://127.0.0.1:8000/docs>
- Readiness: <http://127.0.0.1:8000/api/v1/health/ready>

Select a real company and Live mode for public research. SYNTHBANK with Replay mode
remains the deterministic synthetic demonstration. Live findings require comparable
verified issuer facts, source-owned cutoff dates, relevant independent evidence,
registered calculations, and successful claim review. Missing evidence produces an
explicit abstention rather than an invented discovery.

Changing the model requires updating both Gemini model roles in `.env` and the
matching rate-card entry in `config/model-rates.json`, then restarting services.
Model availability in the list endpoint does not guarantee generation capacity.

## Final setup validation

The complete backend suite passed 81 tests. The final authenticated HDFC Bank run
`93a42542-6880-48fc-becc-76a7c93c4ec9` completed using Tavily and four Gemini calls.
It parsed six documents, then correctly reported `insufficient_evidence` because no
extracted facts passed every evidence/comparability gate. The large annual-report PDF
hit the 45-second parser cap, and a separate source returned HTTP 403. Those source
limitations remain visible; the app did not publish an unsupported finding.

The completed report rendered in Edge with no JavaScript page errors. This verifies
the configured end-to-end path, while live discovery quality still requires a
representative evaluation set. Full measured details are in evaluation-report.md.
