"""Isolated PDF parser; the parent enforces the wall-clock limit."""
import json
import sys
from pathlib import Path
from uuid import UUID

from .passages import parse_pdf

if __name__ == "__main__":
    result = parse_pdf(UUID(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps({"title": result.title, "passages": [p.model_dump(mode="json") for p in result.passages], "blank_page_indexes": result.blank_page_indexes}, ensure_ascii=True))
