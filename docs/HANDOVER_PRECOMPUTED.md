# Beyond precomputed pipeline handover

## Workspace and user constraints

- Repository: `C:/Users/ronak/OneDrive/Desktop/projects/bits/Beyond-review`, branch `main`.
- Project: `shaurya927/Beyond`; Python/FastAPI/worker under `backend/src/signal_research/`.
- **Do not push to GitHub. Do not use sub-agents.** The user requested lower token usage.
- **Do not modify `frontend/` or the report schema.** Preserve all existing endpoints, tables, settings and live execution.
- Never invent financial facts, quotes, dates, links, hashes, peers or independent origins. Research-time downloads are allowed; runtime playback must be offline.
- Use small local commits. The last committed baseline is `0b07afb`; the all-company expansion described below is currently uncommitted.
- `reports/regression-flash-renewed-search.md` was already untracked before this work. Leave it alone.
- Current user request is a handover. Implementation work stopped to prepare this document.

## User's original objective and later change

The original request was stored PUBLISHED discoveries for every current NIFTY 50 Track A company, with the existing progress animation lasting about 120 seconds, original report/evidence/export shapes, and no live research/provider calls during replay. Reference saved runs are HDFC `d45ea5a6-8661-4b6f-a569-b122ba21ea84` and Jio `0f0aaa37-4975-43dc-803f-dbf217b666f8`.

Initially six companies were implemented and six remained research-only. The user then explicitly requested researching/publishing the remaining six and lowering the criteria. This has now been implemented as an **explicit descriptive publication policy**, rather than fabricated evidence or forced Strong ratings. Publication and strength are separate.

## Current result

**The catalog now has 12 published fixtures and zero incomplete entries. All 12 pass the builder's final verifier and publication acceptance. All currently rate Moderate.**

Original larger coverage parity still passes for the original six. The added six publish under `source_verified_discovery_v2`, with unmet original document/history/peer targets retained in metadata and limitations. Do not describe all 12 as passing the original larger coverage contract.

| Symbol | Documents | Passage records | Facts | Calculations | Original coverage parity | Current finding |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| HDFCBANK | 17 | 3297 | 22 | 19 | Passed | Deposit/borrowing funding mix +2.71 percentage points, June 2025–June 2026, consolidated |
| JIOFIN | 9 | 1250 | 44 | 26 | Passed | Investing profit-share versus gross segment-revenue-share gap 39.96 percentage points, Q2 FY27 |
| ICICIBANK | 28 | 1350 | 78 | 222 | Passed | Funding mix −2.63 percentage points, June–September 2026, standalone |
| SBIN | 10 | 519 | 40 | 128 | Passed | Funding mix −0.45 percentage points, March–June 2026, standalone |
| KOTAKBANK | 22 | 6036 | 25 | 25 | Passed | Funding mix +3.48 percentage points, March 2025–March 2026, standalone |
| AXISBANK | 14 | 1842 | 24 | 47 | Passed | Funding mix −1.06 percentage points, June–September 2026, consolidated |
| BAJFINANCE | 3 | 302 | 35 | 40 | Shortfalls disclosed | MSME gross bad-loan ratio increased 0.51 percentage points while the consolidated ratio improved, September 2025–September 2026 |
| BAJAJFINSV | 1 | 33 | 15 | 16 | Shortfalls disclosed | Retail financing contributed 90.85% of segment profit before tax, Q1 FY27 |
| BSE | 2 | 54 | 6 | 8 | Shortfalls disclosed | Transaction-charge growth exceeded operating-revenue growth by 16.55 percentage points, June 2025–June 2026 |
| HDFCLIFE | 8 | 121 | 59 | 67 | Shortfalls disclosed | Early-renewal premium persistency changed −3 percentage points while new-business value grew, September 2025–September 2026 |
| SBILIFE | 4 | 137 | 24 | 20 | Shortfalls disclosed | New-business value versus premium-equivalent growth gap −6.16 percentage points, June 2025–June 2026 |
| SHRIRAMFIN | 12 | 55 | 33 | 49 | Shortfalls disclosed | Net-profit growth exceeded net-interest-income growth by 21.17 percentage points, September 2025–September 2026, standalone |

Figures above are engine outputs, not manually supplied calculation results. Observation years are not a promise of complete FY22–FY26 annual figures and eight quarterly periods. Research cutoff remains **2026-10-24**; the HDFC imported snapshot retains data-as-of **2026-10-18**.

### Official roster

`precomputed/roster.json` and `docs/PRECOMPUTED_COMPANIES.md` contain legal names, aliases, profiles, NSE/BSE identifiers and IR domains. Membership was obtained from the official NSE constituent CSV and NSE circular `FAOP76591.pdf`, confirming BSE replacing Wipro effective 30 September 2026. BSE itself has no BSE equity scrip code; it is NSE-listed. Do not revert to the old seed universe.

## Already committed foundation

