from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Lease:
    owner: str
    fencing_token: int
    expires_at: datetime


def lease_is_current(lease: Lease, owner: str, fencing_token: int, now: datetime) -> bool:
    return lease.owner == owner and lease.fencing_token == fencing_token and lease.expires_at > now
