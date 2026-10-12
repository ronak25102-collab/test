# Actual live validation results

Actual local API/background-worker runs using existing free NVIDIA/Tavily access. No mocks or synthetic data.
Abstention is honest failure to establish a discovery, not a successful discovery. Dates and revisions are retained in run artifacts.
Clean retry folders replace interrupted/cancelled rows in the main matrix; originals remain preserved and documented. Revisions differ where later recovery/identity fixes were tested.

| Company | Status | Runtime s | Outcome | Known model input/output | Search credits reserved | Facts/calculations | Remaining issues |
|---|---|---:|---|---:|---:|---:|---|
| Axis Bank | FAIL | 103.2 | abstention | 22242/4791 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| HDFC Bank | FAIL | 95.8 | abstention | 35089/4529 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| ICICI Bank | PARTIAL | 119.2 | abstention | 58269/5624 | 16 | 6/5 | loan_to_deposit_ratio_2025_06_30; loan_to_deposit_ratio_2026_06_30 |
| Kotak Mahindra Bank | FAIL | 119.8 | abstention | 20859/4568 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| State Bank of India | PARTIAL | 121.3 | abstention | 30696/2420 | 14 | 4/3 | a discovery that survives counterevidence and semantic verification |
| Bajaj Finance | FAIL | 150.1 | abstention | 20139/3932 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| Bajaj Finserv | FAIL | 221.0 | abstention | 18783/2022 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| Shriram Finance | FAIL | 153.3 | abstention | 18984/4458 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| HDFC Life Insurance Company | FAIL | 179.0 | abstention | 20599/3181 | 8 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| SBI Life Insurance Company | FAIL | 70.4 | abstention | 17765/2224 | 8 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| Jio Financial Services | FAIL | 291.4 | abstention | 29358/2106 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| BSE Limited | FAIL | 205.2 | abstention | 0/0 | 12 | 0/0 | dated official issuer financial disclosures |

## Unseen, sparse and repeated live runs

| Company | Status | Runtime s | Outcome | Known model input/output | Search credits reserved | Facts/calculations | Remaining issues |
|---|---|---:|---|---:|---:|---:|---|
| Bajaj Finance (BAJFINANCE-repeat) | FAIL | 151.7 | abstention | 21561/3125 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| Cholamandalam Investment and Finance Company Limited (CHOLAFIN) | FAIL | 126.6 | abstention | 0/0 | 16 | 0/0 | dated official issuer financial disclosures |
| Dhanlaxmi Bank Limited (DHANBANK-sparse) | FAIL | 101.1 | abstention | 0/0 | 16 | 0/0 | dated official issuer financial disclosures |
| The Federal Bank  Limited (FEDERALBNK) | FAIL | 119.9 | abstention | 0/0 | 14 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| HDFC Bank (HDFCBANK-repeat) | FAIL | 130.2 | abstention | 35089/4658 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |

Known tokens are provider-reported successful calls only. Failed/uncertain response usage is unknown; durable budget reservations remain charged conservatively.
Search credits reserve one per basic request or two per advanced request. They are not an independently measured account billing statement. Configured monetary cost is zero for verified included/free access.
No row receives PASS solely from automated checks or successful publication. Published discoveries also require manual source and calculation review.

## AXISBANK: 22dccbb9-550c-4b08-94f5-6cde2ec7d54c

