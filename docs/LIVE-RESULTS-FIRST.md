# Actual live validation results

Actual local API/background-worker runs using existing free NVIDIA/Tavily access. No mocks or synthetic data.
Abstention is honest failure to establish a discovery, not a successful discovery. Dates and revisions are retained in run artifacts.
Clean retry folders replace interrupted/cancelled rows in the main matrix; originals remain preserved and documented. Revisions differ where later recovery/identity fixes were tested.

| Company | Status | Runtime s | Outcome | Known model input/output | Search credits reserved | Facts/calculations | Remaining issues |
|---|---|---:|---|---:|---:|---:|---|
| Axis Bank | PARTIAL | 118.4 | abstention | 11883/1791 | 4 | 4/2 | Historical YoY growth rates for deposits and borrowings prior to FY2020 to establish baseline trend direction.; Evidence of any accounting policy changes affecting deposit or borrowings classification between FY2020 and FY2026. |
| HDFC Bank | PARTIAL | 352.6 | partial | 25054/5498 + 1 unknown calls | 7 | 6/2 | Provider access recovery and additional independently verified evidence |
| ICICI Bank | FAIL | 86.9 | abstention | 12653/4282 | 4 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| Kotak Mahindra Bank | FAIL | 232.5 | abstention | 16980/4833 | 4 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| State Bank of India | PARTIAL | 116.5 | abstention | 18948/2253 | 7 | 4/2 | a discovery that survives counterevidence and semantic verification |
| Bajaj Finance | FAIL | 164.9 | abstention | 0/0 | 5 | 0/0 | dated official issuer financial disclosures |
| Bajaj Finserv | FAIL | 73.9 | abstention | 0/0 | 5 | 0/0 | dated official issuer financial disclosures |
| Shriram Finance | PARTIAL | 217.9 | abstention | 15144/3966 | 4 | 1/0 | comparable verified facts for a relevant registered calculation |
| HDFC Life Insurance Company | FAIL | 119.0 | abstention | 11142/2764 | 3 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| SBI Life Insurance Company | FAIL | 28.5 | abstention | 11889/267 | 4 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| Jio Financial Services | FAIL | 47.5 | abstention | 0/0 | 5 | 0/0 | dated official issuer financial disclosures |
| BSE Limited | FAIL | 49.2 | abstention | 0/0 | 4 | 0/0 | dated official issuer financial disclosures |
| Bajaj Finance (BAJFINANCE-repeat) | FAIL | 164.8 | abstention | 10832/1758 | 4 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| Cholamandalam Investment and Finance Company Limited (CHOLAFIN) | FAIL | 111.3 | abstention | 0/0 | 6 | 0/0 | dated official issuer financial disclosures |
| The Federal Bank  Limited (FEDERALBNK) | FAIL | 111.4 | abstention | 0/0 | 6 | 0/0 | dated official issuer financial disclosures |
| HDFC Bank (HDFCBANK-repeat) | PARTIAL | 113.5 | abstention | 30165/4516 | 4 | 9/3 | Historical standalone vs consolidated borrowings comparison prior to 2023; Policyholders' funds composition and movement details |

Known tokens are provider-reported successful calls only. Failed/uncertain response usage is unknown; durable budget reservations remain charged conservatively.
Search credits reserve one per basic request or two per advanced request. They are not an independently measured account billing statement. Configured monetary cost is zero for verified included/free access.
No row receives PASS solely from automated checks or successful publication. Published discoveries also require manual source and calculation review.

## AXISBANK: f3e6539e-5326-479f-b174-900a5ea5c8bd

Live artifacts: `data/exports/finals-validation/final/AXISBANK`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 68 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 2 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 74 withheld: OCR numeric confidence is too low; the page was withheld
- Source parse failed: https://www.axis.bank.in/docs/default-source/stock-information/debt/debentures/sr-07-disclosure-document-07-03-24.pdf?sfvrsn=8e2f23f7_1: PDF parsing exceeded its 45-second limit
- Source unavailable: https://www.osfi-bsif.gc.ca/en/guidance/guidance-library/liquidity-adequacy-requirements-lar-2026-chapter-2-liquidity-coverage-ratio: source access returned 403
- Candidate contained a percentage absent from its linked verified facts/calculations; candidate withheld before further retrieval.

