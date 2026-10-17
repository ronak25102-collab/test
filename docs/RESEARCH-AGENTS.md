# Research agents inside Beyond

Every website run uses the project's own bounded worker coordinator. No chat
agents, extra user action or separate application is required.

## Work split

- **Page verifiers** extract and independently review different original source
  pages in parallel. Each owns its documents, candidate facts and extraction
  state. Only the coordinator merges reviewed results and removes conflicts.
- **Peer researchers** retrieve and verify comparable observations for selected
  peers concurrently. Their facts remain separate from the target company's facts.
  They start alongside optional issuer history, using the complete classified
  exchange directory rather than the search box's 20-result autocomplete slice.
  Requested metrics, scope and period endpoints are bounded to the comparison.
- **Supporting-source and counter-evidence researchers** search concurrently.
  Search results remain unverified leads until original passages are checked.
- **Angle planners** explore applicable metric groups in parallel. Each receives
  one comparable reporting lane and exact existing arithmetic. Duplicate input
  metadata is removed from planning only; final review retains original evidence.
- Counterargument and current falsification checks can overlap, followed by the
  existing composition and independent final publication review.

The live activity view shows actual agent start/completion/failure events. A
worker finishing does not mean it established a discovery.

## Private configuration

Add credentials only to the ignored local `.env`, then restart the services.
`CODECRAFT_SECONDARY_API_KEYS` accepts a JSON array of your own additional keys.
Do not share `.env`; `.env.example` contains only placeholders and settings.

```dotenv
CODECRAFT_SECONDARY_API_KEYS=["your-secondary-key-1","your-secondary-key-2"]
CODECRAFT_KEY_ROUTING=balanced
MAX_RESEARCH_AGENTS=3
MAX_MODEL_CONCURRENCY=3
CODECRAFT_NVIDIA_FALLBACK=true
```

Balanced mode shares credential leases across agents in the same run, limits
each CodeCraft key to one in-flight request, and enforces the configured shared
concurrency cap. Sequential mode preserves the earlier ordered-failover policy.
Keys are deduplicated. More keys are useful only when the provider gives them
usable capacity; keys belonging to one account may share quota and rate limits.

## Failure handling and limits

- Explicit CodeCraft HTTP 402 permits the configured authorized fallback route.
  Explicit 401/403/404/429/503 rejections also permit the next authorized route.
  Their actual HTTP status is retained separately from credit exhaustion. Rejected
  routes are skipped for the rest of this run; reservations remain conservative.
  Generic 400/500 errors, malformed output and uncertain timeouts do not rotate.
- An uncertain billed operation stays pinned and is never silently resent.
- Each agent obeys the same run deadline, cost and token budget. A failed page or
  unavailable peer does not discard other independently verified results.
- Conflicting values are withheld after merge. Invalid publication dates affect
  every fact from that document, including facts returned by another worker.
- Numerical hypothesis repair is skipped when it would spend the protected final
  review window. Unsupported output still cannot publish.
- Live runs reserve separate windows for challenge, composition and independent
  verification at the actual request boundary. Optional page agents inherit
  their parent's reserve. Database event sequencing is serialized across workers
  and API processes, preventing concurrent progress events from aborting a run.

There is no zero-failure guarantee. Provider latency, exhausted credits, blocked
sources and genuinely insufficient evidence can still produce a Partial or
Not established result. Parallelism reduces independent work's elapsed time;
it does not remove the dependent final review or provider/account limits.

The prior BSE run spent about 111 seconds in three serial page reviews and about
159 seconds in hypothesis generation/repair. Those observations identify the
bottleneck; they are not a measured speed claim for the new implementation.