Live artifacts: `data/exports/finals-validation/final-validation/AXISBANK`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.axis.bank.in/quarterly-results/2026-2027/q1/index.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.axis.bank.in/docs/default-source/shareholders/financial-results-and-other-information/call-transcript/2026-2027/q1fy27-earnings-call.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.axis.bank.in/quarterly-results/2025-2026/q2/index.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.axis.bank.in/shareholders-corner/other-information/investor-presentations; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 68 withheld: OCR numeric confidence is too low; the page was withheld
- Original publication date unknown for https://www.axis.bank.in/docs/default-source/shareholders/financial-results-and-other-information/investor-presentations/2026-2027/investor-presentation-for-the-quarter-ended-30th-june-2026.pdf?sfvrsn=630e6a08_4; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 33 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 28 withheld: OCR numeric confidence is too low; the page was withheld
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.axis.bank.in/docs/default-source/investor-presentations/debt-investor-presentation-june-2026.pdf?sfvrsn=9e1f1034_4; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.axis.bank.in/blogs/financial-planning/get-an-instant-loan-against-your-financial-investments; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.axis.bank.in/blogs/mutual-funds/achieve-financial-goals-with-sips; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.axis.bank.in/learning-hub; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.axis.bank.in/financial-firsts; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: period end is absent from the cited span
- Extraction gap: plain or net advances cannot establish gross advances
- Extraction gap: metric label is absent from the cited span
- Extraction gap: monetary scale is absent from the source
- Extraction gap: percentage value lacks an explicit percentage or ratio label
- Extraction gap: reported advances require an explicit balance row; interest on advances is not a lending stock
- Extraction gap: duration start is absent or not bound to an explicit duration and end date
- Extraction gap: scope is absent from the cited span
- Original publication date unknown for https://www.axis.bank.in/docs/default-source/shareholders/financial-results-and-other-information/quarterly-result/2025-2026/axis-bank-announces-financial-results-for-the-quarter-ended-31st-march-2026.pdf?sfvrsn=278d14ee_5; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Extraction gap: raw value does not occur in the cited passage

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## HDFCBANK: 2425dc45-8e7d-4885-ace4-aad1a4d27ae4

Live artifacts: `data/exports/finals-validation/final-validation/HDFCBANK`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/pdf/about-us/financial-results/2025-2026/quarter-4/press-release-march-2026.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/pdf/investor-meet/2026/Transcript_19Mar_26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/pdf/about-us/financial-results/2025-2026/quarter-4/HDFCBank-Analyst-Apr18-2026-vF.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://smest.in/bond-details/7.95-HDFC-Bank-Limited-21-Sep-2026/INE040A08369; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.facebook.com/FinancewithRajnishMehan/videos/-bigger-branch-network-bigger-profit-per-brancha-banks-total-profit-tells-one-st/1739323423768724; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.hdfc.bank.in/about-us/stakeholders-information/schedule-of-investor-and-analyst-meet-2026; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/personal-banking/about-us/stakeholders-information/disclosures/schedule-of-investor-and-analyst-meet-2025/2026/april/analyst-investor-meet-outcome.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: monetary scale is absent from the source
- Extraction gap: metric label is absent from the cited span
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: plain or net advances cannot establish gross advances
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 2 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 3 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 4 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 5 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 6 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 7 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page cap reached; remaining scanned pages were withheld.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/personal-banking/about-us/stakeholders-information/disclosures/other-stock-exchange-disclosure/2026/july/other-stock-exchange-18july.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## ICICIBANK: 6a2b9c94-9bde-4a85-9a9d-5145dfcaa11f

Live artifacts: `data/exports/finals-validation/final-validation/ICICIBANK`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.icici.bank.in/interest-rate; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.icici.bank.in/find-atm-branch/ifsc-code; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.icici.bank.in/about-us/invest-relations; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 3 withheld: OCR numeric confidence is too low; the page was withheld
- Original publication date unknown for https://www.icici.bank.in/content/dam/icicibank/india/managed-assets/docs/about-us/2027/2026-07-Q1-2027-Investor-presentation.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.icici.bank.in/content/dam/icicibank/india/managed-assets/docs/about-us/2027/transcript-for-earnings-call-held-on-july-18-2026.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.icici.bank.in/about-us/annual; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.icici.bank.in/about-us/investor; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.careratings.com/upload/CompanyFiles/PR/202510121030_ICICI_Bank_Limited.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Source unavailable: https://www.investing.com/news/transcripts/earnings-call-transcript-icici-bank-posts-strong-q1-2026-growth-shares-slip-after-hours-93CH-4799621: source access returned 403
- Original publication date unknown for https://www.careratings.com/uploads/newsfiles/1788171472_Q1FY27%20Strong%20Fundamentals%20Sustain%20Banking%20Sector%20Amid%20Margin%20Pressures.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Extraction gap: duration start is absent or not bound to an explicit duration and end date
- Extraction gap: metric label is absent from the cited span
- Extraction gap: period end is absent from the cited span
- Extraction gap: plain or net advances cannot establish gross advances
- Candidate lacked independently originated relevant evidence or was refuted by the additional check.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: monetary scale is absent from the source
- Candidate lacked independently originated relevant evidence or was refuted by the additional check.

