# Research completeness audit — 16 October 2026

Checkpoint before changes: `66e0442`, pushed to `main`. Baseline: 519 backend tests, 33 browser tests, frontend build and offline evaluation passed.

## What the critique establishes

Live HDFC run `74226ef6-4fc4-4695-ba90-60d648c77ea8` abstained: 9 verified facts, 6 calculations, no discovery. Its metadata explicitly says live, not synthetic. Two candidates failed numerical checks before targeted counterevidence retrieval. Existing code already supports adversarial search and Weak discoveries, but did not reach those steps in this run. Consolidated balances and standalone revenue cannot establish a common-scope relationship without reconciliation.

The brief requires a non-obvious discovery, 3–5 significance bullets, independent linked evidence, temporal development, reproducible numbers, counterargument, observable falsification condition, and a justified strength rating. A dashboard with honest abstention is not a successful discovery submission. Conversely, labelling an unsupported claim Weak does not make it acceptable. Finals allow a 10-minute presentation/demo followed by 15 minutes of Q&A.

## Subtasks and acceptance criteria

1. **Evidence collection:** seek historical original disclosures across a five-year window; preserve scope, definition, duration and issuer boundaries. Seek regulatory and named peer context separately. Report actual coverage and failed retrieval, never an assumed complete series.
2. **Analysis:** expose comparable research lanes to prevent unsupported cross-scope comparisons; retain registered arithmetic, reviewed source spans and explicit novelty review. Allow a bounded revision of a numerically invalid candidate before abandoning investigation.
3. **Challenge:** persist actual opposing searches, strongest alternatives and their source passages even if publication is withheld. Counts must measure performed checks rather than successful discoveries.
4. **Output:** present an eight-part submission checklist, chronological verified observations, candidate decisions and falsification plans. Clearly distinguish an unverified research candidate from a published discovery. Preserve all eight verified fields on successful outputs.
5. **Validation:** test successful qualified discoveries, rejected and refuted candidates, scope mismatches, historical retrieval, independent-source gaps, and the report interface. Run bounded live issuer checks and disclose their actual outcomes and token usage.

No guarantee that every arbitrary company produces a novel discovery is possible. A successful live discovery must survive source, arithmetic, independence, novelty and semantic review; UI completeness alone is not evidence of success.

## Implemented changes

- The saved HDFC batch actually contained a numerically valid third candidate. Two higher-ranked candidates introduced unverified percentages in their mechanisms. Applying the investigation cap before validation hid the valid candidate. Validation now precedes that cap, with a regression test.
- Candidate and final-report checks enforce a common entity, scope, segment and currency boundary. Headline, significance and temporal analysis cannot quietly use different reporting boundaries. Existing verified Decimal formulas remain mandatory.
- Historical retrieval seeks the current annual disclosure plus older windows. It stops after a useful earlier comparative statement and reserves time for hypothesis, opposing search and final review. Operating-metric extraction covers profile-specific quality, funding cost, margins, mix and distribution rather than only balance growth.
- Original regulator and named peer disclosures are retrieved separately. Peer passages are context; their numbers are not automatically target-company facts or verified peer comparisons.
- Original management commentary is included as bounded evidence so its explanation can be tested against the numbers. There is one bounded research revision after failed candidates, and one draft correction when novelty passed but particular statements failed review. Failed novelty cannot be rescued by rewording.
- New registered calculations reproduce the deposit share of deposits plus borrowings and its change over time. They exclude other liabilities explicitly and make no automatic causal claim. Model calculation context is bounded while the report preserves the full arithmetic trail.
- Source pages lacking minimum date/scope/unit/numeric bindings are skipped before model calls. OCR of unrelated blank artwork is bounded. Low-confidence financial numbers remain prohibited; an exact high-confidence cover heading may establish identity through a separately labelled, nonnumeric OCR passage.
- Optional extraction timeouts pause extraction without repeating the uncertain request. Distinct research requests may use already approved facts. Authentication, quota and other access failures retain their existing handling and conservative token accounting.
- Historical caching reuses only older verified issuer facts from completed live reports, with original document hashes and dates checked. It excludes synthetic data, current observations and prior discoveries. Fresh source searches, new hypotheses and new challenges remain necessary; cache use is visible.
- New reports include all eight output checks, a separately reviewed temporal narrative, actual challenge records, linked opposing passages, candidate tests and honest coverage gaps. Two snapshots with unknown onset stay Limited. A reviewed temporal claim citing at least three comparable reporting dates can establish development within an explicitly bounded window without claiming the true historical onset. Uncited history or different reporting scopes cannot fill that gap. Rejected candidates do not receive a discovery rating. Discovery-linked calculations appear first.
- Planning receives verified structured figures and bounded narrative context. Candidate challenge and final verification receive the original linked numerical spans and the candidate's reporting boundary. Unrelated figures are excluded from those reasoning requests; the saved report retains the full audit trail. Regression tests check that this latency optimization does not remove the evidence needed for review.

## Live development checks

These checks used real configured providers and public sources. They ran against isolated databases and did not replace the website's saved HDFC report. Early iterations intentionally used 480-second caps and, in some cases, 90-second request/60,000-output-token test limits. Those tighter test limits are not the user's private production configuration. Later checks retain the configured token and request-timeout allowances with an explicit overall cap.

