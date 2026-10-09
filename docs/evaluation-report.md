# Validation of the live-research fixes

Measured on Windows with Python 3.12, isolated dependencies and installed Edge:

- `pytest -q`: 81 passed at the final Gemini/setup regression checkpoint.
- `ruff check backend tests`: passed.
- `npm run build`: TypeScript and Vite production bundle passed.
- `PLAYWRIGHT_CHANNEL=msedge npm run test:e2e`: four scenarios passed:
  dashboard, discovery/source/calculation/print navigation, failed-run resume,
  and exchange-directory resolution.
- PDF parsing runs in a disposable process and preserves physical page IDs.
- Mocked live providers exercise a published discovery, refuted candidate,
  semantic-review failure, unverified publication date, deadline stop, and
  crash/resume without repeated paid requests.
- Mutation tests reject changed claims, headlines, significance text, timelines,
  pending entailment and forged calculation outputs. Comparability tests reject
  differing entities, metrics, dates, scopes, units, definitions and segments.
- Registered calculations are exercised across banking and all other profiles.

These are deterministic engineering checks. The live-provider outputs in pytest
are mocked and the replay evidence is synthetic. No all-constituent research
benchmark or real-filing OCR accuracy measurement was performed.
Docker/PostgreSQL are not installed on this local host; the GitHub verification
workflow includes PostgreSQL 16 and migration checks for a compatible runner.

Fresh SQLite migrations reached `0002_evidence_and_heartbeats`. The evaluation
runner read both YAML cases and passed discovery and cutoff-abstention expectations.
Use the workflow and README commands to reproduce checks in WSL or a deployment host.

## Authenticated local setup — 9 October 2026

- Both provider credentials authenticated successfully. Tavily initially reported
  the free Researcher plan with 1,000 unused credits. No billing upgrade was performed.
- Gemini 3.8 and 3.7 returned temporary HTTP 503 capacity errors. Gemini 3.5 Flash
  passed a real structured numeric extraction and the complete financial schema check.
- The Gemini adapter translates Pydantic schemas to the supported native structural
  subset. Original Python format, range, enum, size and extra-field checks remain
  enforced on the output. Thinking tokens are included in the usage ledger.
- The former 3,000-token request allowance truncated a real extraction. The configured
  request allowance is now 8,192, bounded by the original 30,000-token run allowance.
- A synthetic PDF rendered with Poppler and read by installed Tesseract recovered
  `120000` with the numeric-confidence gate enabled. This verifies OCR dependencies.
- Live HDFC Bank run `93a42542-6880-48fc-becc-76a7c93c4ec9` completed: three searches,
  eight fetch attempts, six parsed documents, four successful Gemini extraction calls,
  6,965 input tokens and 7,484 output/thinking tokens. Its configured cost estimate was
  zero; account billing remains controlled by the providers.
- No extracted fact met every comparability/evidence requirement, so the result was
  `insufficient_evidence`, with no fabricated finding or calculation. One source
  returned HTTP 403 and the large annual-report PDF exceeded the 45-second parser cap.
  These limitations are preserved in the report. This is a wiring and abstention test,
  not proof of research accuracy or a successful discovery on that company.
- Headless Edge rendered the completed live report with zero JavaScript page errors.
  The API, worker and dashboard passed readiness checks. The Windows service helper
  passed actual start/restart/status checks while preserving the existing database.

Further quality work should measure financial extraction on representative original
filings and address large-document parsing before claiming reliable coverage across
the full company universe. The configured application currently exposes evidence gaps
explicitly. See LOCAL_SETUP.md for repeatable local operating commands.