Missing requirements:

- loan_to_deposit_ratio_2025_06_30
- loan_to_deposit_ratio_2026_06_30
- borrowing_to_deposit_ratio_2025_06_30
- borrowing_to_deposit_ratio_2026_06_30
- off_balance_sheet_loan_funding_details
- regulatory_impact_on_funding_mix

## KOTAKBANK: c0c26bc4-5dac-4568-9e03-1c6844708cf8

Live artifacts: `data/exports/finals-validation/final-validation/KOTAKBANK`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.kotak.bank.in/content/dam/Kotak/about-us/media-press-releases/2026/media-release-q3fy26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.kotak.bank.in/content/dam/Kotak/investor-relation/Financial-Result/QuarterlyReport/FY-2026/q2/investor-presentation/Q2FY26-Investor-Presentation.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3611679; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Source unavailable: https://finance.yahoo.com/quote/KOTAKBANK.BO: retryable HTTP 503
- Original publication date unknown for https://www.kotak.bank.in/content/dam/Kotak/investor-relation/Financial-Result/QuarterlyReport/FY-2026/q4/PressRelease/Q4FY26_Press-Release.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.kotak.bank.in/content/dam/Kotak/investor-relation/Financial-Result/QuarterlyReport/FY-2026/q3/investor-presentation/Q3FY26-Investor-Presentation.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://nsearchives.nseindia.com/corporate/KOTAK_17082026062647_InvestorPresentation.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.boimf.in/docs/default-source/investorcorner/factsheets/factsheet-june-2026.pdf?sfvrsn=45e6c27f_3; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.kotak.bank.in/content/dam/Kotak/investor-relation/Financial-Result/QuarterlyReport/FY-2026/q1/Investor-Presentation/Q1FY26_Investor_Presentation.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.kotak.bank.in/content/dam/Kotak/investor-relation/Financial-Result/QuarterlyReport/FY-2026/q3/transcript/Q3FY26-Transcript.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: reported advances require an explicit balance row; interest on advances is not a lending stock
- Extraction gap: monetary scale is absent from the source
- Extraction gap: percentage value lacks an explicit percentage or ratio label
- Extraction gap: metric label is absent from the cited span
- Extraction gap: duration start is absent or not bound to an explicit duration and end date
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: plain or net advances cannot establish gross advances
- Original publication date unknown for https://www.kotak.bank.in/content/dam/Kotak/investor-relation/governance/governance-sebi-tab/2026/revised-media-jun-2026/media-release-bm-july182026signed.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## SBIN: 1d53bbec-c9f9-44ef-b0bf-80578f7a909a

Live artifacts: `data/exports/finals-validation/final-validation/SBIN`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://sbi.bank.in/web/corporate-governance/4th-quarter-2025-26; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://sbi.bank.in/documents/17826/57445696/823.pdf/820b284d-f7e1-98ba-a77d-6a9224d87d4c?t=1770623480510; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.facebook.com/bloombergbusiness/posts/state-bank-of-india-reported-stronger-than-expected-profit-as-rising-retail-cons/1320534479932642; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://sbi.bank.in/web/investor-relations/sbi-financial-highlights-past-5; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://sbi.bank.in/web/investor-relations/investor-relations; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://sbi.bank.in/web/personal-banking/information-services/government-business/financial-literacy; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://sbi.bank.in/web/agri-rural/rural/flc; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://sbi.bank.in/web/agri-rural/rural/financial-inclusion; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page cap reached; remaining scanned pages were withheld.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.facebook.com/Banker4u/posts/the-state-bank-of-india-shows-positive-and-strong-growth/1662849109175717; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.instagram.com/reel/DbvOyxjz65G; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Extraction gap: metric label is absent from the cited span
- Extraction gap: monetary scale is absent from the source
- Extraction gap: reported advances require an explicit balance row; interest on advances is not a lending stock
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: plain or net advances cannot establish gross advances
- Original publication date unknown for https://www.fitchratings.com/research/banks/fitch-affirms-state-bank-of-india-at-bbb-upgrades-vr-to-bb-02-03-2026; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Candidate lacked independently originated relevant evidence or was refuted by the additional check.

