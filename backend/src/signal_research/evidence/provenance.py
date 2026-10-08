from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ProvenancePath:
    claim_id: UUID
    evidence_id: UUID
    document_id: UUID | None
    source_url: str | None
    locator: str | None


def source_locator(page_index: int | None, section: str | None, row_label: str | None = None) -> str:
    parts = []
    if page_index is not None:
        parts.append(f"page {page_index + 1}")
    if section:
        parts.append(section)
    if row_label:
        parts.append(f"row: {row_label}")
    return " · ".join(parts) or "passage locator unavailable"
