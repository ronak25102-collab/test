# Actual live follow-up - 14 and 15 October 2026

Every row below uses actual local API/background-worker requests. Retained fact counts are automated pipeline outputs, not manually certified financial accuracy. Failed, partial and abstained runs do not establish a discovery.

The source fingerprint, cutoff, model settings, budget and run ID are retained in each private run manifest. Worker code stays fixed during each batch; later fixes are evaluated separately. These partial batches do not replace the historical full-roster matrix.

## Manual review findings

- The first BSE batch admitted an unrelated engineering-company report through an incidental "for BSE" phrase. Its retained figure is invalid as BSE evidence; current authorship checks reject the report.
- The second BSE batch used a mixed newspaper page. Revenue scale normalization was correct, but two profit figures belonged to another company advertisement. The new multiple-issuer-heading guard withholds the unisolated passage.
- A Bajaj Finance funding-cost duration used a comparison date as its start. Current validation requires one explicit reporting interval and rejects that binding.
- HDFC follow-up withdrew conflicting input facts while a hypothesis still referred to them. Current candidate checks withhold such candidates before further review.
- Old reports remain preserved as diagnostic evidence. Fixing code does not retroactively certify their contents.

## Issuer-bound diagnostic batch

Worker revision: `5f80f8d`. Private artifacts: `data/exports/issuer-bound-validation-2026-10-14`.

| Company | Terminal status | Runtime s | Outcome | Retained facts/calculations | Run ID |
|---|---|---:|---|---:|---|
| HDFCBANK | completed | 125.2 | insufficient_evidence | 12/10 | `fc603705-fee8-4bdf-a25e-36ef4b8111ce` |
| HDFCLIFE | failed | 147.1 | no report | 0/0 | `686a0a89-d8b4-4560-96d4-f7d2760b85e5` |
| BAJFINANCE | completed | 172.3 | insufficient_evidence | 0/0 | `c1698c47-e7bf-46dc-a756-8bac816e6b8f` |
| BSE | completed | 182.9 | insufficient_evidence | 1/0 | `9dacfaf0-78cc-4883-beb1-840a3e0f78b8` |
| ICICIGI | failed | 79.3 | no report | 0/0 | `b3a6596f-4093-4b59-a13f-3af548652fd7` |

## Shared-pipeline retest

Worker revision: `5b47410`. Private artifacts: `data/exports/completion-retest-2026-10-14`.

| Company | Terminal status | Runtime s | Outcome | Retained facts/calculations | Run ID |
|---|---|---:|---|---:|---|
| HDFCBANK | completed | 162.9 | insufficient_evidence | 10/6 | `b234136d-fc8b-4ab9-8e99-ac6d53504ef0` |
| HDFCLIFE | completed | 176.6 | insufficient_evidence | 0/0 | `d13cd93b-2d6c-4f5c-bc23-55a24077f639` |
| BAJFINANCE | completed | 176.8 | insufficient_evidence | 6/2 | `b40e7fea-77d0-4778-a75c-6239fd971552` |
| BSE | completed | 121.4 | insufficient_evidence | 4/2 | `c3ba1eeb-472e-4dc0-be40-43777f4b5a4f` |
| ICICIGI | completed | 124.8 | insufficient_evidence | 3/0 | `6d71dcb9-e699-4649-87ee-714a25b659d4` |

## 15 October strict-source validation

Worker revision: `07c0f64`. Private artifacts: `data/exports/completion-validation-2026-10-15`.

| Company | Terminal status | Runtime s | Outcome | Retained facts/calculations | Run ID |
|---|---|---:|---|---:|---|
| HDFCLIFE | completed | 178.6 | insufficient_evidence | 0/0 | `c1f4bca4-ff68-44fe-a6ac-8b30c656ea62` |
| BAJFINANCE | completed | 312.5 | partial | 7/5 | `58834db5-e09d-4378-9d36-37d837ee39c9` |
| BSE | completed | 133.5 | insufficient_evidence | 0/0 | `4717bae6-92ec-4061-b21e-48c63ae74598` |

## Configuration and interpretation

The Lightning batches use the configured `nvidia/nemotron-3.5-lightning-30b-a3b` for research and extraction. Temporary runtime overrides enforce verified included search allowance, a zero-dollar cap, 480 seconds, a 90-second model timeout, 14 searches and 18 fetches. The private `.env` is unchanged.

An authenticated Super access probe succeeded on 15 October. Any full temporary Super comparison is recorded separately with its own model and source fingerprint; it is not a pure model experiment if the software revision or retrieved sources differ. The original model and private rate card are preserved.

Source counts, checked arithmetic and software tests cannot establish source entailment, novelty, sustained historical development or a successful finals demo. A READY claim still requires an actual supported discovery and manual source/calculation review.