Missing requirements:

- a discovery that survives counterevidence and semantic verification

## BAJFINANCE: de8241e8-e908-49cc-97ab-cd131dcf4799

Live artifacts: `data/exports/finals-validation/final-validation/BAJFINANCE`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.bajajfinserv.in/investments/bajfinance-share-price; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/investments/mfsl-share-price; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finance-investor-relations-investor-presentation; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.careratings.com/upload/CompanyFiles/PR/202604130417_Bajaj_Finance_Limited.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.ckycindia.in/ckyc/assets/doc/NodalofficersofthereportingentitiesregisteredwithCKYC.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 201 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 199 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 200 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 222 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 223 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 361 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 362 withheld: OCR numeric confidence is too low; the page was withheld
- Original publication date unknown for https://www.bajajfinserv.in/finserv-digital-annual-report-fy26/assets/pdf/Bajaj%20Finserv%20Limited%20(BFS)%20AR2025-26_CTC.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://cms-assets.bajajfinserv.in/is/content/bajajfinance/bajaj-finance-q3-fy26-earnings-conference-call-transcript?scl=1&fmt=pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://smest.in/bond-details/8.85-Bajaj-Finance-Limited-15-Jul-2026/INE296A08771; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.ckycindia.in/ckyc/assets/doc/Nodal_officer_details_05_August_2025.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finance-digital-annual-report-fy26/chairmens-letter.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finance-digital-annual-report-fy26/digital-first-engagement-driving-financial-inclusion.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: monetary scale is absent from the source
- Extraction gap: percentage value lacks an explicit percentage or ratio label
- Extraction gap: scope is absent from the cited span
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: segment is absent from the cited span
- Extraction gap: metric label is absent from the cited span
- Extraction gap: duration start is absent or not bound to an explicit duration and end date
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.bajajfinserv.in/finserv-digital-annual-report-fy26/assets/pdf/MDA%20from%20Bajaj%20Finserv%20Limited%20BFS%20AR2025-26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page cap reached; remaining scanned pages were withheld.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.bajajfinserv.in/finserv-digital-annual-report-fy26/assets/pdf/CONSOLIDATED%20from%20Bajaj%20Finserv%20Limited%20BFS%20AR2025-26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## BAJAJFINSV: 9cd5eede-02c4-4dfe-abd8-265c82386bb1

Live artifacts: `data/exports/finals-validation/final-validation/BAJAJFINSV`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.bajajfinserv.in/finserv-digital-annual-report-fy26/fy-2026-the-numbers-that-defined-the-year.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for http://www.bajajfinserv.in/finserv-shareholder-download; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Source parse failed: https://www.sebi.gov.in/sebi_data/attachdocs/1343039527809.pdf: PDF parsing exceeded its 45-second limit
- Original publication date unknown for https://www.amfiindia.com/Themes/Theme1/downloads/AverageMarketCapitalization30Jun2025.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finserv-digital-annual-report-fy26/index.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 201 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 199 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 200 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 222 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 223 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 361 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 362 withheld: OCR numeric confidence is too low; the page was withheld
- Original publication date unknown for https://www.bajajfinserv.in/finserv-digital-annual-report-fy26/assets/pdf/Bajaj%20Finserv%20Limited%20(BFS)%20AR2025-26_CTC.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.5paisa.com/stocks/sector/finance; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finance-investor-relations-investor-presentation; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.kotakneo.com/stocks/sectors/finance-stocks; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: duration start is absent or not bound to an explicit duration and end date
- Extraction gap: metric label is absent from the cited span
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: period end is absent from the cited span
- Original publication date unknown for https://www.bajajfinserv.in/finserv-digital-annual-report-fy26/assets/pdf/MDA%20from%20Bajaj%20Finserv%20Limited%20BFS%20AR2025-26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page cap reached; remaining scanned pages were withheld.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.bajajfinserv.in/finserv-digital-annual-report-fy26/assets/pdf/CONSOLIDATED%20from%20Bajaj%20Finserv%20Limited%20BFS%20AR2025-26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## SHRIRAMFIN: 0370ffa1-09c9-4e5c-8bd1-f723a18d7e9d

