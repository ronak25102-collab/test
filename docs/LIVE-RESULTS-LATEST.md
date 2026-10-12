# Actual live validation results

**Historical incomplete snapshot.** This file is preserved for provenance.
Use LIVE-RESULTS.md for the completed clean-retry matrix; pending rows below are
not the current state and must not be cited as the final result.

Actual local API/background-worker runs using existing free NVIDIA/Tavily access. No mocks or synthetic data.
Abstention is honest failure to establish a discovery, not a successful discovery. Dates and revisions are retained in run artifacts.

| Company | Status | Runtime s | Outcome | Known model input/output | Search credits reserved | Facts/calculations | Remaining issues |
|---|---|---:|---|---:|---:|---:|---|
| Axis Bank | FAIL | 103.2 | abstention | 22242/4791 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| HDFC Bank | FAIL | 95.8 | abstention | 35089/4529 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| ICICI Bank | PARTIAL | 119.2 | abstention | 58269/5624 | 16 | 6/5 | loan_to_deposit_ratio_2025_06_30; loan_to_deposit_ratio_2026_06_30 |
| Kotak Mahindra Bank | FAIL | 119.8 | abstention | 20859/4568 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| State Bank of India | PARTIAL | 121.3 | abstention | 30696/2420 | 14 | 4/3 | a discovery that survives counterevidence and semantic verification |
| Bajaj Finance | FAIL | 150.1 | abstention | 20139/3932 | 10 | 0/0 | verified issuer facts with complete metric, value, period, unit and scope bindings |
| BAJAJFINSV | NOT VERIFIED | — | Not finished | — | — | — | Pending live run |
| SHRIRAMFIN | NOT VERIFIED | — | Not finished | — | — | — | Pending live run |
| HDFCLIFE | NOT VERIFIED | — | Not finished | — | — | — | Pending live run |
| SBILIFE | NOT VERIFIED | — | Not finished | — | — | — | Pending live run |
| JIOFIN | NOT VERIFIED | — | Not finished | — | — | — | Pending live run |
| BSE | NOT VERIFIED | — | Not finished | — | — | — | Pending live run |

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
