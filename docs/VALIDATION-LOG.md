# Finals preparation evidence log

Work started 11 October 2026. Existing workspace changes are preserved; no push,
publication, external deployment or submission is authorized.

- Official NSE Indices constituent CSV freshly downloaded: 50 rows, 12 Financial
  Services issuers matching the requested roster. Snapshot saved in the application
  database and `data/exports/finals-validation/official-nifty50.csv`.
- Tavily authenticated `/usage`: Researcher free plan, usage 128/1000, paid-overage
  usage zero. Official free-plan documentation reviewed. Each free-only search now
  checks remaining included quota and refuses unverifiable/non-free plans.
- NVIDIA official Developer Program documentation confirms free hosted prototyping.
  Existing authenticated research succeeded on the configured prototype endpoint;
  a documented remaining-quota API has not been found. Zero-dollar prototype rates
  retain their source URL and verification basis in the private rate card.
- Tesseract 5.4 installed using winget's verified UB-Mannheim package. PDFium remains
  the local renderer. Low-confidence OCR numbers remain withheld.
- Full initial regression run: 280 passed / six failed. Failures exposed the earlier
  token-reserve guard obscuring durable request states and tiny retry allowances.
  Corrected without weakening uncertain-request protections; focused provider,
  retry and account checks subsequently passed (47 tests).
- Shared retrieval now preserves source/time allowances for corroboration; progress
  updates after each parsed document. Expensive sequence comparisons replaced by
  bounded text fingerprints for identifying near-duplicate republications.
- Provisional live target: 480 seconds, separate token/call/document limits retained.
  Real runs are sequential and saved by `scripts/validate_live.py`; completed runs
  are reused on script restart. Failed/partial/abstaining runs are never counted as
  successful discoveries. Artifacts contain no credential values.
- Fresh locked Python install first reproduced Windows uv cross-drive error 17.
  Keeping cache and TEMP/TMP within the checkout fixed installation (63 packages).
  Fresh frontend npm ci installed 122 packages, zero reported vulnerabilities; build
  passed. Fresh SQLite migrations and SYNTHBANK CLI replay completed. A separate
  fresh API process returned HTTP 503 for live research without credentials.
- All roster names/tickers, SBI alias, Federal Bank and Cholamandalam resolved;
  misspelled HDFC Bnak and nonfinancial Reliance were rejected without a report.
  Actual API queued-run cancellation returned CANCELLED without provider work.
- Initial HDFC live pilot: 336.83 seconds, insufficient evidence, nine retained
  facts, six calculations and eight model calls. Human page inspection exposed
  an invalid plain-advances-to-gross definition; see SOURCE-CHECKS.md. Model-produced
  unpublished hypothesis contained invented ratios. Both now have shared rejection
  rules. Original output remains preserved and is not counted as a success.
- Initial NBFC attempt failed on actual Tavily /usage HTTP 429. Official docs specify
  ten usage queries per ten minutes. Replaced per-search network quota checks with
  a shared five-minute ledger and conservative credit reservations. Searches refuse
  unverified or exhausted free allowance; no subscription changes occurred.
- Source date rules now recognize explicit release datelines and earnings
  presentation event dates, not balance-sheet dates. Explicit full-date year/quarter
  duration headers can normalize starts; bare FY labels remain insufficient.
- Extraction guidance is now selected by business type, rather than the old bank
  instruction for all profiles. Exchange domains require issuer authorship so an
  exchange company cannot claim another listed company's filing as its own evidence.
- CSV API and CLI exports share a renderer and retain currency, raw scale, duration,
  segment, definition and source passage alongside normalized figures.

This is a progress log, not a readiness certificate. Results and human source checks
will be recorded as they become available.


## 12 October final validation pass (in progress)

- Refreshed the official NIFTY 50 CSV at 19:07 UTC / 00:37 IST. All 12 expected
  financial constituents, including BSE, are present. The hash remains
  f5ba4027d935ae72879d5c24bbebf0e8439ec8ed504ffdf4175fde69206244b3.
- First complete live matrix includes all 12, Federal Bank, Cholamandalam and two
  repeats. No successful discovery. Later incomplete retest roots are preserved
  and must not be presented as a completed matrix.
- Authenticated probes verified free access to Nemotron Super research and
  Lightning extraction. Advanced Tavily uses two included credits per request.
  Final matrix started with a conservative 740 free credits remaining. Provider
  access does not expose NVIDIA's remaining allowance or guarantee future capacity.
- Current run caps: 480 seconds, 100,000 input reservation tokens, 12,000 output
  tokens, 16 model calls, 14 searches, 16 fetches. UTF-8-byte input estimates are
  conservative reservations, not actual tokenizer measurements. Successful provider
  usage is reconciled; uncertain calls remain reserved. Verification has protected
  input/output/call allowances.