Live artifacts: `data/exports/finals-validation/final-validation/SHRIRAMFIN`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.shriramfinance.in/fixed-deposit-in-mon; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.shriramfinance.in/financial-faq; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.shriramfinance.in/financial-faqs-financial-services-and-taxes; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.shriramfinance.in/financial-faqs-loan-without-financials; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://cdn.shriramfinance.in/sfl-kalam/files/2026-05/Record-Date-Intimation-SFL-2026.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.icra.in/Rating/ShowRationalReportFilePdfViewer/142292; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 40 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 41 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 42 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 43 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 44 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 46 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 47 withheld: OCR numeric confidence is too low; the page was withheld
- Original publication date unknown for https://cdn.shriramfinance.in/sfl-kalam/files/2026-06/Annual-Report-2025-26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.shriramfinance.in/our-journey; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.spglobal.com/ratings/en/regulatory/article/-/view/type/HTML/id/3503463; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.kotakneo.com/stocks; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: period end is absent from the cited span
- Extraction gap: metric label is absent from the cited span
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: monetary scale is absent from the source
- Extraction gap: percentage value lacks an explicit percentage or ratio label

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## HDFCLIFE: 340cebf5-b40d-4787-8843-3ad881a38425

Live artifacts: `data/exports/finals-validation/final-validation/HDFCLIFE`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.hdfclife.com/content/dam/hdfclifeinsurancecompany/about-us/pdf/investor-relations/financial-information/investor-presentation/hdfc-life-12m-fy2026-call-transcript.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 605 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 399 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 401 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 403 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 405 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 407 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 409 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page cap reached; remaining scanned pages were withheld.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- OCR page cap reached; remaining scanned pages were withheld.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfclife.com/content/dam/hdfclifeinsurancecompany/about-us/pdf/investor-relations/financial-information/investor-presentation/HDFC-Life-9M-FY2026-Investor-Presentation.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Source parse failed: https://www.sebi.gov.in/sebi_data/attachdocs/oct-2017/1509087115907.pdf: PDF parsing exceeded its 45-second limit
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfclife.com/content/dam/hdfclifeinsurancecompany/about-us/pdf/investor-relations/financial-information/Quarterly-financial-results/HDFC-Life-12M-FY2026-Press-Release.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.crisil.com/mnt/winshare/Ratings/RatingList/RatingDocs/HDFCLifeInsuranceCompanyLimited_January%2027_%202026_RR_387052.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfclife.com/content/dam/hdfclifeinsurancecompany/about-us/pdf/investor-relations/financial-information/Quarterly-financial-results/HDFC-Life-Q1-FY2027-Press-Release.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page cap reached; remaining scanned pages were withheld.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfclife.com/content/dam/hdfclifeinsurancecompany/about-us/pdf/investor-relations/financial-information/investor-presentation/HDFC-Life-Q1-FY2027-Investor-Presentation.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://hdfclife.com/; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: metric label is absent from the cited span
- Extraction gap: scope is absent from the cited span
- Extraction gap: duration start is absent or not bound to an explicit duration and end date
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: No numeric values for any metric are present in the provided text.
- Extraction gap: monetary scale is absent from the source

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## SBILIFE: 2ed5ded2-6126-444f-a497-5dd044376aa0

