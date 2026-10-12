# Final live failure log — 12 October 2026

All twelve clean roster runs completed with abstention. FAIL means no verified
discovery or usable verified figures; PARTIAL means reviewed figures/calculations
were retained, still no discovery. A successful process exit is not a research PASS.
Exact run IDs, source URLs, provider events and limitations are in LIVE-RESULTS.md
and `data/exports/finals-validation/final-validation/<label>`.

Code locations below identify the responsible shared stage or rejection, not proof
that every rejected candidate was correct. Removing the rejection is not a fix.

| Company | Root cause / exact observed symptom | Code location | Suggested shared improvement |
|---|---|---|---|
| Axis Bank | 0 facts; “period end is absent from the cited span”, “monetary scale is absent from the source”; low-confidence OCR, cover identity failures and source cap | `research/live.py:354`, `extraction/validate.py:49`, `research/live.py:317` | Assemble table header/row evidence with exact offsets; prioritise actual financial statements before generic portal/blog leads; improve OCR without accepting uncertain numbers |
| HDFC Bank | 0 facts; “raw value does not occur in the cited passage”, plain/net advances misidentified as gross; scanned cover pages withheld, source cap | `extraction/validate.py:84`, `research/live.py:359`, `research/live.py:317` | Better table geometry and metric definition binding; prove issuer identity from authoritative document metadata; retain merger notes and comparable business boundaries |
| ICICI Bank | 6 facts / 5 reproduced calculations; “Candidate lacked independently originated relevant evidence or was refuted by the additional check.” Missing gross-loan/deposit and funding-mechanism evidence | `research/live.py:543`, `research/live.py:549`, `research/verifier.py:63` | Retrieve independent evidence for the proposed relationship, not issuer mentions; gather funding composition and historical context before proposing a mechanism |
| Kotak Mahindra Bank | 0 facts; “reported advances require an explicit balance row; interest on advances is not a lending stock”, missing scale/duration; target-cover failures | `extraction/validate.py:49`, `research/live.py:317`, `research/live.py:359` | Separate income-statement flow rows from balance stocks; preserve complete dated scope/unit headers and target/subsidiary distinction |
| State Bank of India | 4 facts / 3 reproduced calculations; same failed-corroboration symptom as ICICI. Selected December 2025/2024 despite later available results | `research/live.py:359`, `research/live.py:543`, `research/verifier.py:63` | Rank explicit financial periods independently of publication-date availability; obtain multiple periods and independent mechanism evidence; net advances must remain distinct from gross |
| Bajaj Finance | 0 facts; “scope is absent from the cited span”, “segment is absent from the cited span”, missing scale/raw values; OCR cap | `extraction/validate.py:49`, `research/live.py:354` | Preserve NBFC funding/AUM and segment-table context; prefer short quarterly filings over giant annual reports; restore numeric glyphs using verified rendering |
| Bajaj Finserv | 0 facts; “duration start is absent or not bound to an explicit duration and end date”, label/raw value gaps; irrelevant old SEBI PDF timed out at 45 seconds | `extraction/validate.py:91`, `research/live.py:230`, `research/live.py:359` | Improve group-versus-subsidiary selection and dated segment evidence; exclude irrelevant old offering documents earlier without bespoke issuer URLs |
| Shriram Finance | 0 facts; missing period end, metric label, raw value and scale; multiple low-confidence OCR pages | `research/live.py:354`, `extraction/validate.py:49` | Table-aware parsing and numeric OCR validation across dates/units; choose current issuer results and verify lending/funding scope |
| HDFC Life | 0 facts; “No numeric values for any metric are present in the provided text.” Wrong narrative pages, cover/OCR failures, old SEBI document timeout | `research/live.py:344`, `research/live.py:359`, `research/live.py:317` | Prioritise insurer operating-metric tables and dated result presentations; distinguish group investment commentary from issuer VNB/APE/persistency |
| SBI Life | 0 facts; “The text contains only ESG and employee well-being disclosures.” Emissions Scope 1/2 pages ranked instead of financial metrics | `research/live.py:344`, `research/live.py:359` | Require financial row/value/period context in ranking; accounting scope must not match environmental “Scope 1/2”; select genuine operating tables |
| Jio Financial Services | 0 facts; audit headers/narrative instead of numeric data, missing scale, low-confidence OCR; large PDFs exceeded 45-second parse limit | `research/live.py:359`, `research/live.py:354`, `extraction/validate.py:114` | Handle financial-statement table spans and encoded currency glyphs generically. Hyphenated dates/compound durations were fixed and unit-tested, but the clean live run preceded that fix: post-fix discovery NOT VERIFIED |
| BSE | 0 model calls / 0 facts; “dated official issuer financial disclosures” absent. Other issuers’ exchange filings consumed leads; PDFs timed out. Root portal returns a JavaScript shell | `retrieval/disclosures.py:28`, `retrieval/disclosures.py:53`, `retrieval/issuer_identity.py:12`, `research/live.py:230` | Add bounded public-portal rendering or issuer-bound official index/API discovery shared across all issuers; an exchange hosting a filing does not make it BSE's financial disclosure |

## Unseen, sparse and repeated runs

- Federal Bank: 119.9 seconds, 0 model calls / facts; issuer/domain evidence did not
  yield usable financial passages, annual-report parse timeout. Verify authoritative
  website changes generically (`retrieval/issuer_identity.py:12`), not guessed domains.
- Cholamandalam: 126.6 seconds, 0 model calls / facts; no dated eligible issuer
  financial disclosures; cover/OCR/cap limitations. Same identity/retrieval path.
- Dhanlaxmi: 101.1 seconds, 0 model calls / facts; no dated eligible issuer financial
  disclosure. This is a real sparse-data test, not successful sparse-data discovery.
- HDFC repeat: 130.2 seconds, 0 facts; Bajaj Finance repeat: 151.7 seconds, 0 facts.
  Their unsuccessful conclusions were stable; successful finding stability is
  **NOT VERIFIED**. Source choices, model outputs and durations vary.

## Interruption and validation defects preserved

Original Jio run `023f...` expired after an approximately 17-hour offline interval;
its 63,722-second wall duration is not active research time. The clean retry above
is used in the results matrix. The original BSE validation was cancelled because
the watchdog counted queue wait against execution time. `scripts/validate_live.py`
now uses the actual server start time; BSE's clean retry above is separate. Neither
original was silently rewritten into a success.

Final timing is bounded, but source coverage, extraction, historical comparability,
novelty, independent claim support and successful eight-element publication remain
unproven. Increasing time/tokens or weakening checks would not resolve these causes.
