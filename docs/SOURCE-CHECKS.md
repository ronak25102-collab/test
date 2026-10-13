# Human source and arithmetic checks

**13 October follow-up:** rendered HDFC annual pages 378/496 and Axis quarterly
page 7 were independently inspected for the new extraction retests. All eighteen
retained raw figures and fifteen reported calculations matched separately
transcribed source cells and Decimal arithmetic. See EXTRACTION-FIX-2026-10-13.md
and `data/exports/extraction-fix-2026-10-13/manual-HDFC-verified.json` /
`manual-AXIS-verified.json`. Both runs are partial evidence, not discoveries.

These checks are distinct from automated verification and model reviews. They do
not establish a discovery when a run abstains. Live artifacts remain under
`data/exports/finals-validation`; original reports are preserved for audit.

## HDFC pilot: 5a91ac4b-3fcd-4e31-9fbc-e52e7baa794f

Rendered and visually inspected PDF page 378 (printed page 358), standalone
balance sheet, in the issuer's [2025-26 integrated annual report](https://www.hdfc.bank.in/content/dam/hdfcbankpws/in/en/personal-banking/about-us/stakeholders-information/disclosures/other-stock-exchange-disclosure/2026/july/Final_IAR.pdf).
Confirmed comparative columns 31 March 2026 / 31 March 2025 and units INR thousand.

| Source row | 2026 raw | 2025 raw | Independent calculation |
|---|---:|---:|---|
| Deposits | 31,052,504,740 | 27,147,148,959 | Growth = (current/prior - 1) × 100 = 14.38587819% |
| Borrowings | 4,893,946,381 | 5,479,308,926 | Growth = (current/prior - 1) × 100 = -10.68314550% |
| Deposits scale | 31,052,504,740 thousand rupees | — | Divide by 10,000 = 3,105,250.474 INR crore |

Those calculations match retained values. However, another row is labelled only
**Advances**, while the pilot extraction called it **gross_advances**. The page
does not establish that definition. The pilot's gross-advance growth and loan/
deposit findings are NOT VERIFIED despite correct arithmetic. The shared validator
now requires an explicit gross advances/loans label; plain balance-sheet advances
cannot establish gross lending. No discovery was published in this run.

The unpublished hypothesis also invented a 108.1% previous ratio and a 13.5-point
decline. Registered arithmetic did not support them. Added earlier numerical
rejection and explicit prior-ratio calculations.

Five cited discovery sources cannot be audited for this pilot: it published no
discovery or claims. Successful discoveries need passage-level, date, definition,
independence and link checks before being counted as successful.

## Axis and SBI: first live matrix

Visually inspected retained official PDF pages, rather than trusting model review:
Axis audited results PDF page 8 and SBI analyst presentation PDF/printed page 46.
Rendered images and independent Decimal arithmetic are retained in
`data/exports/finals-validation` (`manual-bank-arithmetic.json`).

| Issuer | Scope and dates | Figure comparison, INR crore | Recomputed growth |
|---|---|---|---:|
| Axis | Consolidated; 31 March 2026 / 2025 | Deposits 1,333,791.44 / 1,170,920.89 | 13.90961178% |
| Axis | Same columns | Borrowings 280,510.62 / 220,686.75 | 27.10804795% |
| SBI | SOLO (standalone); June 2026 / 2025 comparative month-end columns | Deposits 6,005,805 / 5,473,254 | 9.73006186% |
| SBI | Same columns | Borrowings 768,854 / 537,749 | 42.97637002% |

All four reproduce retained calculations. Each report contains only two
calculations, so a third reported calculation per company is **NOT VERIFIED**.
SBI's page explicitly labels net advances: it cannot support gross advances.
Neither run published a discovery; these are accurate retained observations,
not proof of novelty, causal significance or independent corroboration.


## ICICI and HDFC: later live comparative disclosures

Visually inspected `ICICI-balance.png` (official Q1 FY2027 results PDF page 10)
and `HDFC-2024-balance.png` (official 2023-24 integrated annual report PDF page 412,
printed page 416). Independent arithmetic is saved in
`manual-comparative-arithmetic.json`; these are checks of retained observations,
not published discoveries.