Live artifacts: `data/exports/finals-validation/final-validation/SBILIFE`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://www.sbilife.co.in/documents/20118/569422/SBILife%2BInsurance-Earnings%2Bcalls%2B-Q1%2BFY26.pdf/a4117cb0-6674-6e6c-0f73-aa30df2ffe13?version=1.3&t=1774587655515&download=true; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.icicidirect.com/mailcontent/idirect_sbilife_q4fy26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 41 withheld: OCR numeric confidence is too low; the page was withheld
- Original publication date unknown for https://nsearchives.nseindia.com/corporate/SBILIFE_22042026154453_SEPR22042026_signed.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.sbilife.co.in/documents/d/sbil/news-release_performance_mar-2026-final; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.sbilife.co.in/documents/20118/568834/SBI%2BLife_BRSR%2B2025.pdf/b0b37b8d-2dd0-8246-9d12-250c9fe79a90?version=1.1&t=1774587770381&download=true; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.sbilife.co.in/documents/d/sbil/News%20Release_Performance_June%202026; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: scope is absent from the cited span
- Extraction gap: metric label is absent from the cited span
- Extraction gap: No financial metrics (VNB, APE, persistency, product mix, solvency) are present in the provided passage. The text contains only ESG and employee well-being disclosures.
- Extraction gap: No financial metrics (AUM, VNB, APE, segment profit, VNB margin, persistency ratio, solvency ratio, revenue, net profit) are present in the provided passage. The text contains only environmental and E
- Extraction gap: No financial metrics (AUM, VNB, APE, segment profit, VNB margin, persistency ratio, solvency ratio, revenue, net profit) are present in the provided passage. The passage exclusively discusses Scope 1,
- Extraction gap: Scope 2 greenhouse gas emissions, emission intensity, and sustainability initiatives for SBI Life Insurance Company Limited for FY 2024-25 and FY 2023-24. No values for the requested metrics are found

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## JIOFIN: 5d3be40e-d930-47fc-8ee3-a123f7f14f21

Live artifacts: `data/exports/finals-validation/final-validation/JIOFIN-retry`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Source parse failed: https://www.bseindia.com/downloads/ipo/2023818163653Final%20IM_JIo.pdf: PDF parsing exceeded its 45-second limit
- Source unavailable: https://www.jfs.in/statutory-filings: timed out
- Source unavailable: https://www.jfs.in/download/get-jio-finance-app: timed out
- Source parse failed: https://jep-asset.akamaized.net/cms/assets/jfs/investor-relations/financials/annual-reports/fy2023-2024/annual-report-2023-2024.pdf: PDF parsing exceeded its 45-second limit
- Original publication date unknown for https://www.facebook.com/stocknuj/videos/jio-financial-services-sets-august-10-2026-as-the-record-date-for-its-060share-d/2946781155666987; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Source unavailable: https://www.jfs.in/annual-report: timed out
- Source unavailable: https://www.jfs.in/forms: timed out
- Document cap reached; remaining source leads were withheld.
- Extraction gap: No financial data values are present in the provided text; only narrative and entity information.
- Extraction gap: metric label is absent from the cited span
- Extraction gap: monetary scale is absent from the source
- OCR page 26 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 27 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 28 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 29 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 30 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 31 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 32 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 33 withheld: OCR numeric confidence is too low; the page was withheld
- Extraction gap: No financial data values are present in the provided text; only audit report headers and entity names are visible.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## BSE: 7e71a494-a4c6-47d5-8f42-2bd1e25928f6

Live artifacts: `data/exports/finals-validation/final-validation/BSE-retry`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Source parse failed: https://www.nomuranow.com/portal/site/nnextranet/resources/assets/files/BSE_RHP.pdf: PDF parsing exceeded its 45-second limit
- Source unavailable: https://www.bseindia.com/xml-data/corpfiling/AttachLive/714f5c2e-9473-4d50-8f74-80ad693f12ff.pdf: source access returned 404
- Source unavailable: https://www.bseindia.com/xml-data/corpfiling/AttachLive/a300fc75-e786-4423-8a67-f64d821eafc9.pdf: source access returned 404
- OCR page 49 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 80 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page cap reached; remaining scanned pages were withheld.
- Original publication date unknown for https://www.bseindia.com/xml-data/corpfiling/AttachHis/bb36cffa-352e-463d-b5c9-dc99ff304b8d.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Original publication date unknown for https://bseindia.com/; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Source parse failed: https://www.bseindia.com/xml-data/corpfiling/attachhis/b2612875-1778-45c3-96b2-d30cf438a83a.pdf: PDF parsing exceeded its 45-second limit

Missing requirements:

- dated official issuer financial disclosures

## BAJFINANCE-repeat: ed8bbdfd-9d6c-45a1-abd8-a02a8b6a3401

