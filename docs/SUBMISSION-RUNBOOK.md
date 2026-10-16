# Beyond submission and demonstration runbook

Beyond investigates listed financial businesses using public documents. It binds
facts to source passages, checks scope, units and dates, runs reproducible
calculations, tests competing explanations, and publishes a qualified discovery
only when its evidence gates pass. The green and beige dashboard exposes the trail.

**Read the measured acceptance audit before presenting a result.** Tests and
synthetic replay demonstrate software behavior; they are not proof of a live
financial discovery. A partial run or “Not established” candidate is not a verified
finding. Live research now allows ten minutes; earlier five-minute validation
records do not establish success under the new budget. Consult
[the release acceptance record](RELEASE-ACCEPTANCE.md) and
[recorded cold regression results](../reports/regression-final.md) for measured outcomes.

## Install and configure

Requirements: Python 3.12 or newer, uv, Node.js 22 and npm. Use the locked
dependencies. SQLite is sufficient for a local demonstration. PostgreSQL is also
supported. Tesseract is optional for text PDFs and needed for scanned documents.

Keep `.env` and `config/model-rates.json` private. The archive contains neither
credentials nor saved local research. Each presenter must configure API access.

### Windows PowerShell

From the extracted repository root:

```powershell
.\scripts\setup.ps1
Copy-Item .env.submission.example .env
Copy-Item config/model-rates.codecraft.example.json config/model-rates.json
# Edit .env and config/model-rates.json privately before starting research.
.\.venv\Scripts\python.exe scripts/doctor.py --live
.\.venv\Scripts\python.exe -m signal_research.cli universe refresh
.\scripts\local.ps1 start
```

`setup.ps1 -InstallOCR` additionally installs the Windows Tesseract package.
Set `TESSERACT_PATH` to the installed executable if it is not on PATH.
`local.ps1 status`, `restart` and `stop` manage this checkout's services. Restart
after editing `.env`. Do not overwrite an existing private `.env` when updating.

### WSL / Linux

Run from a Linux checkout, using Linux dependencies rather than a Windows `.venv`:

```bash
uv sync --frozen --extra dev
cp .env.submission.example .env
cp config/model-rates.codecraft.example.json config/model-rates.json
# Edit the private files, then:
uv run alembic -c backend/alembic.ini upgrade head
uv run python scripts/doctor.py --live
uv run signal-research universe refresh
cd frontend
npm ci
npm run build
cd ..
uv run uvicorn signal_research.main:app --host 127.0.0.1 --port 8000
```

In a second terminal at the repository root:

```bash
uv run python -m signal_research.worker.main
```

In a third terminal:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173>. API diagnostics are at
<http://127.0.0.1:8000/docs>. Use `Ctrl+C` in each terminal to stop WSL services.

### Provider and rate-card readiness

The submission template uses CodeCraft Opus for extraction and research, with an
explicit NVIDIA fallback, including final review, after definitive credit
exhaustion. Secondary CodeCraft credentials are a JSON array in the private
`CODECRAFT_SECONDARY_API_KEYS`. They do not increase an account's actual quota.
Reports identify the model/provider used and distinguish reported token receipts
from conservative reservations for uncertain requests.

The rate card's `provider` must match `LLM_PROVIDER`. Its models must cover every
configured role and fallback model. Copy the relevant `config/*.example.json`,
then verify its values against your own account; examples are snapshots, not
current price guarantees. Set `SEARCH_USD_PER_CREDIT` from the search account's
terms; zero is valid only for requests covered by an included allowance.
`FREE_SERVICES_ONLY=false` permits configured nonzero rate accounting; it does
not purchase credits, enable billing or remove provider limits.

The configured local run ceiling and stage allowances are safety budgets. They
cannot override provider rate limits, context windows or an exhausted account.
Do not work around a readiness failure by removing numerical or cost checks.

## Present the actual research

1. Open **Research workspace**, enter the judge's company and choose a real
   cutoff date. Use **Live · public sources**, with **Cold start** enabled for a
   rehearsal that must not reuse historical facts. Cold start still uses the
   exchange directory and the same generic metric definitions.
2. Start once. The progress display shows stages and elapsed time. Live mode is
   bounded by the 600-second Live ceiling; it may finish with partial evidence.
   Deep mode uses the longer configured run ceiling and is clearly outside that
   target. Do not describe a Deep run as a five-minute cold run.
3. Lead with the one-sentence discovery and strength rule trace. Explain the
   quantified relationship, structural-break exclusions and verified peer verdict.
   If verification fails, show the missing evidence rather than claiming success.
4. Walk through the required eight output elements: discovery; three to five
   reasons it matters; linked independent evidence; timeline and onset; the
   necessary numbers; strongest counterargument; falsification conditions; and
   evidence strength with limitations. Open claim chips to show the exact passage
   and calculation inputs. Explain whether each “checkable now” test was supported,
   contradicted or not found.
5. Show cache reuse/fresh fact counts and any source, extraction or peer gaps.
   **Saved investigations** reopen persisted reports without rerunning research.
   A saved report retains its original run ID, cutoff and live/synthetic label.
6. Use **Export report** to download one self-contained HTML report. Open that
   file offline, then **Print / Save as PDF**. Source passages remain embedded;
   public original-source links require internet. Share the exported file rather
   than a localhost workspace URL. Synthetic replay must stay labelled synthetic.

An honest fallback demonstration is `SYNTHBANK` in replay mode, with no model or
search request. State explicitly that it is a synthetic software demonstration.
It does not satisfy a live, judge-chosen company discovery by itself.

## Rehearse, verify and package

These live validation commands consume provider/search quota:

```bash
uv run python scripts/validate_discovery.py HDFCBANK --cold-start --seconds 300
uv run python scripts/regression.py --seconds 300 --workers 3
```

The first command writes an isolated database and artifacts under
`data/exports/live-validation/`. The second records unattended company outcomes
in `reports/regression.md`. Preserve failed runs in the audit; a fast provider
failure is not a successful discovery. Do not hand-edit a sealed report's claims,
source passages or attestation to improve its appearance.

Offline software checks:

```bash
uv run ruff check backend tests scripts
uv run pytest
uv run signal-research evaluate --offline
cd frontend
npm run build
npm run test:e2e
cd ..
```

For browser tests, install the supported Playwright browser first, or set
`PLAYWRIGHT_CHANNEL=msedge` when Microsoft Edge is already installed. Browser
tests verify interaction and rendering, not the truth of financial conclusions.

Create the source archive from the repository root:

```bash
uv run python scripts/package_submission.py --output output/Beyond-Final-Submission.zip
```

The archive includes tracked and nonignored source changes, a Git commit ID and
SHA-256 per-file manifest. It excludes local documents, reports, databases,
dependencies and build output; it rejects private configuration, symlinks and
recognized credential shapes. It is a local artifact, not a submitted or
published entry. Share an independently reviewed portable report alongside it
when available. The source ZIP does not contain that private research database.

Use Beyond for evidence-backed research. It does not provide investment advice.

## Response headroom and provider latency

CodeCraft documents that internal reasoning counts toward the completion-token
allowance. A response can truncate even when its final JSON would be small.
See [CodeCraft reasoning documentation](https://www.codecraftapi.com/docs/reasoning).
The template keeps per-stage response allowances explicit. Raising them cannot
remove provider latency or account limits. Local reasoning and peer-source reserves
protect final verification; incomplete or malformed financial output remains withheld.
