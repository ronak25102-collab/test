from __future__ import annotations

from defusedxml import ElementTree


def parse_safe_xbrl(raw: bytes) -> list[dict[str, str]]:
    """Parse basic XBRL facts without resolving external entities."""
    root = ElementTree.fromstring(raw)
    facts = []
    for element in root.iter():
        if element.text and element.text.strip() and element.tag.rsplit("}", 1)[-1] not in {"context", "unit"}:
            facts.append({"concept": element.tag.rsplit("}", 1)[-1], "value": element.text.strip()})
    return facts
