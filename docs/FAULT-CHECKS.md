# Fault and recovery verification

Updated 12 October 2026. No dummy data is silently substituted. These labels are
part of the results; mocked failures are not real provider outages.

| Scenario | Evidence and kind | Observed behavior |
|---|---|---|
| Missing credentials | Actual new frozen installation, isolated API/worker, `fresh-current.json` | Live request HTTP 503 with missing keys/card; synthetic replay works explicitly |
| Invalid credentials | Actual NVIDIA and Tavily requests with deliberately invalid QA token, `actual-auth-rejections.json` | Both HTTP 401; no real key or inference authorized |
| Tavily rate limit | Actual initial /usage HTTP 429 plus controlled regression | Run failed clearly; shared five-minute quota ledger prevents per-search usage calls |
| Free search quota exhausted | Controlled zero allowance and key-limit tests in `test_free_account.py` | Refuses search before sending; no billing/upgrade |
| NVIDIA quota/503 | Controlled adapter HTTP 429/503 tests | Actionable error, no blind NVIDIA retry or model fallback; actual exhaustion not deliberately induced |
| Provider timeout/lost stream | Controlled adapter and durable reservation tests | Partial JSON refused; uncertain allocation retained and request not resent |
| Empty search + inaccessible sources | Controlled full worker integration test | Honest abstention with no facts, no discovery and no model/dummy response |
| Malformed PDF | Controlled full worker using a corrupt PDF; actual matrix parse failures separately retained | Parser failure in limitations; honest abstention without synthetic substitution |
| PDF parse timeout | Controlled bounded parser test plus actual live large-report timeouts | Child process timeout handled separately from download timeout |
| Source SSL/unavailability | Actual real source failures; `native-tls.json` | Windows trust store fixes verified certificate access; full Jio fetch still timed out, no claim of universal fix |
| Queued cancellation | Actual API, `real-cancellation.json` | CANCELLED with zero provider work |
| In-flight cancellation | Actual ICICI request, `real-inflight-cancellation.json` | Cancelled while extracting, one model call in flight; CANCELLED in 4.138 seconds, six reviewed facts checkpointed |
| Expired evidence recovery | Actual retained ICICI evidence plus explicitly controlled shortening of the owned QA deadline | Resume completed PARTIAL with six facts, zero additional provider calls and no discovery; not a naturally occurring power outage |
| Restart/migration | Actual main service restart and preserved real Axis reports/exports, `restart-exports.json` | JSON, CSV and evidence ZIP HTTP 200 after migration 0003 |
| Publication recovery/fencing | Controlled lease/checkpoint tests in `test_recovery_and_universe.py` and `test_live.py` | Fenced worker stops; verified checkpoint persists without provider replay or extending deadline |
| Existing replay after fresh restart | Actual credential-free API/worker process, synthetic report | Report readable after restart; this is engineering validation, not live issuer quality |
| Private IP, redirect and oversized body | Controlled security tests | Public transport refuses unsafe destination or excessive source size |

Backend tests now include 320 passing cases, with one existing Starlette deprecation
warning. Actual HTTP/hash source checks do not validate every cited financial claim.
Tavily's conservative free ledger does not automatically refund uncertain usage or
accept a monthly replenishment; resolve that explicitly before a future demo.
NVIDIA remaining quota has no verified documented endpoint in this validation.

## 13 October: malformed URL crash

Actual HDFC run `cc4c461f-88db-4040-b039-bcafe750b628` failed while collecting
issuer identity, before any model call. A malformed website reference triggered
`ValueError: Invalid IPv6 URL` in Python URL parsing; the per-reference rejection
handler expected `UnsafeURL`. The shared URL validator now translates parse,
hostname and invalid-port errors into `UnsafeURL`. Official navigation and document
link discovery also skip malformed links before parsing their hosts.

74 targeted URL, disclosure, generality and fetch-security tests passed (one
existing Starlette deprecation warning), including bad links followed by usable
issuer links. Ruff and whitespace checks passed. These tests do not establish a
successful new live HDFC discovery. The original failed run remains unchanged;
start a new run with the restarted worker to use the correction.
