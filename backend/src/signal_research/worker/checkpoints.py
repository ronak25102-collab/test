from __future__ import annotations

import json
from hashlib import sha256


def input_hash(payload: object) -> str:
    return sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
