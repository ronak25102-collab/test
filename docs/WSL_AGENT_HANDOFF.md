# WSL Agent Implementation Handoff

Read docs/TRACK_A_PRD_AND_IMPLEMENTATION.md in full and implement the application it specifies. That document is the authoritative product requirements and implementation contract. This handoff is a task prompt, not a replacement for the detailed requirements.

## Copy this prompt into your CLI agent

```text
Build the Track A autonomous financial research application described in
docs/TRACK_A_PRD_AND_IMPLEMENTATION.md. Read the entire document before
implementation, inspect the existing repository and applicable AGENTS.md
instructions, and preserve existing work.

Implement a working application, not just a plan, scaffold or static UI.
Use the specified Python FastAPI backend, PostgreSQL durable worker,
React TypeScript dashboard, public-source retrieval, structured LLM
adapter, evidence model and deterministic financial calculations.

Follow the phase sequence and acceptance gates in section 19. Complete
every P0 requirement, including bank, NBFC, insurer, exchange and financial
group coverage; supporting same-sector profiles; independent-source
checks; active counterevidence searches; falsification; cutoff and period
validation; citation verification; honest abstention; recovery; budgets;
and the evidence-linked dashboard. A bank-only prototype is not complete.

Make routine engineering decisions without repeatedly asking for approval.
Document necessary deviations in docs/decisions.md. Ask only for credentials,
account-specific model availability or a materially unresolved constraint.
Continue offline implementation and tests if live credentials are missing.
Do not expose secrets or silently use fixtures in live mode.

Use the Linux filesystem for the active WSL checkout when practical. The
supplied docs are in /mnt/c/Users/ronak/OneDrive/Desktop/projects/bits/docs.
If creating ~/projects/bits, copy these docs there without overwriting
existing work and state clearly which path contains the implementation.

Create real integrations and deterministic offline tests. Do not hard-code
company findings, invent figures, count mirrored filings as independent
sources, apply bank metrics to insurers, mix standalone and consolidated
facts, or claim a live test passed when it only ran against fixtures.

Maintain docs/implementation-status.md as you work, recording phase gates,
checks run and concrete blockers. Run appropriate unit, integration and
browser tests, then bounded live smoke tests when configuration permits.
Implement the operational commands defined in section 18 and confirm that
the README is sufficient for a clean setup.

Finish with runnable code, README, .env.example, dependency locks,
migrations, tests, evaluation report and demo runbook. Your final message
must give the implementation path, startup commands, missing configuration,
test results, live run IDs where available and unresolved limitations.

Do not publish, submit to Unstop, push commits or deploy publicly as an
incidental part of this task. Do not remove the supplied specification.
```

## Files to give the agent

Give the agent this handoff and TRACK_A_PRD_AND_IMPLEMENTATION.md in the same docs directory. The detailed specification already includes the problem-statement requirements, so the original PDF is optional context. Keep any existing repository instructions in effect. The specification contains proposed commands and target paths; the agent must implement them before they can be used.

## Configuration the build will eventually need

- An API key for the chosen model provider and account-accessible model IDs that support the required schemas.
- A Tavily API key for the initial search adapter.
- Docker with WSL integration or a working Linux Docker Engine.
- Current provider pricing in the rate card if enforcing a dollar budget, or an explicit choice to use hard token and call caps with cost marked unknown.

Configure credentials locally in the ignored .env file. They are not needed to read this documentation, scaffold the application or run the offline test suite.
