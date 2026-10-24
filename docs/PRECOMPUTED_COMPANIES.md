# Precomputed company research roster

As of 24 October 2026, the current official NSE constituent CSV contains 50 companies, including the 12 Financial Services constituents below. This is a research roster, not a claim that 12 publication-ready fixtures exist.

Membership was fetched directly from [NSE constituent CSV](https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv), HTTP 200. [NSE/FAOP/76591](https://nsearchives.nseindia.com/content/circulars/FAOP76591.pdf), dated 28 September 2026, confirms BSE replaced Wipro effective 30 September 2026. Actual fetched bytes and SHA-256 receipts are under `backend/src/signal_research/precomputed/research_sources/`.

| Company | NSE symbol | BSE code | Profile | IR domain | Aliases |
| --- | --- | --- | --- | --- | --- |
| Axis Bank Ltd. | AXISBANK | 532215 | bank | axis.bank.in | AXISBANK, Axis Bank Ltd., Axis Bank |
| BSE Ltd. | BSE | N/A (NSE only) | exchange | bseindia.com | BSE, BSE Ltd. |
| Bajaj Finance Ltd. | BAJFINANCE | 500034 | nbfc | aboutbajajfinserv.com | BAJFINANCE, Bajaj Finance Ltd., Bajaj Finance |
| Bajaj Finserv Ltd. | BAJAJFINSV | 532978 | diversified | aboutbajajfinserv.com | BAJAJFINSV, Bajaj Finserv Ltd., Bajaj Finserv |
| HDFC Bank Ltd. | HDFCBANK | 500180 | bank | hdfc.bank.in | HDFCBANK, HDFC Bank Ltd., HDFC Bank |
| HDFC Life Insurance Company Ltd. | HDFCLIFE | 540777 | life_insurer | hdfclife.com | HDFCLIFE, HDFC Life Insurance Company Ltd., HDFC Life Insurance Company |
| ICICI Bank Ltd. | ICICIBANK | 532174 | bank | icici.bank.in | ICICIBANK, ICICI Bank Ltd., ICICI Bank |
| Jio Financial Services Ltd. | JIOFIN | 543940 | diversified | jfs.in | JIOFIN, Jio Financial Services Ltd., Jio Financial Services |
| Kotak Mahindra Bank Ltd. | KOTAKBANK | 500247 | bank | kotak.bank.in | KOTAKBANK, Kotak Mahindra Bank Ltd., Kotak Mahindra Bank |
| SBI Life Insurance Company Ltd. | SBILIFE | 540719 | life_insurer | sbilife.co.in | SBILIFE, SBI Life Insurance Company Ltd., SBI Life Insurance Company |
| Shriram Finance Ltd. | SHRIRAMFIN | 511218 | nbfc | shriramfinance.in | SHRIRAMFIN, Shriram Finance Ltd., Shriram Finance |
| State Bank of India | SBIN | 500112 | bank | sbi.bank.in | SBIN, State Bank of India |

BSE Limited has no BSE equity scrip code: its equity is listed on NSE. The opened [SEBI-hosted BSE buyback filing](https://www.sebi.gov.in/sebi_data/commondocs/oct-2023/BSE_Limited_PBPA_p.pdf) explicitly identifies NSE as its only listing exchange. No value has been invented for this field.

Profiles follow the issuer businesses and existing registry categories; aliases shown are the exact symbol, CSV name and deterministic removal of the legal suffix. There are no asset-manager constituents in this official roster.

## Source identity checks

Scrip-code evidence filenames for each company are recorded in `roster.json`. The corresponding source bytes and HTTP receipts are retained locally. ICICI Q2 FY27 results have been released; SBI Q2 FY27 is scheduled for 3 November 2026 (future to this cutoff), so SBI latest reporting period is Q1 FY27. Bajaj Finance Q2 FY27 results were released 19 October 2026.

## Honest coverage gaps

The roster establishes membership only. Publication-ready reports additionally require verified historical metrics, matching peer facts, reviewed findings and current verifier/parity acceptance. Research-only YAML files retain exact shortfalls and never substitute another issuer report.
