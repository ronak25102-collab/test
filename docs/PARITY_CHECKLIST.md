# Stored report parity contract

The reference runs were exported read-only from `data/signal.db`, before writing
any fixture. The exports are immutable snapshots in
`backend/src/signal_research/precomputed/references/`:

| Company | Original run | Documents | Passages | Facts | Calculations | Claims | Timeline events | Verified matched peers |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HDFC Bank | `d45ea5a6-8661-4b6f-a569-b122ba21ea84` | 17 | 3297 | 22 | 19 | 7 | 4 | at least 2 |
| Jio Financial Services | `0f0aaa37-4975-43dc-803f-dbf217b666f8` | 6 | 962 | 10 | 10 | 7 | 8 | 0 |

Both original reports have `publication_status=published`, one discovery,
`outcome=discovery`, cutoff **2026-10-18**, and pass the current `verify_report`.
Both have identical top-level schema keys and generation-metadata keys. Their
arrays differ in length and source coverage. JSON report snapshots are gzip
compressed; `.events.json` contains the actual recorded event sequence and
`.run.json` contains the run row and actual historic provider receipts. These
receipts are historical evidence, never reported as work performed during replay.

## Required report keys and relationships

Preserve `schema_version`, `run_id`, `company`, `cutoff`, `historical_coverage`,
`source_coverage`, `outcome`, `publication_status`, `discoveries`, `limitations`,
`generation_metadata`, `claims`, `timeline_events`, `calculations`, `facts`,
`documents`, `passages`, and `abstention`.

- A published discovery has a one-sentence headline of at most 35 words, three
  to five linked significance statements, a sourced timeline, a counterargument,
  falsification rules, a computed evidence tier, and limitations.
- Every claim's calculation IDs resolve. Each calculation's ordered input facts
  resolve to exact source passages, whose document IDs resolve. Source documents
  retain canonical/final URL, publisher, origin, MIME type, original retrieval
  date, measured SHA256, source availability basis and publication date (nullable
  when genuinely unknown). Passage page, printed page, row, column, section and
  extraction context keys stay present even when their source does not supply
  a value.
- Facts retain raw and normalized value/unit, currency, scope, segment,
  definition, instant/duration, actual start/end, entity and passage ownership,
  verified status and missingness fields.
- All calculation outputs are recomputed by the registered Decimal formula
  engine; authored output mismatches fail the build. No ad-hoc arithmetic is
  substituted for the existing formula engine.
- Peer source bundles retain their own company, documents, passages and facts.
  Comparison rows are reproduced through `compare_peers`, including matching
  scope/definition/periods, each peer's value, median, gap and descriptive label.
- Strength comes from `evidence_tier`, using reviewed qualitative predicates
  and reproduced numerical/peer results. Missing peers cap the tier at Weak.
- Structural screen, comparable history, timeline/onset and filing cadence are
  rerun through the existing deterministic helpers. Unknown onset or a missing
  filing-date estimate remains explicitly unknown.

## Existing generation metadata retained

Both reference reports contain `pipeline`, `configured_provider`, `routing`,
`configured_model_id`, `models_used`, `provider`, `model_id`, `search_queries`,
`research_decisions`, `challenge_reviews`, `opposing_queries`, `context_searches`,
`novelty_status`, `novelty_rationale`, `published_explanation`,
`non_obvious_synthesis_reviewed`, `temporal_reasoning`, `historical_cache`,
`cache_usage`, `structural_breaks`, `peer_benchmark`, `submission_checklist`,
`headline`, `strength_trace`, `tiered_publication`, `falsification_tests`,
`timeline_story`, and `verification_digest`.

Precomputed fixtures retain these keys. This run's model/provider/search/fetch
counts are zero, model IDs are null, `models_used` and query arrays are empty,
cache fresh count is zero, and historical facts are counted as reused.
The original model/query records remain under `reference_review.provenance`,
with original run ID and original verification digest. This explicitly archives
the original review and does not claim a fresh semantic model review.
New keys record `mode=precomputed`, `generated_at`, `data_as_of`, source receipts,
zero usage/budget summary, replay stage durations, cutoff and parity shortfalls.
Empty model/search arrays intentionally have no model/query records to claim;
all their containing keys are retained.

## Endpoints and runtime acceptance

Keep existing request and response schemas for runs, queue, cancellation,
history, resume and configuration. A replay must last the configured duration
using persisted `started_at`; cancellation must prevent publication. Remap all
run-owned UUID references consistently, including IDs nested inside metadata.
Never change the issuer to make a fixture match a request.

After `Store.save_report`, verify HTTP 200 for the report, a linked claim,
calculation, document passages, HTML/JSON/CSV/ZIP exports and history. Existing
frontend tabs, dialogs and print layout consume the same `ResearchReport` and
evidence response structure; no frontend file changes are permitted.

The original strict coverage target is at least 6 documents, 300 passages, 15 facts,
8 calculations, 2 verified matched peers and 3 fiscal years represented by
actual verified fact periods. `build_precomputed.py --strict-parity` fails
loudly for any such shortfall. Normal builds record the precise shortfall and
do not manufacture records to pass it. A passing technical verifier alone is
not a passing original coverage target.

## User-approved descriptive publication policy

All 12 roster constituents now have published reports. At the user's request,
`source_verified_discovery_v2` makes history/document/peer breadth disclosed
targets rather than publication blockers for a reviewed arithmetic finding.
It requires at least four bound verified facts, a registered reproducible
calculation, a dated timeline, linked significance, counterargument and
falsification tests. Original count shortfalls remain in `parity.shortfalls`
and report limitations; they are never turned into fabricated records or passes.

