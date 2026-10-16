# Track A engineering and live acceptance — 16 October 2026

**Status: implementation and deterministic checks completed; live discovery acceptance has not passed.** Neither an honest abstention nor an early provider timeout counts as a successful financial discovery. No numerical, source, scope, period, independent semantic-review or novelty gate was removed to manufacture a result.

The latest requested routing is enabled privately: configured NVIDIA for extraction and hypothesis planning, configured CodeCraft Opus for challenge, composition and final verification. It is opt-in through `NVIDIA_PLANNING=true`; credentials remain outside Git. Final review does not silently fall back to NVIDIA in this mode.

## Task commits, in the requested order

| Task | Commit | Implementation and boundaries |
| --- | --- | --- |
| 3 — structural breaks | `2c523cc` | Comparable annual balance jumps above 40% trigger a conservative break flag and original-filing event search. Flagged growth intervals cannot lead the headline. Timeline/chart markers retain exact passages. A keyword establishes a possible documented event, not merger-adjusted organic growth. |
| 4 — peers | `c827707` | Directory/profile-based peer selection; up to three peer extractions in parallel; separate issuer fact stores; exact metric/definition/scope/unit/period matching; at least two verified peers before reproducing median and gap. A 10-percentage-point descriptive screen distinguishes company-specific from sector-wide movement; it is not a causal test. |
| 1 — headline/recovery | `15f1020` | Writer after discovery review; one sentence, at most 35 words, verified numbers and units, bounded regeneration and independently checked rewrite, then registered-arithmetic fallback. Long technical claim remains expandable. Recovery ratios use original verified facts, including a separately registered six-input funding-mix formula. |
| 5 — timeline/onset | `2abe8cd` | Retrieval targets twelve completed quarter ends plus annual history; retains older comparable facts; separates quarters, annual endpoints and durations. Source-linked events, metric sparklines, break markers and bounded sign/slope onset estimates. Missing quarterly evidence is explicit. |
| 6 — falsification | `9479fe7` | Next-quarter primary and annual secondary tests; quarterly filing date estimated from at least two source-owned filing lags. Current reconciliation is actually searched/reviewed; supported/contradicted results need passages and final semantic review. `not_found` is not evidence of absence. |
| 2 — tiers | `69793d0` | Explicit Strong/Moderate/Weak rules and visible trace. Issuer-only figures cap at Moderate; unverified peers cap at Weak. Numerical failures retain a Not established candidate and missing evidence. Source-backed non-causal arithmetic can qualify Weak; uncorroborated inferred claims still cannot publish. |
| 7 — generality | `a3a8714` | Schema-driven bank, NBFC, insurer, AMC, housing-finance and diversified angles; availability/novelty ranking; top covered angles generate hypotheses in parallel. The common pipeline and metric registry are used for every issuer. Unattended isolated cold regression covers eight issuers, including an NBFC and a life insurer. |
| 9 — data quality | `74e79fa` | Publication date cannot precede the covered/verified financial period; contradictory dates become unknown rather than invented. Issuer mirrors retain issuer origin and do not create independence. Generated prose uses grouped rounded figures; original quotations remain verbatim. Extraction gaps appear under Limitations. |
| 8 — runtime/cache | `5be172b` | Live deadline target 300 seconds, per-request stage budgets, final reasoning reserve, concurrent PDF retrieval/peer extraction/planning, per-run cold toggle, actual fresh/reused fact counts and elapsed/stage/fact progress. Deep mode is explicitly outside the live target. |
| 10 — portable/demo output | `ecc6eae` | Single offline HTML export with embedded CSS/JS/data/passages, public source URLs, exact claim dialogs, linked calculation inputs, peer passages and print/PDF view. Discovery, significance, charts, story, evidence, counterargument, falsification and limitations follow the requested reading order. |

Integration commits `8800822`, `2f41060` and `4c1045b` add independent peer reproduction at publication, issuer-mirror coverage, concurrent reservation protection, preservation of zero-fact provider failures, hybrid model routing, financial sentence fact/calculation anchors, ISO/fiscal date handling, portable peer evidence and a Moderate-tier regression for primary observations with verified peers. Every task has automated coverage; synthetic integration tests exercise the actual state machine without paid calls.

## Real cold results

Both batches ran without manual intervention, issuer tuning, synthetic substitutions or historical fact reuse. Each company used a new database. Three companies were allowed concurrently. Full per-company limitations are in the linked reports; private provider call receipts remain in the local validation databases.

| Issuer | Earlier configured provider / seconds / facts | NVIDIA planning + Opus review / seconds / facts |
| --- | --- | --- |
| HDFC Bank | 154.2 / 0 | 122.0 / 0 |
| ICICI Bank | 188.7 / 6 | 110.9 / 0 |
| SBI | 204.7 / 8 | 203.1 / 4 |
| Kotak Mahindra Bank | 107.0 / 0 | 96.0 / 0 |
| Axis Bank | 203.3 / 6 | 91.1 / 0 |
| Bajaj Finance | 72.8 / 0 | 56.6 / 0 |
| Bajaj Finserv | 68.2 / 0 | 98.8 / 0 |
| SBI Life | 92.1 / 0 | 88.2 / 0 |

**Published discoveries: 0/8 in each batch. Verified peer benchmarks: 0/8.** All measured runs returned within five minutes, largely because provider work stopped early or sufficient source bindings were unavailable. This is a runtime bound, not successful end-to-end discovery performance.

- [Latest hybrid regression](../reports/regression.md)
- [Preserved earlier provider regression](../reports/regression-opus-only.md)

