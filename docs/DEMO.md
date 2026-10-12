# Windows setup, transfer and ten-minute demo

Current target: this Windows PC. Locked installation is tested with Python 3.13.7
and Node 24.11; Python >=3.12 is supported. Install Python, uv and Node using their
official installers. No billing or paid services are required.

## Install on another PC

1. Copy repository source, including uncommitted changes and lockfiles. Exclude
   `.venv`, `node_modules`, caches and runtime process manifests. A plain clone of
   the remote will not contain the unpushed workspace fixes.
2. From the repository root in PowerShell:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1 -InstallOCR
   ```

   This installs locked dependencies, builds the dashboard, migrates SQLite and
   creates `.env` only if absent. Local cache/temp paths avoid Windows cross-drive
   uv failures. Existing keys are never overwritten.
3. Enter the existing keys privately in `.env`, or transfer it securely. Never
   include it in Git, submission archives, screenshots or public reports. Retain
   `FREE_SERVICES_ONLY=true`, zero monetary cap and hard usage limits. Adjust
   `TESSERACT_PATH` if its installed location differs.
4. Verify account access and create the private rate card:

   ```powershell
   .\.venv\Scripts\python.exe scripts/configure_free.py
   .\.venv\Scripts\python.exe -m signal_research.cli universe refresh
   .\.venv\Scripts\python.exe scripts/doctor.py --live
   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local.ps1 start
   ```

   The first command makes a small NVIDIA access probe and checks the Tavily free
   plan. It never activates a subscription. Resolve failures through free-account
   access rather than billing. Doctor checks configuration, not discovery quality.
5. Open http://127.0.0.1:5173/; API docs: http://127.0.0.1:8000/docs. Use
   `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\local.ps1 stop`
   (or replace `stop` with `restart`) to manage owned services. Bypass applies only
   to this process; it does not change the machine execution policy.
   Research data and exports are preserved.

## Validate before presenting

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Push-Location frontend
npm run build
$env:PLAYWRIGHT_CHANNEL='msedge'
npm run test:e2e
Pop-Location
.\.venv\Scripts\python.exe -u scripts/validate_live.py --output data/exports/demo-validation
```

The real matrix is sequential, resumes saved runs and consumes included quota.
Automated tests use mocks/replay where stated; do not call them real issuer
validation. Preserve reports and source/calculation audit evidence.

## Provisional presentation sequence

- First minute: resolve a judge-selected issuer; show profile/cutoff and start.
- While running: explain source trust, date/scope/unit binding, independence,
  calculation reproduction, contradiction search and publication gates.
- By about eight minutes: inspect the actual outcome and source passages. State
  whether it is discovery, partial evidence or abstention.
- Final two minutes: timeline, counterargument, falsification, evidence strength
  and exports. If no discovery exists, explain missing evidence; never substitute
  an old report or SYNTHBANK as a new live finding.

The final clean roster runs took 70.4–291.4 seconds, but all abstained. This proves
bounded completion on this machine, not an eight-minute successful discovery.
The eight-minute deadline guarantees neither a discovery nor a ten-minute total.
Network operations and final processing add overhead. Measured live results must
establish whether this format is viable. SYNTHBANK is only an explicitly labelled
offline architecture tour, never evidence of real-company readiness.


## Current free configuration

Both roles use `nvidia/nemotron-3-super-120b-a12b`, selected after actual access and
binding probes. Advanced search reserves two included credits per request. This
is global configuration, not issuer-specific tuning. Limits are 480 seconds,
100,000 conservative input reservation tokens, 12,000 output tokens, 16 model
calls, 14 searches and 16 fetches. Never describe these as account quota limits.

The official CSV snapshot is dated; refresh it before presenting. Source availability
receipts cannot backdate an undated document for historical runs. Unknown publication
must stay visible. Check `/api/v1/health/ready` for API/worker readiness and
`/api/v1/health/configuration` for live configuration. These do not establish
financial readiness. Exports can contain retained parsed source passages; respect
source reuse terms and keep raw credentials out of all archives.

If the free ledger stops searches, do not enable billing or manually inflate it.
Investigate actual quota and uncertain reservations first. If NVIDIA rejects a
request, keep the clear failure and account limits; no provider/model substitution
is automatic. The latest full matrix, source checks and readiness verdict should
travel with the source archive. Saved real runs are prior research, not fresh live
findings; SYNTHBANK remains synthetic.


## Local submission draft

Generate the one-page solution proposal and a source-only draft archive locally:

```powershell
.\.venv\Scripts\python.exe scripts/draft_report.py
.\.venv\Scripts\python.exe scripts/package_submission.py
.\.venv\Scripts\python.exe scripts/package_validation.py
```

The archive includes uncommitted source and lockfiles, excludes ignored secrets and
runtime data, and stops on credential-shaped content. It does not push or submit
anything. The separate `output/validation-evidence.zip` includes saved live reports,
usage/events, manual verification and link checks, with its own hash manifest. It
contains retained public passages, not credentials, databases or raw PDFs; keep
source reuse terms in mind. Extract it into a review folder, not into the runtime
database. Review the PDF and replace its team-name placeholder before the required
19 October deadline. The current application is not certified ready for the finals.