The tier function now accepts an explicit `source_verified_arithmetic` predicate.
Such descriptive findings may be Moderate without two exact-period peers. Strong
still requires the existing independent-origin, non-issuer, peer and challenge
criteria. Issuer-hosted and mirrored copies of the same disclosure remain one
origin. The default function behavior and live pipeline retain the old policy.
The verifier permits this exception only for precomputed descriptive publications
with a calculation-backed derived headline; it still rejects unsupported strength,
inferred claims without independent evidence, broken chains and invalid arithmetic.

SBI Life's standalone designation is bound to a separately retained, contemporaneous
NSE iXBRL filing. Supplemental scope evidence must name the same issuer and share
the original filing date. It cannot supply a missing value, unit, or numerical
binding from a different document. Fiscal table columns are normalized only when
the source itself provides the complete fiscal-calendar/duration anchor.

## Measured gaps in the original references

HDFC meets these minimum record/history/peer counts, but does not contain the
complete requested FY22–FY26 annual series and last eight consecutive quarters.
Its oldest verified observation is September 2023. Jio's original report has
only 10 facts, all covering April–June 2026, and no verified matched peer
comparison. Thus importing Jio alone cannot pass the stronger requested parity
contract or establish a multi-year onset. Research additions must be real and
reviewed before these gaps can be marked resolved.

The authored October 24 Jio fixture now resolves the minimum record/history/peer
gaps with 44 verified facts, 26 calculations, nine documents and 1,250 passages,
including source-bound FY24–FY26 annual observations and September 2026 segment
results. Matched FY25–FY26 consolidated profit comparisons use Bajaj Finserv and
Aditya Birla Capital's own disclosures. They do not benchmark Jio's exact
Investing segment. Under the original peer requirement this capped the discovery
at Weak; the explicitly recorded descriptive arithmetic policy now permits Moderate.
This is distinct from the unchanged archived Jio reference.

Six companies currently pass this minimum contract: HDFCBANK, JIOFIN, ICICIBANK,
SBIN, KOTAKBANK and AXISBANK. BSE, BAJFINANCE, BAJAJFINSV, HDFCLIFE, SBILIFE and
SHRIRAMFIN are also published under the revised policy with real source-bound
discoveries and explicit coverage shortfalls. See PRECOMPUTED_STATUS.md for
measured coverage and source exceptions.

All 23 original report documents' retained raw bytes exist locally and match
their recorded SHA256. The separate `references/source-link-audit.json` records
HTTP requests actually made while preparing fixtures. Most original and peer
links returned HTTP 200. Two CRISIL links returned HTTP 406; old NSE links timed
out or disconnected. A preserved source hash is not a claim that the URL
currently returns HTTP 200. These current accessibility failures remain
explicit; current response hashes are stored separately from original evidence
hashes, so changed web pages never overwrite historic source identity.

## Refresh workflow

Edit `precomputed/inputs/<SYMBOL>.yaml`. Imported inputs reference a compressed,
previously reviewed report and include editable full fact/source bindings.
`additions` may supply real documents, passages, facts, calculation definitions
and `peer_sources`. Authored or changed content requires an `editorial_review`
record identifying the reviewer, actual review date, source-based review notes
and every material claim ID. A new company without a source-reviewed report
fails closed instead of generating an unreviewed discovery.

Run `python scripts/build_precomputed.py SYMBOL`. Use `--strict-parity` to additionally
enforce the original coverage targets. The builder
validates source bytes and normalization, recomputes formulas, peers, history,
breaks, cadence and strength, validates the headline and final verifier, then
writes the fixture and index. Runtime replay performs no source/network calls.

## Initial validation baseline, before the all-company expansion

- Strict offline rebuild: all six published fixtures passed their verifier and
  minimum parity checks against actual local source bytes.
- Ruff passed for backend source, tests and all five new scripts.
- Full pytest: 770 passed, one Windows symlink-permission skip, six expected
  failures explicitly recording the six unfinished constituents. These expected
  failures are unmet deliverables, not completed company coverage.
- The expanded parity test then passed for every published fixture against both
  archived reference structures: 40 unit tests passed, with the same six explicit
  incomplete-company expected failures.
- Integration tests replayed all six real fixtures with an advancing fake clock,
  outbound socket connections disabled, full-duration publication gating and
  issuer-specific report/evidence/export/history endpoints returning HTTP 200.
- `git diff --stat -- frontend` produced no output. No remote push was made.

## Current all-company validation

- Offline build: all 12 fixtures passed source-byte binding, reproducible
  arithmetic, headline validation, publication acceptance and the final verifier.
- Six retain the original larger coverage parity pass. The six additions publish
  under the explicit descriptive policy with original coverage gaps disclosed.
- Focused replay/report/evidence/export/history and source-binding suite:
  118 passed, including all 12 issuers with outbound connections blocked.
- Latest full pytest: **824 passed, one Windows symlink-permission skip,
  one existing Starlette/httpx warning, no expected failures**, in 162.03 seconds.
- Ruff and `git diff --check` passed. Frontend diff is empty; nothing was pushed.
- Follow-up audit: blank passage records exist in the legacy HDFC/Kotak imports
  and one Bajaj Finance page. Their actual counts and recommended treatment
  are recorded in HANDOVER_PRECOMPUTED.md; no replacement text was fabricated.
