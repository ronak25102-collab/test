"""Read-only quota checks. Never modify a subscription or enable overage billing."""
import hashlib
import sqlite3
import time
from time import sleep

import httpx


class FreeQuotaUnavailable(RuntimeError):
    code = "FREE_QUOTA_UNAVAILABLE"


def remaining_free_credits(payload):
    account, key = payload.get("account", {}), payload.get("key", {})
    if account.get("current_plan", "").lower() not in {"researcher", "free"}:
        raise FreeQuotaUnavailable("Tavily account is not a verified free Researcher plan; no search was sent")
    limit, usage = account.get("plan_limit"), account.get("plan_usage")
    if type(limit) is not int or type(usage) is not int or limit < 0 or usage < 0:
        raise FreeQuotaUnavailable("Tavily free quota could not be verified; no search was sent")
    remaining = max(0, limit - usage)
    if key.get("limit") is not None:
        if type(key["limit"]) is not int or type(key.get("usage")) is not int:
            raise FreeQuotaUnavailable("Tavily API-key allowance could not be verified")
        remaining = min(remaining, max(0, key["limit"] - key["usage"]))
    return remaining


def free_account_usage(settings, reserve=0):
    # A shared SQLite ledger avoids exceeding /usage's 10 requests/10min limit.
    # Reservations survive uncertain searches; they never increase free allowance.
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(settings.tavily_api_key.encode()).hexdigest()
    with sqlite3.connect(settings.data_dir / 'free-quota.db', timeout=20) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS quota (key TEXT PRIMARY KEY, remaining INTEGER, verified REAL)')
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT remaining, verified FROM quota WHERE key=?', (key,)).fetchone()
        if row and time.time() - row[1] < 300:
            remaining = row[0]
        else:
            remaining = fetch_free_account_usage(settings)
            if row:
                # Provider usage can lag a successful/uncertain request. A refresh
                # must never refund our durable reservations. This deliberately
                # remains conservative across account replenishment as well.
                remaining = min(remaining, row[0])
            connection.execute('INSERT OR REPLACE INTO quota VALUES (?, ?, ?)', (key, remaining, time.time()))
        if remaining < reserve:
            raise FreeQuotaUnavailable('Tavily free allowance is exhausted; paid overage will not be used')
        if reserve:
            connection.execute('UPDATE quota SET remaining=? WHERE key=?', (remaining - reserve, key))
        return remaining


def fetch_free_account_usage(settings):
    from signal_research.precomputed.guard import require_network_allowed
    require_network_allowed()
    for attempt in range(2):
        try:
            response = httpx.get("https://api.tavily.com/usage", headers={"Authorization": "Bearer " + settings.tavily_api_key},
                                 timeout=min(15, settings.source_request_timeout_seconds), follow_redirects=False)
            response.raise_for_status()
            return remaining_free_credits(response.json())
        except FreeQuotaUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError, AttributeError, KeyError) as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
            if attempt == 0 and (isinstance(exc, httpx.RequestError) or status in {500, 502, 503, 504}):
                sleep(1)
                continue
            raise FreeQuotaUnavailable(f"Tavily account/quota check failed ({status}); no search was sent") from None
