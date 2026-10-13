# Document selection and extraction correction — 13 October 2026

The user's HDFC run `f257097c-6e35-448f-bcfe-28882b7f9ec9` completed without a
discovery and retained zero verified figures. The relevant quarterly PDF was
retrieved, but its text layer contained damaged decimal separators and a missing
currency symbol. A readable 678-page issuer annual report exceeded the old parser
deadline. Search results also promoted named calls/subsidiary reports above actual
audited/unaudited statements. These were extraction/retrieval problems, not evidence
that the financial figures did not exist.

## Shared changes

- Large PDFs use PDFium native text, with selective glyph-aware balance-page
  extraction. Source page indices, full table headers and resource/deadline limits
  remain intact. The actual retained annual report parsed in 3.31 seconds within
  the unchanged 45-second limit. No raw figures or page numbers are hard-coded.
- The comparative bank parser accepts explicitly declared INR thousand as well as
  crore, retains raw cells and strips schedule numbers only under explicit headers.
  It still requires target identity, exact dates and accounting scope. Plain/net
  advances cannot become gross advances or a gross-loan/deposit ratio.
- Numeric parsing rejects damaged/ambiguous grouping, including `3170830,09`,
  instead of silently multiplying the amount by removing the comma.
- Extraction prioritises readable unit/date/scope-bound financial rows; within
  otherwise comparable evidence, explicit dates outrank publication-date availability.
  Narrative/ESG mentions are not preferred merely for containing metric words.
- When initial extraction fails, the fallback seeks an original annual disclosure
  without requiring both standalone and consolidated scope words in the search.
- Financial-document searches prioritise audited/unaudited results or balance
  statements and rank explicit subsidiary paths lower. These are retrieval leads,
  never issuer or claim proof. Independent/mechanism query ranking is unchanged.
- No OCR confidence threshold, source-independence rule, claim check or eight-element
  publication requirement was weakened. No company-specific result/URL was added.

## Actual live validation

Artifacts: `data/exports/extraction-fix-2026-10-13`. Existing free NVIDIA/Tavily only;
no response mocks. Earlier unsuccessful Axis attempts are preserved, not overwritten.

| Company / run | Runtime | Known model input/output | Search credits reserved | Reviewed facts / calculations | Outcome |
|---|---:|---:|---:|---:|---|
| HDFC `0548673b-dd4d-4c6c-aaf4-42905062bb4d` | 140.4 s | 64,181 / 3,744 | 18 | 12 / 10 | PARTIAL; no discovery |
| Axis `ccdf40f4-de8a-4027-b63f-d7676cbeaf05` | 176.0 s | 53,477 / 6,676 | 18 | 6 / 5 | PARTIAL; no discovery |

HDFC was run before the later statement-ranking/fallback changes; Axis used the
final shared production changes. Source fingerprints/configuration are retained.
This is not a new full twelve-company success matrix. Provider-reported successful
tokens and conservative search reservations are distinct from account-wide quota.

HDFC hypotheses lacked independently originated relevant corroboration, then reached
the model-token/call allowance. Axis lacked corroboration and later stopped because
the remaining response allowance was too small, preserving the final-review reserve.
Reviewed facts/calculations survived both stops. Neither is a successful discovery;
bounded partial evidence is not finals readiness. Remaining work includes reducing
redundant analytical context, obtaining relevant independent evidence, establishing
multi-period development and rerunning all profiles.

## Human verification and tests

Visually inspected HDFC annual PDF page 378 / printed 358 (standalone, INR thousand)
and page 496 / printed 476 (consolidated, INR crore), March 2026/2025. Independently
transcribed all twelve raw cells and reproduced all ten reported calculations.
`manual-HDFC-verified.json` retains the comparisons. These March balances are not
June results, and no organic-growth or gross-advances inference was substituted.

Visually inspected Axis June quarterly results PDF page 7: consolidated INR crore,
June 2026/2025 columns, with March 2026 in the middle. Independently transcribed six
cells and reproduced all five reported calculations (`manual-AXIS-verified.json`).
These source-page checks do not establish independent origins or causal significance.

343 backend tests passed, one existing Starlette deprecation warning. The only
failure during the final broad check was an outdated parser-method expectation;
it was updated from `pdf_layout` to the actual `pdf_pdfium`, retaining its complete
page/header/deterministic-ID assertions. The complete suite then passed. Added
tests cover ambiguous separators, explicit thousand units, financial-page ranking,
statement-versus-call/subsidiary ranking and generated large-PDF header retention.
Generated PDFs and controlled provider responses are engineering tests, not live
issuer evidence. Services were restarted with the corrected shared code. No push,
billing, purchase or external publication was performed for these corrections.

## Subsequent HDFC repeat regression and correction

The user's run `f960b8f8-a7c7-405f-8013-0f7f7a1014c1` still retained zero figures.
Its annual fallback search returned the readable original report, but already-used
releases occupied the bounded retrieval slots and financial-statement ranking did
not respect the annual-report search intent. This demonstrates that the earlier
successful extraction was not sufficient proof of repeated-run reliability.

The shared search now removes already-fetched leads before taking bounded slices.
Annual searches prioritise annual/integrated report metadata (including the generic
IAR abbreviation); explicit subsidiary-path variants rank lower. These are only
retrieval hints; cover identity, units, dates, scope and evidence gates are unchanged.
The regression test includes reused releases, dated integrated reports, quarterly
statements and subsidiary reports. No specific bank or financial result is encoded.

The fresh live HDFC retest `cf970bfb-1bfd-4587-89e0-312b66d33665` completed in
205.5 seconds with twelve reviewed figures and ten calculations. Its unchanged
source cells and calculations match the independent human/Decimal verification
above (`manual-HDFC-repeat-verified.json`). It remains PARTIAL: independent relevant
corroboration was insufficient and exploration stopped to preserve final verification
allowance. The original zero-figure run remains unchanged. Latest full backend
suite: **344 passed**, one existing Starlette deprecation warning; services restarted.