Live artifacts: `data/exports/finals-validation/final-validation/BAJFINANCE-repeat`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://cms-assets.bajajfinserv.in/is/content/bajajfinance/bajaj-finance-q3-fy26-earnings-conference-call-transcript?scl=1&fmt=pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finance-investor-relations-investor-presentation; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://dsijpub.s3.ap-south-1.amazonaws.com/productAttachment/BrokerRecommendation/BAF-20260203-MOSL-RU-PG012.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Source parse failed: https://www.bseindia.com/corporates/download/10186/Northern%20Arc%20Capital%20Limited%20-%20DRHP_20210716184732.pdf: PDF parsing exceeded its 45-second limit
- Original publication date unknown for https://www.bajajfinserv.in/investments/bajfinance-share-price; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/investments/mfsl-share-price; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finance-investor-relations-financial-results.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finservsecurities-about-us; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finance-investor-relations-alm-statement; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bajajfinserv.in/finance-investor-relations-financial-results; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: monetary scale is absent from the source
- Extraction gap: duration start is absent or not bound to an explicit duration and end date
- Extraction gap: metric label is absent from the cited span
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: scope is absent from the cited span
- Extraction gap: No numeric values for any metric were found in the provided text. The passage contains only narrative discussion without tables or specific figures.
- Extraction gap: No numeric values for any allowed metric were found in the provided evidence.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## CHOLAFIN: 45d0c6f3-a7d7-43d1-9773-a7569b69fbd4

Live artifacts: `data/exports/finals-validation/final-validation/CHOLAFIN-retry`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Original publication date unknown for https://nsearchives.nseindia.com/content/circulars/CML76516.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.bseindia.com/xml-data/corpfiling/AttachLive/83bcec9c-5b58-4ef0-92cf-aba3c7467d58.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 136 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 219 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 220 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 243 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 320 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 137 withheld: OCR numeric confidence is too low; the page was withheld
- Original publication date unknown for https://files.cholamandalam.com/Earnings_Call_Transcript_4_May2026_2cf2ef8c05.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.cholamandalam.com/about-us; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page cap reached; remaining scanned pages were withheld.
- Original publication date unknown for https://files.cholamandalam.com/Chola_Investor_presentation_Mar_26_63135c32db.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page cap reached; remaining scanned pages were withheld.
- Source unavailable: https://www.investing.com/news/transcripts/earnings-call-transcript-cholamandalam-posts-strong-q1-2026-growth-shares-slip-93CH-4816663: source access returned 403
- Original publication date unknown for https://www.cholamandalam.com/investors/financials; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Source unavailable: https://beta.bseindia.com/xml-data/corpfiling/AttachLive/1f9669c9-ff60-4e14-a79d-5ddad888f86e.pdf: source access returned 404
- Original publication date unknown for https://nsearchives.nseindia.com/corporate/SHANTIGEAR_06072026114633_Notice_2026.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Original publication date unknown for https://www.icra.in/Rating/ShowRationalReportFilePdfViewer/144345; public availability is verified by the dated retrieval receipt, not an inferred publication date.

Missing requirements:

- dated official issuer financial disclosures

## DHANBANK-sparse: 3b02173d-8ebc-48cf-bd8d-428053597e3c

Live artifacts: `data/exports/finals-validation/final-validation/DHANBANK-sparse`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 227 withheld: OCR numeric confidence is too low; the page was withheld
- Original publication date unknown for https://www.bseindia.com/stock-share-price/dhanlaxmi-bank-ltd/dhanbank/532180/financials-results; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.icicidirect.com/stocks/dhanlaxmi-bank-ltd-share-price; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.instagram.com/reel/DUCtJRgArcN; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.careratings.com/upload/CompanyFiles/PR/202507120702_Dhanlaxmi_Bank_Limited.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.instagram.com/p/Dd8obmeDWVl; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://trendlyne.com/fundamentals/financials/326/DHANBANK/dhanlaxmi-bank-ltd; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.dhan.bank.in/investor-relations; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.sharekhan.com/stock/dhanlaxmi-bank-ltd; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Source unavailable: https://telanganaslbc.com/wp-content/uploads/2026/21%2048th%20SLBC%20Agenda%20Meeting%20dt%2027.02.2026.pdf: timed out
- Document cap reached; remaining source leads were withheld.
- OCR page cap reached; remaining scanned pages were withheld.
- Original publication date unknown for https://nsearchives.nseindia.com/corporate/CGCL_29062026201400_RoadshowPresentation_June29_2026.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.

