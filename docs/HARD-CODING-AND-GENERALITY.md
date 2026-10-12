# Generality and company-reference review

The production worker and live research workflow are shared. Research/extraction
instructions depend on a registered business profile, never a company ticker or
legal-name branch. Names are inserted into the same search and issuer-binding
rules. Numeric thresholds apply to source quality, budgets and evidence gates,
not a specific bank. Neither model roles nor rate cards vary by company.

`data/exports/finals-validation/company-occurrences-final.json` records each grep
occurrence with its file, line, text and classification (285 at the recorded scan;
later documentation may add references). The classifications are:

| Location | Purpose | Violation finding |
|---|---|---|
| DB bootstrap/reference data | Legal names, tickers, aliases, verified domains, business profiles | Identity data; no tailored findings or financial thresholds |
| Retrieval metadata | NSE/BSE authoritative exchange hosts and issuer authorship | Generic source trust, including protection against another issuer's exchange filing |
| Frontend initial search input | HDFCBANK as a starting input | UI default only; saved runs restore their own issuer/cutoff/mode |
| QA scripts | Explicit 12-company matrix, unseen issuers and named probe cases | Validation inputs, not production tuning |
| Tests and fixtures | Named financial disclosures, renamed unseen-bank regression | Controlled test data; never silent live fallback |
| Docs | Actual sources, failures, arithmetic and roster references | Documentation, not live research rules |
| SYNTHBANK replay | Deliberate synthetic architecture fixture | Explicitly restricted to replay; cannot be used with a real issuer |

No real-company canned discovery or analytical branch was found in the reviewed
production paths. That does not prove judge-level generality. The live matrix
records multiple abstentions, including on unseen listed issuers. Tests with
renamed synthetic tables verify parser generality, not live source coverage.

## Limits identified

- `research/ranker.py` is an unused score helper; `research/hypotheses.py` contains
  unused synthetic hypothesis helpers. They are not the live hypothesis/ranking
  system and must not be claimed as implemented scoring. The live path uses
  constrained generated candidates, registered arithmetic, opposing retrieval and
  evidence checks. Replay's synthetic challenger/report builder is separate.
- The scan found no TODO/FIXME implementation placeholders in active backend or
  frontend code. Abstract provider base methods raise NotImplementedError by design.
- Name-based profile inference for newly imported issuers is fallible; a legal name
  alone does not prove an NBFC, insurer or diversified business classification.
- Unknown issuer domains need authoritative, issuer-bound identity evidence. Search
  snippets or guessed website names cannot authorize extraction. Current retrieval
  receipts may establish availability today, but cannot backdate identity evidence.
- Same code and prompts do not guarantee equally useful documents, correct model
  judgments, historical comparability or a non-obvious discovery for every issuer.

Actual alias/name/ticker checks are in `resolution.json`: SBI resolves separately
from SBI Life; typo HDFC Bnak and non-financial Reliance are rejected rather than
guessed. Federal Bank and Cholamandalam use the same path; their final live outcomes
must be read from the matrix. Dhanlaxmi completed a real sparse-data run in 101.1
seconds: zero model calls, zero verified facts, honest abstention. No successful
unseen-company or sparse-data discovery has been verified.