| Issuer / consolidated INR crore | Metric | Current / prior | Recomputed YoY |
|---|---|---|---:|
| ICICI, June 2026 / 2025 | Deposits | 1,870,362.74 / 1,641,136.66 | 13.96751932% |
| Same | Borrowings | 226,317.72 / 215,148.97 | 5.19117056% |
| Same | Advances as reported | 1,729,327.48 / 1,445,593.02 | 19.62754773% |
| HDFC, March 2024 / 2023 | Deposits | 2,376,887.28 / 1,882,663.25 | 26.25132402% |
| Same | Borrowings | 730,615.46 / 256,548.66 | 184.78630915% |
| Same | Advances as reported | 2,565,891.41 / 1,661,949.29 | 54.39047542% |

ICICI's middle column is March 2026 and must not be assigned the June values.
HDFC's arithmetic spans the HDFC merger and a changed consolidated business
boundary. It does **not** establish organic growth or comparable continuing
operations. Any inference requires the merger and accounting notes. Plain advances
are not gross advances and cannot establish a gross-loan/deposit ratio.

There is no successful discovery here to validate against five cited sources.
For companies without reported calculations, three reported-number checks remain
**NOT VERIFIED**; invented example calculations are not a substitute.


## Final Super/Super ICICI run

Run `6a2b9c94-9bde-4a85-9a9d-5145dfcaa11f` retained exactly the six consolidated
June 2026/2025 source figures checked above. All five reported calculations match
independent Decimal arithmetic: deposits +13.96751932%, borrowings +5.19117056%,
advances as reported +19.62754773%, borrowing-versus-deposit growth gap
-8.77634875 percentage points, and advances-versus-deposit gap +5.66002841 points.
The raw-cell comparison and calculation IDs are saved in `manual-final-ICICI.json`.
Neither hypothesis survived relevant independent corroboration. Correct calculations
do not establish a non-obvious discovery or its mechanism.

The first matrix's source-link check retrieved 79 source prefixes: 76 HTTP 200,
two network errors and one non-200 response. All retained hashes matched. This is
**automated HTTP/hash validation**, not human checking of five cited claims per
issuer. The final matrix has its own independent check artifact; do not transfer
the first matrix's counts onto it.


## Final SBI run: three reported calculations

Run `1d53bbec-c9f9-44ef-b0bf-80578f7a909a` used the official
[Q3 FY26 analyst presentation](https://sbi.bank.in/documents/17826/57445696/824.pdf/b38eccf4-faae-0a76-35d2-dc1dbcb7ea54?t=1770623478633).
Visually checked PDF page 56 / printed page 55, **SBI SOLO** columns in INR crore,
December 2025 / 2024: deposits 5,701,309 / 5,229,384; borrowings 635,707 / 709,135.
Independent arithmetic reproduced deposit growth +9.02448548%, borrowing growth
-10.35458693%, and the borrowing-versus-deposit gap -19.37907241 percentage points.
All three reported calculations match. The adjacent GROUP columns are different
and were not used. The assets table says **Net Advances**, which cannot establish
gross advances. This retained observation is older than the latest available
quarter; it is not a verified current discovery. Render and arithmetic record:
`SBIN-final-balance.png`, `manual-final-SBI.json`.

## Final source accessibility checks

The final independent check selected five retained sources per clean roster,
unseen, repeat and sparse run: **85 checks across 17 runs**. Actual HTTP prefix
retrieval returned 75 HTTP 200, five HTTP 406 and five network timeouts. All 85
retained content hashes matched. BSE-hosted documents account for all five HTTP
406 responses; BSE, NSE and SBI sources also timed out. These failures mean live
links are not universally reliable even when retained evidence remains intact.
The artifact `final-source-link-checks.json` identifies exact URLs and timestamps.

This is automated link/hash verification, not human verification of five claimed
passages per company. No final discovery exists to pass that semantic requirement.

Jio's official Q3 FY2026 report was also visually inspected, PDF page 4: the table
declares consolidated INR crore, quarter and nine months ended 31 December 2025.
Its native text corrupts the rupee glyph and mixes some table/header spans. The
clean live run retained zero verified facts. Hyphenated dates and the explicit
compound durations were subsequently fixed in shared rules and tested; currency
and table recovery remain unresolved. No example Jio arithmetic is represented
as a reproduced reported calculation.
