from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid5

from bs4 import BeautifulSoup

from signal_research.domain.schemas import Passage


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    passages: list[Passage]
    extraction_method: str
    blank_page_indexes: list[int] = field(default_factory=list)


def parse_html(document_id: UUID, raw: bytes) -> ParsedDocument:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled public document"
    blocks = []
    for element in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        value = re.sub(r"\s+", " ", element.get_text(" ", strip=True))
        if value:
            blocks.append(value)
    result = _chunk(document_id, title, blocks, "html")
    for table_index, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        headers = " | ".join(c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])) if rows else ""
        context = "\n".join(blocks[-6:])[:2000]
        for row_index, row in enumerate(rows[1:]):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
            if not cells:
                continue
            text = f"{context}\n{headers}\n{' | '.join(cells)}"
            result.passages.append(Passage(id=uuid5(document_id, f"table:{table_index}:{row_index}:{text}"), document_id=document_id, section=title, table_id=str(table_index), row_label=cells[0], column_label=headers, text=text, extraction_method="html_table"))
    return result


def parse_pdf(document_id: UUID, path: Path) -> ParsedDocument:
    from pypdf import PdfReader

    reader = PdfReader(path)
    # Annual reports can contain hundreds of pages. Exhaustive table detection on
    # every page is much slower than extracting text with its column positions.
    if len(reader.pages) > 80:
        from contextlib import ExitStack

        import pdfplumber

        passages, blank_pages = [], []
        with ExitStack() as resources:
            financial_pdf = None
            for page_index, page in enumerate(reader.pages):
                text = page.extract_text(extraction_mode="layout") or ""
                method = "pdf_layout"
                if _balance_page(text):
                    # Use glyph-aware text extraction only on balance pages. This
                    # recovers complete headers without detecting tables on all pages.
                    if financial_pdf is None:
                        financial_pdf = resources.enter_context(pdfplumber.open(path))
                    financial_page = financial_pdf.pages[page_index]
                    recover_rupee_glyphs(financial_page.chars)
                    text = financial_page.extract_text() or text
                    method = "pdf"
                # Keep column separation without letting blank padding split headers
                # from their rows or consume the model's input allowance.
                text = re.sub(r"[ \t]{3,}", "  ", text)
                if len(text.strip()) < 40:
                    blank_pages.append(page_index)
                parsed = _chunk(document_id, path.name, [line for line in text.splitlines() if line.strip()], method)
                for passage in parsed.passages:
                    passage.id = uuid5(document_id, f"layout:page:{page_index}:{passage.text}")
                    passage.page_index = page_index
                    passage.printed_page_label = str(page_index + 1)
                passages.extend(parsed.passages)
        return ParsedDocument(path.name, passages, "pdf_layout", blank_pages)
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required for PDF extraction") from exc
    passages = []
    blank_pages = []
    title = path.name
    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            recover_rupee_glyphs(page.chars)
            text = page.extract_text() or ""
            if len(text.strip()) < 40:
                blank_pages.append(page_index)
            if text.strip():
                parsed = _chunk(document_id, title, text.splitlines(), "pdf")
                for passage in parsed.passages:
                    passage.id = uuid5(document_id, f"page:{page_index}:{passage.text}")
                    passage.page_index = page_index
                    passage.printed_page_label = str(page_index + 1)
                passages.extend(parsed.passages)
            for table_index, table in enumerate(page.extract_tables()):
                if not table:
                    continue
                headers = " | ".join(str(c or "") for c in table[0])
                for row_index, row in enumerate(table[1:]):
                    cells = [str(c or "") for c in row]
                    row_text = f"{text[:1600]}\n{headers}\n{' | '.join(cells)}"
                    passages.append(Passage(id=uuid5(document_id, f"page:{page_index}:table:{table_index}:row:{row_index}"), document_id=document_id, page_index=page_index, printed_page_label=str(page_index + 1), table_id=f"{page_index}:{table_index}", row_label=cells[0], column_label=headers, text=row_text, extraction_method="pdf_table"))
    return ParsedDocument(title, passages, "pdf", blank_pages)


def _balance_page(text):
    rows = re.findall(r"(?im)^\s*(?:total\s+|gross\s+)?(?:advances|deposits|borrowings)\b[^\n]*\d", text)
    return len(rows) >= 2 and bool(re.search(r"\b(?:standalone|consolidated)\b", text, re.I))


def recover_rupee_glyphs(chars):
    """Recover font-encoded rupees without changing ordinary letters or punctuation."""
    for char in chars:
        font = char.get("fontname", "").split("+")[-1]
        if (font == "ITFRupee" and char.get("text") == "C") or (font in {"Rupee", "RupeeForadian"} and char.get("text") == "`"):
            char["text"] = "\u20b9"


def bounded_parse_pdf(document_id, path, timeout):
    """Contain CPU-heavy untrusted PDF parsing in a disposable process."""
    import json
    import subprocess
    import sys
    try:
        result = subprocess.run([sys.executable, "-m", "signal_research.retrieval.parse_worker", str(document_id), str(path.resolve())],
                                capture_output=True, timeout=timeout, check=True)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"PDF parsing exceeded its {timeout:g}-second limit") from None
    except subprocess.CalledProcessError:
        raise RuntimeError("PDF parser could not read this document") from None
    payload = json.loads(result.stdout)
    return ParsedDocument(payload["title"], [Passage.model_validate(p) for p in payload["passages"]], "pdf", payload.get("blank_page_indexes", []))


def parse_xbrl(document_id, raw):
    from signal_research.extraction.xbrl import parse_safe_xbrl
    facts = parse_safe_xbrl(raw)
    passages = []
    for i, fact in enumerate(facts):
        label = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", fact["concept"])
        text = "\n".join([f"{label}: {fact['value']}", *[f"{key}: {value}" for key, value in fact.items() if key not in {"concept", "value"}]])
        passages.append(Passage(id=uuid5(document_id, f"xbrl:{i}:{text}"), document_id=document_id, row_label=label, text=text, extraction_method="xbrl"))
    return ParsedDocument("XBRL disclosure", passages, "xbrl")


def _chunk(document_id: UUID, title: str, blocks: list[str], method: str) -> ParsedDocument:
    passages: list[Passage] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        if current and size + len(block) > 4500:
            text = "\n".join(current)
            passages.append(Passage(id=uuid5(document_id, f"{method}:{len(passages)}:{text}"), document_id=document_id, section=title, text=text, extraction_method=method, extraction_quality="good"))
            current, size = [], 0
        current.append(block)
        size += len(block)
    if current:
        passages.append(Passage(id=uuid5(document_id, f"{method}:{len(passages)}:{' '.join(current)}"), document_id=document_id, section=title, text="\n".join(current), extraction_method=method, extraction_quality="good"))
    return ParsedDocument(title, passages, method)
