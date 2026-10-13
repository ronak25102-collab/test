# Track A readiness — 12 October 2026

**13 October update:** shared selection/parser corrections improved actual HDFC
from zero facts to twelve facts/ten calculations, and Axis to six/five. Both
retained partial evidence; neither published a discovery. The latest full backend
suite passed 343 tests. See EXTRACTION-FIX-2026-10-13.md; the historical full roster
matrix below is not a new final-revision success matrix. The verdict remains NOT READY.

**NOT READY for a judge-selected live discovery.** The Windows application starts,
installation is reproducible, and evidence checks reject unsupported outputs.
The final 12-company live matrix, two unseen issuers, two repeated runs and a
sparse-data bank produced no successful discovery. ICICI and SBI retained verified
facts and calculations; the other ten roster companies retained no verified facts.
It is not legitimate to infer readiness from automated tests or honest abstentions.

## Architecture (12 lines)

1. FastAPI `main.py` serves company resolution, run lifecycle, evidence and exports.
2. React/Vite restores saved runs and renders facts, calculations, claims and print view.
3. SQLite persists runs, leases, checkpoints, provider usage and source lineage.
4. A separate durable worker executes the same state machine for every real issuer.
5. Official NIFTY CSV plus exchange identities provide names, tickers, aliases and ISINs.
6. Seven business profiles route questions and registered metrics; no per-company analysis.
7. Tavily search, verified issuer navigation and exchange leads find documents dynamically.
8. Public-only HTTP transport validates redirects, TLS and destination IPs.
9. PDF/HTML/XBRL parsing and confidence-gated local OCR retain source passages and hashes.
10. Extraction binds entity, date, period, unit, segment and scope before independent review.
11. Registered arithmetic feeds hypotheses, opposing searches and semantic claim review.
12. Publication requires independent relevant origins and all eight elements; otherwise abstain.

## Verified engineering work

- Official roster refreshed locally on 12 October IST: all 12 expected companies,
  including BSE, appear in the current Financial Services industry classification.
- NVIDIA Nemotron Super hosted free prototype access verified for both model roles.
  Tavily Researcher allowance checked without enabling paid overage; advanced search
  consumes two included credits. Remaining NVIDIA quota is NOT VERIFIED.
- Protected final-review budgets; durable uncertain-call reservations and no blind
  retries. Current caps: 480 seconds, 100,000 input reservation tokens, 12,000 output
  tokens, 16 model calls, 14 searches and 16 fetches. Input estimates are conservative
  byte-based reservations, not precise tokenization.
- Comparative bank rows preserve standalone/group scope and column order. Plain or
  net advances cannot establish gross advances. INR scales and duration starts are
  validated. Explicit short-year day/month dates do not imply fiscal-quarter dates.
- Publication dates remain unknown when undisclosed. Successful dated retrieval and
  a real content hash can prove current availability, never an earlier historical
  cutoff. Unknown publication cannot receive Strong evidence.
- NVIDIA/Tavily failures remain explicit; retained facts survive interruptions when
  possible. Unsupported or contradictory findings are withheld, never dummy output.
- 320 backend tests passed; one existing Starlette deprecation warning. Production
  frontend build and 14 Edge tests passed. Mocked responses/replay are labelled and
  do not validate live financial quality. Ruff and whitespace checks passed.
- Fresh locked dependency install/build/migrations passed on an isolated source copy;
  actual fresh API/worker health passed, missing credentials returned 503, and an
  existing synthetic report remained readable after migration 0003.
- Human PDF checks reproduced source arithmetic for HDFC, Axis, SBI and ICICI. Merger
  and gross/net definition caveats are explicit. See SOURCE-CHECKS.md.

## Evidence and unresolved limits

The complete first matrix is preserved under `data/exports/finals-validation/final`.
Partial later roots retain their own source fingerprints and configurations; they
must never be described as completed latest-version matrices. The new stable
Super/Super matrix is under `final-validation`. See LIVE-RESULTS.md for measured
runtime, usage, retained facts and missing requirements. Later clean retries used
shared identity/recovery changes; this is not a uniform-final-revision success test.

The twelve clean runs took 70.4–291.4 seconds each, below eight minutes, but all
abstained. Fast abstentions do not validate an eight-minute successful discovery.
The conservative Tavily allowance was 312 credits at the final account check.
NVIDIA remaining quota is unknown. Actual in-flight cancellation completed in
4.138 seconds; a controlled expired-deadline recovery retained six reviewed ICICI
facts with zero additional provider calls and zero discoveries.

The most consequential remaining risk is financial evidence quality, not startup:
source discovery can return parent/subsidiary documents, unclear scope, old periods,
large or inaccessible PDFs; model extraction/review is fallible. Independent
corroboration must support the actual relationship, not merely mention the issuer.
Two snapshots alone do not prove historical development or causality. Novelty is
not established by a headline similarity filter. No success rate, stability or
successful eight-minute discovery target has yet been established.

Manual checking of five cited documents and three reported calculations for each
company remains NOT VERIFIED when no discovery/calculations were produced. We do
not fabricate examples to satisfy those counts. Account exhaustion/rate-limit
faults are controlled tests unless a real rejection is explicitly recorded.

## Account and submission actions

No billing, purchase, upgrade, push, publication, deployment or submission occurred.
Keep credentials private. NVIDIA dashboard quota is not exposed by a documented
API; check it before the finals if available. Tavily's durable local ledger stays
conservative even after a provider refresh; it will not automatically refund
uncertain reservations or adopt replenished credits. A new-PC copy requires secure
keys and a freshly verified private rate card, not a copied invented price.

See FAILURE-LOG.md for per-company symptoms and code locations, and FINAL-AUDIT.md
for the ten remaining score-critical improvements and estimated effort. Full
five-citation semantic checks are NOT VERIFIED: no discovery was published.

The Round 1 PDF is a local draft. The final team name is needed for the required
TeamName_TrackA_Round1.pdf filename. Submission requires separate authorization.
