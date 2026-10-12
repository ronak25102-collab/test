> Historical document. Current Windows setup and free configuration are in [DEMO.md](DEMO.md); measured live results and the current verdict are in [LIVE-RESULTS.md](LIVE-RESULTS.md) and [READINESS.md](READINESS.md). Older model choices, limits and test counts below are not current validation.

# Implementation status

The previous live-path placeholder has been replaced. The same service is used by
the API and CLI for all seven profiles; there are no issuer-specific calculation
rules. Replay is explicitly synthetic and restricted to SYNTHBANK.

Implemented and exercised offline:

- Issuer and unrestricted independent/context discovery; profile-based peers and
  regulator selection; targeted follow-up and opposing searches; ranked candidate
  hypotheses; rejection or qualification after challenge.
- Exact numeric-token, metric, explicit date, scope, currency and monetary-scale
  checks plus independent model checks for row/column and entity binding. Missing
  context and unresolved conflicting disclosures are withheld.
- Registered calculations over comparable original facts. Growth gaps and LDR
  changes have four-input formulas, so their outputs can be independently reproduced.
- Independent semantic claim review followed by a report integrity checksum.
  The checksum binds the reviewed text; it does not itself prove entailment.
  The verifier rejects pending links, broken lineage, altered content, unreproducible
  calculations, unknown/future publication dates and missing relevant origins.
- Source-owned publication metadata, IST cutoff boundaries, exact/substantial-copy
  origin grouping, issuer/exchange-copy grouping, and explicit wire attribution.
- Streamed downloads, decompressed size caps, bounded validated redirect chains,
  and public-IP-pinned TCP connections with original hostname TLS validation.
- Deterministic passage/fact/calculation IDs; HTML table and PDF page/row locators;
  isolated PDF parsing with a timeout; selective OCR with numeric-confidence gates;
  XBRL entity/context/date/dimension/unit retention and entity-expansion protection.
- Persisted tool results, call accounting and budget reservations; cumulative token,
  call, OCR, USD-estimate and wall-clock limits; preserved limits/deadline on resume;
  continuous heartbeat, active-run admission, stale-lease fencing, and atomic report
  publication/terminal state. Uncertain paid calls are never automatically retried.
- Runtime exchange-directory resolution using portable identity lookups, source
  navigation and calculation inputs in the dashboard, explicit failed/cancelled
  states, resume control, printable timeline and clickable original URLs.

Validation: 81 backend tests passed after the Gemini/Tavily setup; the browser
suite has four passing scenarios and the production frontend build passes.
See evaluation-report.md for the final command results and limits of this evidence.

Authenticated Gemini extraction and Tavily calls now pass; a real HDFC Bank run
completed with an explicit evidence-gap abstention. See LOCAL_SETUP.md and
evaluation-report.md for the measured results and the large-PDF timeout encountered.

Remaining deployment validation is external: a representative live company set,
public-PDF/OCR accuracy against manually checked
disclosures, and real concurrent PostgreSQL workers. No real-provider quality or
all-constituent success rate is claimed from mocked tests. Some issuers omit dates,
scope, units or duration starts in retrievable spans; those cases legitimately
abstain. OCR tools are bundled in Docker but may be absent from a host installation.
