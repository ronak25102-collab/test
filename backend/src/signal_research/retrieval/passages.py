from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from bs4 import BeautifulSoup

from signal_research.domain.schemas import Passage


@dataclass(frozen=True)
class ParsedDocument:
    title: str
    passages: list[Passage]
    extraction_method: str


def parse_html(document_id: UUID, raw: bytes) -> ParsedDocument:
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled public document"
    blocks = []
    for element in soup.find_all(["h1", "h2", "h3", "p", "li", "td", "th"]):
        value = re.sub(r"\s+", " ", element.get_text(" ", strip=True))
        if value:
            blocks.append(value)
    return _chunk(document_id, title, blocks, "html")


def parse_pdf(document_id: UUID, path: Path) -> ParsedDocument:
    try:
        import pdfplumber
    except ImportError as exc:
        raise RuntimeError("pdfplumber is required for PDF extraction") from exc
    blocks: list[str] = []
    title = path.name
    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if text.strip():
                blocks.append(f"[page {page_index + 1}] {text}")
    return _chunk(document_id, title, blocks, "pdf")


def _chunk(document_id: UUID, title: str, blocks: list[str], method: str) -> ParsedDocument:
    passages: list[Passage] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        if current and size + len(block) > 4500:
            text = "\n".join(current)
            passages.append(Passage(id=uuid4(), document_id=document_id, section=title, text=text, extraction_method=method, extraction_quality="good"))
            current, size = [], 0
        current.append(block)
        size += len(block)
    if current:
        passages.append(Passage(id=uuid4(), document_id=document_id, section=title, text="\n".join(current), extraction_method=method, extraction_quality="good"))
    return ParsedDocument(title, passages, method)
