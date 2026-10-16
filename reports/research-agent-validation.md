# Project research-agent validation

Beyond now executes its own bounded research workers during website research.
Page verification uses isolated mutable state and a single coordinator merge.
Peer workers retain separate company evidence. Supporting and opposing source
searches overlap. Actual worker lifecycle events appear in the live dashboard.
These are application runtime workers, not agents in a chat application.

## Checks

- Full backend suite: **647 passed, 1 platform skip** (Windows symlink permission).
- Full browser suite: **40 passed**, including actual agent-event states and
  unfinished workers remaining Incomplete after a stopped run.
- Production frontend build, Ruff and whitespace checks passed.
- Both offline evaluation cases passed in an isolated database.
- Barrier-based tests prove overlap of independent source review and credential
  use, avoiding flaky speed thresholds. An integration test independently reviews
  conflicting source pages and verifies the conflicting value is withheld in the
  saved checkpoint. Credential tests cover shared per-run caps, cache reuse,
  explicit credit exhaustion, authorized fallback, and uncertain request pinning.
- Late numerical repair is skipped when it cannot leave enough time for final review.

## Measured context reduction

Rebuilding planning input locally from saved BSE run
`d952abd7-603f-45c9-9f50-42c6e7ba756b` required no provider calls. JSON payload size
fell from **43,307 bytes to 24,789 bytes (42.8%)**. The selected comparable lane
contained nine verified facts and eleven registered calculations. Formula input
order, definition IDs and original evidence remain available; redundant input
metadata is omitted from planning only.

The earlier run spent approximately 111 seconds in serial page reviews and
159 seconds in hypothesis generation/repair. These prior timings motivated the
change. They are not a measured new-run speedup.

## Live acceptance remains open

No new paid research run was started during this change. A fresh successful cold
discovery within five minutes, with verified peers and a completed independent
final review, remains unproven. More keys help only when the provider supplies
usable capacity; account limits may be shared. Provider errors, unavailable
sources and insufficient evidence remain possible. No evidence gate was removed
and no Partial report was relabelled as a discovery.

Configuration and failure semantics: [Research agents](../docs/RESEARCH-AGENTS.md).
