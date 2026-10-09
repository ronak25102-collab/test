from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OCRBudget:
    max_pages: int
    used_pages: int = 0

    def select(self, page_indexes: list[int]) -> list[int]:
        return page_indexes[: max(0, self.max_pages - self.used_pages)]


def ocr_required(text: str | None, table_count: int = 0) -> bool:
    return not text or len(text.strip()) < 40


def ocr_page(path, page_index, data_dir, timeout, pdftoppm_path="pdftoppm", tesseract_path="tesseract"):
    import csv
    import io
    import shutil
    import subprocess
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from time import monotonic

    renderer = shutil.which(pdftoppm_path)
    recognizer = shutil.which(tesseract_path)
    if not renderer or not recognizer:
        raise RuntimeError("OCR requires pdftoppm and tesseract (included in the backend Docker image)")
    deadline = monotonic() + timeout
    (data_dir / "parsed").mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=data_dir / "parsed") as directory:
        prefix = Path(directory) / "page"
        subprocess.run([renderer, "-f", str(page_index + 1), "-l", str(page_index + 1), "-singlefile", "-r", "180", "-png", str(path), str(prefix)], check=True, capture_output=True, timeout=max(.1, deadline - monotonic()))
        result = subprocess.run([recognizer, str(prefix.with_suffix(".png")), "stdout", "tsv"], check=True, capture_output=True, timeout=max(.1, deadline - monotonic()))
        rows = list(csv.DictReader(io.StringIO(result.stdout.decode("utf-8", errors="replace")), delimiter="\t"))
        tokens = [r for r in rows if r.get("text", "").strip()]
        if any(any(c.isdigit() for c in r["text"]) and float(r.get("conf", "-1")) < 95 for r in tokens):
            raise RuntimeError("OCR numeric confidence is too low; the page was withheld")
        return " ".join(r["text"] for r in tokens)