Missing requirements:

- dated official issuer financial disclosures

## FEDERALBNK: 1ca95e8f-fd13-43ab-ac7f-018f16882d8d

Live artifacts: `data/exports/finals-validation/final-validation/FEDERALBNK-retry`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- Source parse failed: https://www.federalbank.co.in/annual-report-FY2024/assets/pdf/FederalBank-AR%202024.pdf: PDF parsing exceeded its 45-second limit
- Original publication date unknown for https://www.federalbank.co.in/documents/10180/1128159406/Earnings+Call+Transcript_Q1FY26.pdf/89f9853a-4a1c-c372-92ba-0a0a16146d72?t=1754558852975; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.careratings.com/upload/CompanyFiles/PR/202510121028_The_Federal_Bank_Limited.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.instagram.com/reel/DUDsf64jr_2; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.federalbank.co.in/about-us; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.crisil.com/mnt/winshare/Ratings/RatingList/RatingDocs/TheFederalBankLimited_December%2030_%202025_RR_385602.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.federalbank.co.in/-/annual-reports; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.crisilratings.com/mnt/winshare/Ratings/RatingList/RatingDocs/CredilaFinancialServicesLimited_July%2021_%202026_RR_400778.html; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.federalbank.co.in/-/annual-reports-1; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Original publication date unknown for https://nsearchives.nseindia.com/corporate/FEDERALBNK_17072026135617_FBL_Press_Release_170726_S.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 135 withheld: OCR numeric confidence is too low; the page was withheld

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings

## HDFCBANK-repeat: a0cd5978-df8d-436e-b4b9-98f91bcae1c1

Live artifacts: `data/exports/finals-validation/final-validation/HDFCBANK-repeat`. Status completed; outcome insufficient_evidence.

Issues actually recorded:

- No primary discovery was published because the evidence gates did not pass.
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/personal-banking/about-us/stakeholders-information/disclosures/schedule-of-investor-and-analyst-meet/july/se-intimation-9-july.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/pdf/investor-meet/2026/Transcript_19Mar_26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://web-assets.bcg.com/f2/42/3099132d4f64a777ffe93fc64969/banking-sector-roundup-9mfy26.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/pdf/financial-results/2025-2026/quarter-3/press-release-december-2025.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/pdf/about-us/financial-results/2025-2026/quarter-4/HDFCBank-Analyst-Apr18-2026-vF.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Original publication date unknown for https://smest.in/bond-details/7.95-HDFC-Bank-Limited-21-Sep-2026/INE040A08369; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Source unavailable: https://www.au.bank.in/blogs/best-savings-account-for-individuals-in-india: source access returned 403
- Original publication date unknown for https://www.hdfc.bank.in/about-us/stakeholders-information/schedule-of-investor-and-analyst-meet-2026; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/personal-banking/about-us/stakeholders-information/disclosures/schedule-of-investor-and-analyst-meet-2025/2026/april/analyst-investor-meet-outcome.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- Document cap reached; remaining source leads were withheld.
- Extraction gap: monetary scale is absent from the source
- Extraction gap: metric label is absent from the cited span
- Extraction gap: raw value does not occur in the cited passage
- Extraction gap: plain or net advances cannot establish gross advances
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/pdf/about-us/financial-results/2025-2026/quarter-4/press-release-march-2026.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.
- OCR page 1 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 2 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 3 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 4 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page 5 withheld: OCR numeric confidence is too low; the page was withheld
- OCR page cap reached; remaining scanned pages were withheld.
- Official-portal PDF did not identify the target issuer in its cover; withheld as primary financial evidence.
- Original publication date unknown for https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/personal-banking/about-us/stakeholders-information/disclosures/other-stock-exchange-disclosure/2026/july/other-stock-exchange-18july.pdf; public availability is verified by the dated retrieval receipt, not an inferred publication date.

Missing requirements:

- verified issuer facts with complete metric, value, period, unit and scope bindings