Missing requirements:

- Historical YoY growth rates for deposits and borrowings prior to FY2020 to establish baseline trend direction.
- Evidence of any accounting policy changes affecting deposit or borrowings classification between FY2020 and FY2026.
- Segment-level breakdown of deposits and borrowings to verify 'all' segment consistency across the full period.

## HDFCBANK: 30368f59-f4a8-4269-a8e2-f5ee2576d5b4

Live artifacts: `data/exports/finals-validation/final/HDFCBANK`. Status completed; outcome partial.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Document cap reached; remaining source leads were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- Provider work stopped: NVIDIA reached its output token limit before completing structured output. Previously verified evidence was preserved; no discovery was substituted.

Missing requirements:

- Provider access recovery and additional independently verified evidence

## ICICIBANK: 682478ad-20b9-442e-86fc-f78572869d11

Live artifacts: `data/exports/finals-validation/final/ICICIBANK`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 3 withheld: OCR numeric confidence is too low; the page was withheld
- Document cap reached; remaining source leads were withheld.
- Extraction gap: plain or net advances cannot establish gross advances
- Extraction gap: metric label is absent from the cited span
- Extraction gap: Independent source review: Deposits value 1,870,362.74 crore is for period_end 2026-03-31, not June 30, 2026 as required.
- Extraction gap: Independent source review: Borrowings value 226,317.72 crore is for period_end 2026-03-31, not June 30, 2026 as required.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## KOTAKBANK: b86f4dd3-fb46-4fd2-935f-c1dd20fce752

Live artifacts: `data/exports/finals-validation/final/KOTAKBANK`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Source parse failed: https://www.kotak.bank.in/content/dam/Kotak/investor-relation/qip/kmbl-preliminary-placement-document-26may2020.pdf: PDF parser could not read this document
- Extraction gap: metric label is absent from the cited span
- Extraction gap: percentage value lacks an explicit percentage or ratio label
- Extraction gap: Independent source review: The value 11,271.24 crore for gross advances is from the 'Interest/discount on advances/ bills' line item, not the gross advances metric itself; the text does not contain a standalone gross advances figure for the standalone segment.
- Extraction gap: plain or net advances cannot establish gross advances
- Extraction gap: Independent source review: Candidate 0 claims deposits of 16000 Crores INR as of 2026-03-31, but the evidence_quote is null; the source text only mentions deposits of ~16000 crore as part of the Business Undertaking as of 31st March 2026, with no explicit scope or segment binding, and the figure is embedded in a passage about

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## SBIN: 4b4f8323-2899-4869-b623-8431a0788209

Live artifacts: `data/exports/finals-validation/final/SBIN`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Source unavailable: https://tijer.org/jnrid/papers/JNRID2508011.pdf: source access returned 403
- Source unavailable: https://www.summitsecurities.net/Annual_Report_2025-26.pdf: timed out
- Extraction gap: plain or net advances cannot establish gross advances
- Extraction gap: metric label is absent from the cited span
- Extraction gap: Passage text contains Board of Directors' responsibility statements and auditor responsibilities for standalone financial results of State Bank of India. No deposit, advance, asset quality, funding liquidity, or profitability metrics are present in the provided text.
- Candidate lacked independently originated relevant evidence or was refuted by the additional check.

Missing requirements:

- a discovery that survives counterevidence and semantic verification

## BAJFINANCE: 90a0739f-65a7-4bc9-9b59-68feff559bef

Live artifacts: `data/exports/finals-validation/final/BAJFINANCE`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 199 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 200 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 201 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 222 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 223 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 361 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 362 withheld: OCR numeric confidence is too low; the page was withheld
- Source parse failed: https://www.bajajfinserv.in/corporate/media/investor-presentation/FY14/crisil-issuer-profile-bajaj-finance-limited--oct-2013.pdf: PDF parser could not read this document
- OCR page cap reached; remaining scanned pages were withheld.
- Document cap reached; remaining source leads were withheld.