| Issuer / development run | Seconds | Verified facts | Calculations | Discoveries | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| HDFC `4331157c` | 480.8 | 24 | 15 | 0 | Partial; optional history consumed the reasoning window |
| ICICI `928a827c` | 460.0 | 6 | 5 | 0 | Partial; excessive OCR and provider timeout |
| Bajaj Finance `327841be` | 471.8 | 4 | 4 | 0 | Partial; missing bindings and provider timeout |
| SBI `d2489952` | 482.8 | 4 | 3 | 0 | Partial; ambiguous date labels and extraction starvation |
| Kotak `35ef74d3` | 481.4 | 12 | 5 | 0 | Partial; source access and provider deadline |
| HDFC `cf745b43` | 601.8 | 24 | 25 | 0 | Partial; no final discovery verification |
| HDFC `296c4f4e` | 424.8 | 12 | 10 | 0 | Partial; research provider timeout |
| HDFC cache check `3b90988a` | 601.3 | 21 | 20 | 0 | Partial; did not reach final approval |

These are failed discovery acceptance checks, not successful demos. They motivated the phase scheduling, source-screening, cache and reasoning-input changes above. Their source coverage and token receipts remain in `data/exports/live-validation/` locally. Uncertain requests may have additional unknown usage; token reservations are not claimed as actual billed usage.

The configured gateway's [reasoning documentation](https://www.codecraftapi.com/docs/reasoning) confirms that reported completion usage includes reasoning and that reasoning models are slower. No undocumented reasoning-control parameter was added to bypass this limitation.

## Completed HDFC discovery

Real live run `605c7f4a-a384-43ed-9a3e-5bc03c176984`, cutoff 15 October 2026, published one **Weak** discovery using the configured CodeCraft `claude-opus-5.5` model ID. The run included fresh retrieval and review, plus disclosed reuse of verified older source observations. It is not a cold-start performance result. The gateway model ID identifies its configured route; it is not independent verification of its upstream model identity.

| Measurement | Recorded result |
| --- | --- |
| Runtime | 824.2 seconds — 13 minutes 44 seconds |
| Verified facts / reproducible calculations | 33 / 58 |
| Documents / timeline events | 24 / 8 |
| Longest comparable annual series | Six reporting dates |
| Why It Matters | Three reviewed statements |
| Relevant supporting origin families | Three |
| Provider-reported input tokens | 213,961 |
| Provider-reported output tokens | 50,418 |
| Total provider-reported tokens | **264,379** |

The relationship concerns the reversal in HDFC Bank's standalone borrowing-versus-deposit growth gap and the changing deposit share of deposits plus borrowings across FY2023–FY2026. The report qualifies the interpretation: merger-acquired balances and classification effects remain the strongest unresolved alternative. It does not establish that management's funding strategy caused the numerical change. Its falsification condition specifies subsequent comparable standalone disclosures and a reversal or a verified reconciliation that explains the pattern.

The report contains all eight sections with original source passages, input figures and arithmetic. Its temporal analysis explicitly leaves true onset outside the observation window unresolved. The immutable report's earlier checklist therefore marks Timeline Limited; later code distinguishes reviewed bounded development from a two-snapshot claim. The sealed report was not rewritten to improve that label.

The completed, verified report was copied into the local website without new provider calls or changes to its attested contents:

`http://127.0.0.1:5173/?run=605c7f4a-a384-43ed-9a3e-5bc03c176984`

The subsequent compact-context repeat, `8b0e592b-a775-452c-9fab-a412fccad508`, was interrupted. After its original deadline, the worker recovered 29 verified facts as a Partial report with no new provider work. Its wall-clock duration is not a valid latency measurement. A faster completed live run has **not** been established.

## Remaining acceptance limits

- The measured successful run exceeds the ten-minute presentation/demo window. A reliable four-to-five-minute fresh live discovery is not demonstrated. Use the transparently labelled saved report for reviewing this result; do not present it as a fresh judge-chosen run.
- The current HDFC finding is Weak because the merger/base-effect alternative remains unresolved. All eight fields being present is not proof of a high-quality or causal discovery.
- Development checks on ICICI Bank, SBI, Kotak and Bajaj Finance did not publish discoveries. Generic profile handling and offline tests do not substitute for successful live validation on these companies.
- Some issuer pages remain unusable because of missing units, scope bindings, access restrictions or OCR confidence. Their financial numbers remain withheld. Peer/regulatory retrieval supplies context; complete verified numerical peer benchmarking is not implemented by this change.
- A provider response or public source cannot be guaranteed to be available, and a defensible novel finding cannot be guaranteed for every company. Partial results retain verified evidence and actual rejected hypotheses instead of inventing the required fields.

## Final local verification

- Ruff: passed for backend, tests and the new live validator.
- Backend suite: **531 passed**, with one existing Starlette/httpx deprecation warning.
- Edge browser suite: **35 passed**, including mobile layout, source dialogs, abstention, recorded challenges and the eight-part output.
- TypeScript and production frontend build: passed.
- Offline evaluation: both synthetic discovery and cutoff-withheld cases passed. These are explicitly synthetic evaluations, not additional live successes.
- The installed HDFC report was fetched from the local API and passed the report verifier again. Website returned HTTP 200 after restarting the managed services.

PostgreSQL-specific integration and migration checks also run in the repository's GitHub workflow; local counts above refer to SQLite. The local environment does not claim a PostgreSQL test run.
