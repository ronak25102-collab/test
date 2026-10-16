# Issuer retrieval and quarterly extraction correction

The original BSE run `f21a047b-97f0-48c0-9dc5-f48991f188b7` retained 17
documents as context and verified no facts. Searches matched other companies'
filings addressed to the exchange. There were no completed LLM research calls;
this failure was not caused by exhausting model credits.

## Generic corrections

- Prefer an exchange-verified ISIN for filing searches. Without one, require
  explicit company-name and exchange-symbol fields. A matching seed identity
  can now be enriched when the user requests an exchange-directory refresh.
- Follow verified issuer navigation when search results fail issuer ownership
  checks, including the short “Investors” navigation label.
- Recognize explicit comparative month-year columns paired with Quarter labels
  in a single-scope income statement. Bare FY labels and ambiguous dates remain
  insufficient. Adjacent abbreviated years no longer become invented day/month dates.
- Bind literal quarterly cells and verify table width, reporting scope, source
  currency and scale. Mixed fiscal/YTD columns remain omitted. Every candidate
  still undergoes independent source review.
- Keep transaction-fee and profit-label synonyms in the shared metric registry.
- Permit one numerical repair of a generated hypothesis. An unrepaired candidate
  remains withheld; all comparability, novelty, adversarial and publication gates
  still apply. Never turn an unestablished candidate into a discovery by relabelling it.

No issuer-specific URL, ticker, date or financial value was added to the pipeline.

## Real-provider validation

Cold run `45723deb-7975-4d32-a154-7af002720014` completed in 274.3 seconds:
9 verified facts, 7 calculations, no reused facts, no published discovery.
The proposed hypothesis included percentages absent from its linked arithmetic
and was withheld. This confirms retrieval/extraction progress, not successful
discovery acceptance. It preceded the literal-table and bounded hypothesis-repair
corrections.

Final cold validation run `d952abd7-603f-45c9-9f50-42c6e7ba756b` completed in
300.1 seconds with a **Partial** outcome: **15 verified facts, 17 calculations,
zero reused facts, no published discovery**. Literal table candidates passed
independent column review. The numerical repair produced a candidate that passed
the local arithmetic gates and entered investigation. The primary CodeCraft key
returned HTTP 402; the configured backup completed the repair. The later review
request timed out with only 10.3 seconds left in the live budget. The original
verified evidence was preserved, with the incomplete review disclosed.

Peer comparison remained inconclusive, and final adversarial/semantic review did
not complete. This is **not** a passing cold-discovery acceptance result. Source
retrieval and quarterly extraction improved; the end-to-end five-minute discovery
target remains unproven. The earlier failed report is retained unchanged.

## Checks

- Full backend suite: **638 passed, 1 skipped** (Windows symlink permission).
- The final shared-registry synonym refactor also passed all 14 quarterly flow
  and duration-binding checks after the full-suite run.
- Ruff and whitespace checks passed.
- Both offline evaluation cases passed in an isolated database, with no paid
  model or search requests.
- No frontend design or evidence/publication rule was removed.