Missing requirements:

- dated official issuer financial disclosures

## BAJAJFINSV: db04efad-fb83-46c4-af3b-7c770adaed3e

Live artifacts: `data/exports/finals-validation/final/BAJAJFINSV`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 199 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 200 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 201 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 222 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 223 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 361 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 362 withheld: OCR numeric confidence is too low; the page was withheld
- Source unavailable: https://www.bajajfinserv.in/finserv-digital-annual-report-fy25/Bajaj%20Finserv%20AR%202024-25.pdf: source exceeds configured size limit
- OCR page cap reached; remaining scanned pages were withheld.
- Document cap reached; remaining source leads were withheld.

Missing requirements:

- dated official issuer financial disclosures

## SHRIRAMFIN: 55064d1f-0a5f-450d-9ec3-663b357770a0

Live artifacts: `data/exports/finals-validation/final/SHRIRAMFIN`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 40 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 41 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 42 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 43 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 44 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 46 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 47 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page cap reached; remaining scanned pages were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- Source unavailable: https://www.nidohomefin.com/static/doc/corporate-governance/NCD-Public%20Issue/Nido%20Home%20Finance%20Limited-%20Prospectus%20dated%20August%2013%2C%202025.pdf: source access returned 403
- OCR page cap reached; remaining scanned pages were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: metric label is absent from the cited span
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: plain or net advances cannot establish gross advances

Missing requirements:

- comparable verified facts for a relevant registered calculation

## HDFCLIFE: 5dfd63e8-b713-47d4-9044-7728c16f0827

Live artifacts: `data/exports/finals-validation/final/HDFCLIFE`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 288 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 362 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 363 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 364 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 365 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 366 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 367 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page cap reached; remaining scanned pages were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- Extraction gap: monetary scale is absent from the source
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: metric label is absent from the cited span
- Extraction gap: duration start is absent or not bound to an explicit duration and end date

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## SBILIFE: c0c10663-b384-4dd4-875e-149b1dea5216

Live artifacts: `data/exports/finals-validation/final/SBILIFE`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Extraction gap: The provided text is a notice of the 26th Annual General Meeting and does not contain financial data, segment reporting, or persistency/product mix metrics for the requested period.
- Extraction gap: Passage text contains no financial data relevant to VNB APE persistency product mix distribution solvency.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## JIOFIN: a81ce683-aeba-4829-8626-3a776641d355

Live artifacts: `data/exports/finals-validation/final/JIOFIN`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Source unavailable: https://www.jfs.in/docs/cms/assets/jfs/investor-relations/financials/quarterly-results/q3-report-2025-2026.pdf: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
- Source unavailable: https://www.jfs.in/disclosure: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
- Source unavailable: https://www.jfs.in/docs/cms/assets/jfs/investor-relations/financials/annual-reports/fy2024-2025/brsr-report-24-25.pdf: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
- Source unavailable: https://www.jfs.in/financials: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
- Document cap reached; remaining source leads were withheld.
- Source unavailable: https://www.jfs.in/annual-report: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)

Missing requirements:

- dated official issuer financial disclosures

## BSE: 87ef632c-ea0c-45bd-8d15-7895418670b0

Live artifacts: `data/exports/finals-validation/final/BSE`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Source unavailable: https://www.bseindia.com/xml-data/corpfiling/AttachLive/a5491ca0-092d-4f99-a329-c62579cc6ef2.pdf: source access returned 404
- OCR page 2 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 23 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 24 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 49 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 80 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 136 withheld: OCR numeric confidence is too low; the page was withheld
- Document cap reached; remaining source leads were withheld.
- Source parse failed: https://www.bseindia.com/xml-data/corpfiling/AttachHis/a8ab95f4-4634-4a2d-bdeb-2865412027b5.pdf: PDF parser could not read this document

