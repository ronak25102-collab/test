from __future__ import annotations

from dataclasses import dataclass

from signal_research.domain.errors import BudgetExceeded


@dataclass
class Budget:
    max_search_calls: int
    max_fetch_documents: int
    max_model_calls: int
    max_ocr_pages: int
    search_calls: int = 0
    fetch_documents: int = 0
    model_calls: int = 0
    ocr_pages: int = 0

    def reserve(self, kind: str, amount: int = 1) -> None:
        current = getattr(self, kind)
        maximum = getattr(self, f"max_{kind}")
        if current + amount > maximum:
            raise BudgetExceeded(f"budget exceeded for {kind}")
        setattr(self, kind, current + amount)

    def snapshot(self) -> dict[str, int]:
        return {"search_calls": self.search_calls, "fetch_documents": self.fetch_documents, "model_calls": self.model_calls, "ocr_pages": self.ocr_pages}
