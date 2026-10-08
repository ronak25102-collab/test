from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OCRBudget:
    max_pages: int
    used_pages: int = 0

    def select(self, page_indexes: list[int]) -> list[int]:
        return page_indexes[: max(0, self.max_pages - self.used_pages)]


def ocr_required(text: str | None, table_count: int = 0) -> bool:
    return (not text or len(text.strip()) < 40) and table_count > 0
