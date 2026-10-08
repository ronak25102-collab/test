from __future__ import annotations

from bs4 import BeautifulSoup


def html_table_rows(raw: bytes) -> list[dict[str, str]]:
    """Extract rows while retaining the table header in every row context."""
    soup = BeautifulSoup(raw, "html.parser")
    rows: list[dict[str, str]] = []
    for table_index, table in enumerate(soup.find_all("table")):
        headers = [cell.get_text(" ", strip=True) for cell in table.find_all("th")]
        for row in table.find_all("tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"])]
            if not cells or cells == headers:
                continue
            rows.append({"table_id": str(table_index), "headers": " | ".join(headers), "cells": " | ".join(cells)})
    return rows