The cold hybrid HDFC run extracted six proposed facts in a 25.1-second NVIDIA response, but its independent normalization request timed out at 55 seconds. No proposed fact was promoted to verified. The returned report is Partial, labelled Not established, and retains the provider failure. SBI verified four facts but did not establish a supported new relationship. Bajaj Finance lacked a complete set of source-bound comparable figures. Other hybrid runs primarily stopped on uncertain NVIDIA requests. These requests are never automatically repeated.

An additional cold HDFC **Deep** run with a 900-second budget returned Partial after **901.2 seconds**, with eight verified facts, ten reproducible calculations and no discovery. It is not a five-minute acceptance result. Its provider receipts report **81,334 input + 38,141 output tokens**; unknown consumption on failed/uncertain calls is excluded. It used the prior routing with explicit credit-exhaustion fallback; multiple CodeCraft credentials returned HTTP 402 and a later NVIDIA normalization request succeeded in 87.2 seconds. A later NVIDIA request timed out. This demonstrates that provider latency and allowance are material constraints, rather than proving either model always fails.

The hybrid batch was started before final export and publication-edge integration changes; those changes were covered by the final deterministic suite. Its failed extraction paths did not reach those later stages. The older successful cached HDFC report remains a legacy result and is not presented as a cold success for this implementation.

## Definition of Done: measured status

| Requirement | Status | Evidence / missing work |
| --- | --- | --- |
| 1. Cold HDFC short non-merger headline | **Not met live** | Validator, break exclusion and fallback pass automated tests. Both new cold live runs withheld discovery before composition. |
| 2. At least two matching HDFC peers and verdict | **Not met live** | Full state-machine fixture verifies three peer issuers, matching deposit-growth inputs, median reproduction and sector-wide classification. No cold real benchmark passed. |
| 3. Quarterly timeline, break and onset | **Not met live** | Source-linked quarterly stories/break/onset logic is tested. The Deep HDFC run retained four observed dates with only two-point comparable series; adequate quarterly history and a break receipt were not verified. |
| 4. Next-quarter condition and actual current check | **Not met live** | Cadence, future test and performed current check are exercised in integration tests. Cold runs did not reach supported hypothesis challenge/final publication. |
| 5. Strength trace and issuer-only cap | **Implemented/tested** | Rule trace and caps are displayed. A one-origin observation with verified peers and an addressed counterargument can be Moderate; no-peer case stays Weak. Inferred claims retain independent-origin checks. No real new rating was earned. |
| 6. At least six cold issuers, including NBFC, runtime recorded | **Run completed; discovery generality unproven** | Eight issuers in each batch; all live timings below 300 seconds; zero accepted discoveries. Deep run explicitly exceeded the target. |
| 7. Formatting, portable links, publication dates | **Implemented/tested** | HTML has no external asset requests, local service links are excluded, original passages remain embedded, impossible source dates are rejected/unknown, grouped monetary prose tested. Original quotes retain their exact numbers. |
| 8. All tests pass | **Final verification recorded below** | Backend full suite, browser suite, build, lint, offline evaluation and GitHub PostgreSQL checks. |

## Validation and reproducibility

Run from repository root; these commands do not use real providers unless explicitly marked:

```bash
uv run ruff check backend tests scripts/regression.py scripts/validate_discovery.py
uv run pytest -q
uv run signal-research evaluate --offline
cd frontend
npm run build
npm run test:e2e
```

Paid/quota-consuming, fully automatic cold rehearsal:

```bash
uv run python scripts/regression.py --seconds 300 --workers 3 \
  --artifact-root data/exports/cold-regression-hybrid --output reports/regression.md
```

To regenerate a Markdown result without provider requests, use `--summarize data/exports/cold-regression-hybrid`. Never replace failed run evidence with a synthetic report. Provider results and uncertain reservations have separate accounting.

Final local checks after the export formatting correction `09fe521`: **558 backend tests passed**, **36 browser tests passed**, production build passed, Ruff passed and both offline evaluation cases passed. The one backend warning is the existing Starlette/httpx deprecation. Local database checks use SQLite. The [GitHub integration checkpoint for b51fb25](https://github.com/shaurya927/Beyond/actions/runs/38863927520) passed both backend and frontend jobs, including PostgreSQL integration/publication checks and migrations. The final formatting correction reran the full local suite and triggers the same workflow on push. Portable export QA opened the file without a server, opened an exact claim dialog, observed **zero HTTP asset requests**, generated its PDF print view, and visually inspected all five pages for clipping. The QA report is explicitly synthetic and is not financial validation.

## Remaining risks and unverified metrics

1. The configured providers have not delivered enough timely independently reviewed evidence for a new cold discovery. A stronger model name or a larger token allowance does not establish that result. Known CodeCraft HTTP 402 rejections also threaten final Opus review even if NVIDIA planning succeeds.
2. Same-definition quarterly history, peer medians, structural-event reconciliation and company-specific recovery ratios have **not** been verified in a successful real run of the new pipeline. No recovery percentage is asserted as a real finding.
3. Angle hypothesis generation is parallel, but candidate investigation is bounded and ranked. It can return the first supported candidate; it does not exhaustively investigate every angle to prove a globally optimal discovery.
4. Target extraction is conservative and issuer-focused. Independent qualitative context and separate peer figures do not automatically make target-company facts independently originated. Strong ratings are therefore difficult to earn by design.
5. Filing-date estimates require actual historical publication dates. Unknown dates remain unknown; the system cannot promise an announced disclosure date from a fiscal period label alone.
6. Public portals, PDF access, OCR, search quota, structured-output latency and rate limits can cause partial reports. The UI discloses these gaps; the implementation cannot guarantee that every live judge-chosen company yields a novel discovery in five minutes under the current account/provider conditions.