1. `dc605fe`: supported reviewed source table columns/short dates and half-year durations.
2. `0af61f4`: offline runtime, persisted replay duration, provider/fetch guards, configuration/CLI/API integration.
3. `9acaecd`: deterministic builder, source authoring helpers and research/download/status scripts.
4. `6f9f09a`, `f274a1c`: immutable saved-run references, HDFC fixture, researched Jio fixture.
5. `4d4990c`, `ce0a474`: ICICI/SBI and Kotak/Axis fixtures.
6. `83c3a39`: official roster, receipts and then-incomplete issuer inputs.
7. `58fe177`, `0b07afb`: tests, docs and whitespace cleanup.

Core runtime modules are `precomputed/catalog.py`, `runtime.py`, `guard.py`. Settings default to `PIPELINE_MODE=precomputed`, `REPLAY_DURATION_SECONDS=120`. Accepted runs pin mode and duration in existing DB configuration JSON; no migration/schema change was needed. Replay uses DB `started_at`, respects cancellation/resume, reuses HDFC event-stage proportions, uses truthful stored-evidence messages, remaps evidence IDs, saves under the new run ID and supplies report/evidence/exports/history. Provider factories/calls, search and fetch entry points raise inside the offline context. Live caches exclude precomputed reports. Health configuration needs no provider keys/rate card in this mode.

Saved-investigation entries are created when a new replay completes, through the existing history behavior. Fixtures being published does not mean twelve new rows were prepopulated in the user's production DB. No service restart or production replay was performed during the latest expansion.

## Uncommitted expansion and policy changes

- Six new JSON fixtures and rewritten full inputs: BAJFINANCE, BAJAJFINSV, BSE, HDFCLIFE, SBILIFE, SHRIRAMFIN.
- `scripts/research_remaining_precomputed.py`: offline editorial assembly/transcriptions from actual fetched documents. Calculations use the registered Decimal engine. It generates the six inputs; `build_precomputed.py` builds the final fixtures.
- `research_sources/remaining_receipts.json`: actual HTTP-200 receipts/hashes. It includes additional downloaded leads that are not published facts.
- Raw downloaded financial PDF/HTML bytes live locally under ignored `data/precomputed-sources/` and `precomputed/research_sources/`. Runtime does not need them. The offline builder does require them; `gather_precomputed_sources.py --restore-fixtures` can restore missing cited bytes and rejects changed hashes.
- Scratch collector `tmp/collect_remaining.py` is ignored. Do not commit it accidentally.
- Old five authored fixtures/inputs now opt into `publication_policy: source_verified_discovery_v2`. HDFC keeps the original full-reference policy. The bank/Jio authoring scripts were updated to preserve the policy on refresh.
- `evidence/tiers.py` adds optional `source_verified_arithmetic=False`. Default/live behavior stays the same. Explicit descriptive arithmetic may be Moderate without exact-period peers. Strong still requires independent origins, non-issuer support, verified peers and challenge predicates. Issuer-only support remains capped at Moderate.
- `precomputed/builder.py` records policy acceptance, recomputes strength, keeps original coverage shortfalls, enforces at least four verified facts plus calculation/timeline/significance/counterargument/falsification for descriptive publication, and still validates hashes, normalisation, headlines and the final report verifier.
- `research/verifier.py` permits the Moderate/no-peer exception only for the explicit precomputed policy and a calculation-backed derived headline. It does not waive calculation reproduction or claim/source lineage.
- SBI Life press tables lack an explicit standalone label. Their scope is separately anchored to the same issuer's same-date NSE iXBRL filing. `fact_scope_contexts` retains those source passage IDs. Builder requires same issuer origin, matching issuer name and filing date. `validate_candidate` can use supplemental scope text solely for scope; it cannot supply a value missing from the main quote.
- `extraction/dates.py`: reviewed comparative FY/Q1/H1 columns normalize only with an explicit source fiscal-calendar/duration anchor; handles superscript ordinals and spaced table headers. Bare FY/publication-date guesses still fail.
- `extraction/validate.py`: supports whitespace-wrapped metric labels and reviewed compact 13M/61M persistency rows.
- Registry adds the generic bank/NBFC `net_interest_income` metric.
- **Bug fixed:** `research/headline.py` now follows `calculation.input_fact_ids` order instead of report fact-array order. Previously interleaved facts could label a growth gap as the same metric on both sides. BSE and Shriram were reauthored after this fix.
- `authoring.py` supports reviewed custom headlines and additional factual/calculation context.
- README, parity checklist and generated coverage report were updated for all 12 and the explicit revised policy.

## Important source qualifications

