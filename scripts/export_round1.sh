#!/usr/bin/env bash
set -euo pipefail
mkdir -p output
uv run python - <<'PY'
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

out = Path("output/TeamName_TrackA_Round1.pdf")
doc = SimpleDocTemplate(str(out), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
styles = getSampleStyleSheet()
story = [Paragraph("Track A — Autonomous Financial Research", styles["Title"]), Spacer(1, 12)]
for paragraph in Path("docs/round1-outline.md").read_text().splitlines():
    if paragraph.startswith("#"):
        story.append(Paragraph(paragraph.lstrip("# "), styles["Heading2"]))
    elif paragraph.strip():
        story.append(Paragraph(paragraph, styles["BodyText"]))
        story.append(Spacer(1, 6))
doc.build(story)
print(out)
PY