- A dated successful HTTP retrieval can prove availability today without inventing
  an original publication date. Hash, successful access and aware timestamp are
  mandatory; historical cutoffs before receipt still reject it. Unknown publication
  prevents Strong evidence. Migration 0003 preserves this distinction, with a
  pre-migration SQLite backup. Legacy report attestation digests remain compatible.
- Backend: 310 tests passed (one existing Starlette deprecation warning). Production
  frontend build and all 10 Edge tests passed. Browser tests containing mocked
  responses do not prove real-company research quality.
- Current sources were installed in the isolated fresh checkout with frozen uv,
  npm ci/build and migration 0003. All installation steps passed. No private keys
  were copied; fresh live research must remain unavailable without credentials.
- Human ICICI and HDFC comparative-page arithmetic adds six reproduced percentages.
  Merger-related scope changes remain explicit caveats, not organic-growth claims.
- Current-cutoff live results are retained under `current-validation`. A later
  source-format/fallback fix will need separately identified real retests; the
  running worker is not silently reloaded mid-matrix.


## Continuation after interruption

The managed API, worker and frontend had stopped during the interrupted session.
They were restarted. The original Jio run expired against its unchanged absolute
deadline after a long offline interval; its 63,722-second wall duration is not an
active research runtime. Six already-created user runs were processed in order.
The validation watchdog incorrectly included queue wait and cancelled BSE; this
was a validation-script defect. It now checks time since actual execution start,
and both Jio and BSE need clean retry records, with the original failures preserved.

The dashboard now blocks another Start while a run is queued/active, prevents
synchronous duplicate submission, and reuses the same idempotency key after a lost
creation response. Read-only polling reconnects after a local API outage and stops
for a nonexistent run. Fourteen browser tests passed after these changes, including
controlled lost-response, queued duplicate and reconnection scenarios.

Reviewed evidence is now checkpointed after each complete extraction/conflict
resolution batch. Expired-run recovery may save the latest verified snapshot as
partial evidence without provider calls or extending the original deadline.
An empty later snapshot supersedes older figures; it cannot resurrect withheld
facts. This improves future recovery and does not retroactively certify the old
interrupted Jio run. Focused and full checks are being recorded separately.

## Completed validation and local artifacts

- The twelve clean roster runs, Federal Bank, Cholamandalam, Dhanlaxmi and HDFC/Bajaj
  repeats are terminal. Zero discoveries; ICICI retained six facts/five calculations,
  SBI four/three; all other clean runs retained zero verified facts. Clean Jio/BSE
  retries replace interrupted rows in the matrix, preserving original failures.
- Final full backend run: 320 passed, one existing Starlette deprecation warning.
  Frontend production build and 14 Edge cases passed. These are separate from live
  financial validation. Ruff and whitespace checks passed after documentation work.
- Actual in-flight ICICI cancellation completed in 4.138 seconds. Controlled expiry
  of the owned QA run then recovered six reviewed facts with zero additional provider
  calls and no discovery. See `real-inflight-cancellation.json`; deadline shortening
  is explicitly fault injection, not a naturally occurring power outage.
- Current source transferred onto the isolated credential-free installation passed
  frozen setup, npm ci/build, migrations and doctor. Actual fresh API/worker restart
  returned readiness 200, missing-credential live request 503 and saved synthetic
  report 200 (`fresh-latest.json`). Synthetic report persistence is not real research.
- Final HTTP/hash check: 85 sources, 75 HTTP 200, five HTTP 406 and five timeouts;
  85 retained hashes match. HTTP success does not prove claim support. Human source
  arithmetic for final ICICI/SBI reproduced all five/three retained calculations.
- Last conservative free Tavily allowance: 312 credits. NVIDIA quota remains unknown.
  No paid service, billing activation, push, publication or external submission.
- Final audit, twelve-company failure log, setup instructions and the one-page local
  Round 1 draft now state NOT READY explicitly. The draft was rendered and visually
  checked after updating its actual validation results. Source and validation archives
  remain local, with credential screening and content hash manifests.

## 13 October: extraction and document selection

See EXTRACTION-FIX-2026-10-13.md for shared native-PDF, explicit-unit, numeric-grouping,
ranking and fallback changes. Actual HDFC retained twelve figures/ten calculations
in 140.4 seconds; final Axis retest retained six/five in 176.0 seconds. All 18 cells
and 15 calculations were independently checked against rendered source pages.
Both are partial evidence with no discovery; corroboration and budget limitations
remain explicit. Earlier unsuccessful Axis retests remain preserved. The final full
backend suite passed 343 tests (one existing Starlette deprecation warning).
No evidence check was weakened and no company-specific analysis was introduced.

Later HDFC repeat `f960b8f8...` exposed an unfetched annual report despite its
presence in search results. Fresh-lead filtering now occurs before bounded slicing,
and annual-search ranking respects report type. Retest `cf970bfb...`: 205.5 seconds,
twelve retained figures/ten calculations, still PARTIAL with no discovery. Figures
and arithmetic match the previously visually checked unchanged source. The latest
complete backend suite passed 344 tests. See the extraction-fix follow-up section.
