# Validation of the live-research fixes

Measured on Windows with Python 3.12, isolated dependencies and installed Edge:

- `pytest -q`: 69 passed at the final regression checkpoint.
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

These are deterministic engineering checks. The live-provider outputs in tests are
mocked and the replay evidence is synthetic. No account-backed search/model call,
all-constituent research benchmark or real OCR accuracy measurement was performed.
Docker/PostgreSQL are not installed on this local host; the GitHub verification
workflow includes PostgreSQL 16 and migration checks for a compatible runner.

Fresh SQLite migrations reached `0002_evidence_and_heartbeats`. The evaluation
runner read both YAML cases and passed discovery and cutoff-abstention expectations.
Use the workflow and README commands to reproduce checks in WSL or a deployment host.
