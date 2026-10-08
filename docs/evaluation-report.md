# Evaluation report

The deterministic suite covers units, periods, missingness, scope,
restatements, calculations, SSRF policy, deduplication, evidence gates,
abstention, CSV formula injection and report invariants. The synthetic bank
fixture reproduces the specification's advances/deposits example using
`Decimal` arithmetic.

## Measured on 8 October 2026

| Check | Result |
| --- | --- |
| `uv run pytest -q` | 18 passed (two dependency deprecation warnings) |
| `uv run ruff check backend/src tests scripts/doctor.py` | Passed |
| `npm run build` | Passed; TypeScript and Vite production bundle |
| `npm run test:e2e` | 1 passed; dashboard shell and controls visible |
| Alembic on a fresh SQLite database | Passed; initial durable schema created |
| CLI replay | Completed; run `830e35a2-376b-4b8a-bd72-eb077b3ffb26` |
| CLI offline evaluation | Discovery; run `6af6ba2d-505e-466b-af15-5508f85c0f61` |
| Live attempt without rate card | Failed with `COST_POLICY_UNCONFIGURED`; run `07210d6d-250d-44af-9cea-4c322a1993c8` |
| Live attempt with unknown-cost override | Failed with `PROVIDER_NOT_CONFIGURED` for missing Tavily key; run `d207cc64-5f7e-49d0-a115-a2f8f83321bc` |

The replay calculation set produced 20.0% advances growth, 10.0% deposit
growth, a 10.0 percentage-point gap, and loan-to-deposit ratios of 80.0%
and 87.272727…%. The report intentionally does not infer funding stress.

The mocked live integration path validates an LLM-shaped fact against an exact
passage, stores the provider-call ledger, and abstains because one fact and one
origin are insufficient for a publishable discovery. This test does not count
as a live provider run.

Live latency, extraction accuracy on public documents and current constituent
coverage are intentionally not claimed until credentials and network access
are configured. Run `signal-research evaluate --suite tests/evaluation/cases.yaml
--offline` for the repeatable offline score.