- Jio FY24–FY26 annual observations and September 2026 segment disclosures were researched and bound. Its peer context does not benchmark the exact Investing segment; no independent sector-differentiation claim is made.
- Bajaj Finance: current MSME versus Total ratios are from the rendered consolidated provisioning table, PDF page 56. The source's rupee/date/column text was inspected. An older Q1 FY27 deck's publication date is still unknown and disclosed.
- Bajaj Finserv: all top-level profit components, including the negative investments/others component, reconcile exactly to reported segment profit before tax. Do not substitute consolidated PAT or double-count life/general insurance within Insurance total.
- BSE uses issuer-rounded million-rupee presentation data; do not silently replace it with differently rounded signed results. Current headline is consolidated.
- HDFC Life FY23 is on a merged basis; the issuer explicitly says prior years are not comparable. Early-renewal means its 13-month premium persistency. Pension-subsidiary AUM is not substituted for insurer AUM.
- SBI Life uses actual billion-rupee VNB/APE table values and separately retained standalone scope receipts. It supplies one HDFC Life peer bundle; two matched peers are not claimed.
- Shriram uses standalone quarterly PAT/NII from each original-period release. December 2024 PAT includes the housing-finance sale gain; adjusted and as-reported profits are not silently interchanged. Some AUM bindings were deliberately omitted and listed as shortfalls. Later AUM comparisons can differ from original-period disclosures; revisions are not asserted reconciled.
- Some legacy URLs failed current accessibility checks (CRISIL HTTP 406 and older NSE timeouts). Original source bytes/hashes are retained. Do not claim all legacy links now return 200.

## Validation state

- All 12 completed the latest offline build successfully, including source-byte checks and final verifier.
- Latest Ruff check passed after automatic import ordering/unused-import cleanup.
- Focused tests: **118 passed**, one existing Starlette/httpx deprecation warning. This included all 12 actual-fixture replay/evidence/export/history endpoint cases with outbound socket connections blocked, the full-duration fake-clock checks, structural reference keys, source-scope safeguards and headline-input-order regression.
- A few final minor changes followed that focused run (explicit issuer-name check, trace wording, ordinal punctuation handling and authoring-policy persistence). The all-fixture build and Ruff passed after those changes.
- **Latest full pytest completed: 824 passed, one skipped, one warning in 162.03 seconds.** The skip is the existing Windows symlink-permission case; the warning is the existing Starlette/httpx deprecation. There are no expected failures remaining. Exec session `86144` is finished.
- Earlier six-company baseline: 770 passed, one Windows symlink-permission skip, six expected failures for then-incomplete issuers. Those six expected failures have now been removed: the roster test asserts all twelve fixtures exist.
- `git diff --stat -- frontend` is empty. Nothing has been pushed.
- Final `git diff --check` passed; Git printed only line-ending conversion notices.

## Remaining work / recommended next actions

1. The full suite is finished and its result is recorded below and in `docs/PARITY_CHECKLIST.md`. No test process needs polling. Continue with the evidence audit and local review/commits.
2. **Audit blank passage records before describing record counts as nonempty evidence:** current fixtures contain 48 blank records in HDFC, 70 in Kotak (legacy imports), and one in new Bajaj Finance. The other nine have zero. Consider filtering only unreferenced empty passages during fixture assembly/build, preserving immutable reference exports, then rebuild and rerun relevant tests. No fabricated text should be added to those records. This issue was just identified and has not been fixed.
3. Review the current diff, run `git diff --check`, rerun Ruff and relevant pytest if further implementation changes occur. Do not repeatedly rerun the full suite without a change/failure warranting it.
4. Make small **local** commits for policy/parser/headline/tests and the added company fixtures/inputs/receipts/docs. Do not include the preexisting untracked regression report. Do not push.
5. If an actual app smoke test is needed, check/restart the local API/worker with precomputed mode. Keep any smoke-test DB isolated unless the user asks to populate their actual history. Windows may require process-scoped `-ExecutionPolicy Bypass` for `scripts/local.ps1`; do not change machine execution policy or expose private `.env` values.
6. Original broad coverage remains optional follow-up: more annual/quarterly metrics, two exact-period same-profile peers for the six added issuers, missing older publication dates, and legacy URL refresh. Their absence no longer blocks user-approved descriptive publication, but must remain disclosed.

## Commands

Run in the repository root with the existing environment:

```powershell
# Rebuild all 12 from reviewed YAML and local source bytes.
uv run --no-sync python scripts/build_precomputed.py
uv run --no-sync python scripts/precomputed_status.py

# Optional original breadth enforcement; all-company strict mode intentionally
# fails for disclosed coverage gaps. HDFC and the other original six pass.
uv run --no-sync python scripts/build_precomputed.py HDFCBANK --strict-parity

# Reauthor the six added companies from their reviewed source transcriptions.
uv run --no-sync python scripts/research_remaining_precomputed.py

uv run --no-sync ruff check backend/src tests scripts/build_precomputed.py scripts/gather_precomputed_sources.py scripts/research_remaining_precomputed.py scripts/research_bank_precomputed.py scripts/research_jio_precomputed.py scripts/precomputed_status.py
uv run --no-sync pytest -q
git diff --stat -- frontend
git diff --check
```

Do not run the reauthoring/build commands concurrently with one another or with fixture tests; they mutate the same catalog and report files. Provider-backed execution remains available with `PIPELINE_MODE=live`.
