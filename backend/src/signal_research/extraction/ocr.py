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


class LowNumericConfidence(RuntimeError):
    """Financial numbers remain withheld; clear cover lettering may identify the issuer."""
    def __init__(self, identity_text):
        super().__init__('OCR numeric confidence is too low; the page was withheld')
        self.identity_text = identity_text


def ocr_page(path, page_index, data_dir, timeout, pdftoppm_path="pdftoppm", tesseract_path="tesseract"):
    import csv
    import importlib.util
    import io
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    from tempfile import TemporaryDirectory
    from time import monotonic

    renderer = shutil.which(pdftoppm_path)
    recognizer = shutil.which(tesseract_path)
    packaged = importlib.util.find_spec("tesserocr") and (data_dir / "tessdata" / "eng.traineddata").exists()
    if not recognizer and not packaged:
        raise RuntimeError("OCR requires Tesseract; configure TESSERACT_PATH or install it")
    deadline = monotonic() + timeout
    (data_dir / "parsed").mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=data_dir / "parsed") as directory:
        prefix = Path(directory) / "page"
        command = ([renderer, "-f", str(page_index + 1), "-l", str(page_index + 1), "-singlefile", "-r", "180", "-png", str(path), str(prefix)] if renderer else
                   [sys.executable, "-m", "signal_research.extraction.render_worker", str(path), str(page_index), str(prefix.with_suffix(".png"))])
        subprocess.run(command, check=True, capture_output=True, timeout=max(.1, deadline - monotonic()))
        command = ([recognizer, str(prefix.with_suffix(".png")), "stdout", "tsv"] if recognizer else
                   [sys.executable, "-m", "signal_research.extraction.tesseract_worker", str(prefix.with_suffix(".png")), str(data_dir / "tessdata")])
        result = subprocess.run(command, check=True, capture_output=True, timeout=max(.1, deadline - monotonic()))
        rows = list(csv.DictReader(io.StringIO(result.stdout.decode("utf-8", errors="replace")), delimiter="\t"))
        tokens = [r for r in rows if r.get("text", "").strip()]
        if any(any(c.isdigit() for c in r["text"]) and float(r.get("conf", "-1")) < 95 for r in tokens):
            identity_lines = {}
            for row in tokens:
                # Never rescue a damaged number, currency, publication date or
                # financial measurement through the identity-only path.
                if any(c.isdigit() for c in row['text']) or float(row.get('conf', '-1')) < 90:
                    continue
                key = tuple(row.get(field) for field in ('block_num', 'par_num', 'line_num'))
                identity_lines.setdefault(key, []).append(row['text'])
            raise LowNumericConfidence('\n'.join(' '.join(words) for words in identity_lines.values()))
        # Preserve row boundaries; flattening the page destroys table bindings.
        lines = {}
        for row in tokens:
            key = tuple(row.get(field) for field in ("block_num", "par_num", "line_num"))
            lines.setdefault(key, []).append(row["text"])
        return "\n".join(" ".join(words) for words in lines.values())