Missing requirements:

- dated official issuer financial disclosures

## BAJFINANCE-repeat: 0b3ce514-53ef-46a2-98e4-04006630c3f0

Live artifacts: `data/exports/finals-validation/final/BAJFINANCE-repeat`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 201 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 199 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 200 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 222 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 223 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 361 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 362 withheld: OCR numeric confidence is too low; the page was withheld
- Source parse failed: https://www.bajajfinserv.in/corporate/media/investor-presentation/FY14/crisil-issuer-profile-bajaj-finance-limited--oct-2013.pdf: PDF parser could not read this document
- OCR page cap reached; remaining scanned pages were withheld.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: scope is absent from the cited span
- Extraction gap: metric label is absent from the cited span
- Extraction gap: Passage contains no financial metrics for Bajaj Finance; only narrative about Bajaj Housing Finance Q1 FY26 results and general disclaimers.
- Extraction gap: No source_declared_durations or source_period_columns provided to anchor dates or segment scopes.
- Extraction gap: Entity is Bajaj Finance but passage discusses Bajaj Housing Finance; metrics cannot be mapped without segment/period data.
- Extraction gap: Passage contains only corporate disclaimer and broking service information for Bajaj Financial Securities Limited, not Bajaj Finance financial metrics.
- Extraction gap: No financial data, period columns, or declared durations are present in the source text.
- Extraction gap: Entity context appears to be Bajaj Broking/Bajaj Finance but no extractable financial metrics are provided.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## CHOLAFIN: ae2e075d-0f87-41ad-9639-2a8da6aaa19c

Live artifacts: `data/exports/finals-validation/final/CHOLAFIN`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 156 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 238 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 239 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 266 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 49 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 157 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 247 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 267 withheld: OCR numeric confidence is too low; the page was withheld
- Source unavailable: https://www.investing.com/news/transcripts/earnings-call-transcript-cholamandalam-posts-strong-q1-2026-growth-shares-slip-93CH-4816663: source access returned 403
- OCR page cap reached; remaining scanned pages were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- Source unavailable: https://www.axiscapital.co.in/contents/Hero-FinCorp-Limited-DRHP.pdf: retryable HTTP 502
- Document cap reached; remaining source leads were withheld.

Missing requirements:

- dated official issuer financial disclosures

## FEDERALBNK: 54861222-0557-46b6-846f-fb6bb430a820

Live artifacts: `data/exports/finals-validation/final/FEDERALBNK`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 50 withheld: OCR numeric confidence is too low; the page was withheld
- Source unavailable: https://www.ecb.europa.eu/press/financial-stability-publications/fsr/html/ecb.fsr202605~50566915a7.en.html: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1032)
- OCR page cap reached; remaining scanned pages were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- Document cap reached; remaining source leads were withheld.

Missing requirements:

- dated official issuer financial disclosures

## HDFCBANK-repeat: e5094a05-3b54-4be4-bac5-48c20f74ebb1

Live artifacts: `data/exports/finals-validation/final/HDFCBANK-repeat`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- OCR page 201 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 203 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 316 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 318 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 322 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 484 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page cap reached; remaining scanned pages were withheld.
- Extraction gap: monetary value lacks explicit INR currency
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: metric label is absent from the cited span
- Extraction gap: Independent source review: Deposits value 3167330.55 in crore belongs to consolidated statement dated 30.06.2026, not standalone period ended 30.06.2026; standalone deposits not provided in evidence.
- Extraction gap: Independent source review: Advances value 3156014.45 in crore belongs to consolidated statement dated 30.06.2026, not standalone period ended 30.06.2026; standalone advances not provided in evidence.
- Candidate contained a percentage absent from its linked verified facts/calculations; candidate withheld before further retrieval.

Missing requirements:

- Historical standalone vs consolidated borrowings comparison prior to 2023
- Policyholders' funds composition and movement details
- Subsidiary-level borrowings breakdown contributing to consolidated total
