from __future__ import annotations

from defusedxml import ElementTree


def parse_safe_xbrl(raw: bytes) -> list[dict[str, str]]:
    """Parse basic XBRL facts without resolving external entities."""
    root = ElementTree.fromstring(raw)
    contexts, units = {}, {}
    def label(tag):
        return tag.rsplit("}", 1)[-1]
    for element in root.iter():
        if label(element.tag) == "context":
            contexts[element.get("id")] = {label(child.tag): child.text.strip() for child in element.iter() if child.text and child.text.strip() and label(child.tag) in {"identifier", "instant", "startDate", "endDate", "explicitMember"}}
        elif label(element.tag) == "unit":
            units[element.get("id")] = " / ".join(child.text.strip() for child in element.iter() if child.text and child.text.strip() and label(child.tag) == "measure")
    facts = []
    for element in root.iter():
        if element.get("contextRef") and element.text and element.text.strip():
            context = contexts.get(element.get("contextRef"), {})
            unit = units.get(element.get("unitRef"), "unknown")
            if unit.lower().endswith(":inr"):
                unit = "INR rupees"
            dimensions = context.get("explicitMember", "")
            facts.append({"concept": label(element.tag), "value": element.text.strip(), "context_id": element.get("contextRef"),
                          "entity_identifier": context.get("identifier", "unknown"), "unit": unit,
                          "period_start": context.get("startDate", ""), "period_end": context.get("instant", context.get("endDate", "")),
                          "dimensions": dimensions.replace("ConsolidatedMember", "Consolidated Member").replace("StandaloneMember", "Standalone Member"), "decimals": element.get("decimals", "unknown")})
    return facts
