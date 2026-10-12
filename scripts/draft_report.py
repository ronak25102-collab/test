"""Create the LOCAL one-page Round 1 proposal draft; never submit it."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def main():
    output = Path('output/pdf/Beyond_TrackA_Round1_DRAFT.pdf')
    output.parent.mkdir(parents=True, exist_ok=True)
    body = ParagraphStyle('body', fontName='Helvetica', fontSize=10, leading=13.5,
                          textColor=colors.HexColor('#263747'), spaceAfter=7, alignment=TA_LEFT)
    heading = ParagraphStyle('heading', parent=body, fontName='Helvetica-Bold', fontSize=11,
                             textColor=colors.HexColor('#12656c'), spaceBefore=5, spaceAfter=4)
    title = ParagraphStyle('title', parent=body, fontName='Helvetica-Bold', fontSize=21, leading=25,
                           textColor=colors.HexColor('#162b40'), spaceAfter=5)
    small = ParagraphStyle('small', parent=body, fontSize=8.5, leading=11)
    story = [Paragraph('Beyond | Finding the Next Signal', title),
             Paragraph('ATMOS 2026 - Track A: Banking, NBFCs &amp; Financial Services', heading),
             Paragraph('Round 1 solution-report draft - 12 October 2026<br/>Team name pending confirmation; replace the project filename with the final team name before submission.', small),
             Spacer(1, 7)]
    sections = [
        ('Idea: investigate a relationship, not a headline',
         'Beyond investigates changes that conventional result summaries can miss: differences between business growth, asset quality, funding, distribution or segment economics. It separates a measured observation from a proposed mechanism, seeks historical context and tests the strongest alternative before publishing. A missing or contradictory evidence trail produces a clear abstention, never a fabricated finding or investment recommendation.'),
        ('One shared workflow for every issuer',
         'Resolve the company using official exchange identities and the current NIFTY 50 snapshot. Select questions and metrics by business type: banks, NBFCs, life insurers, exchanges and diversified financial groups. Search dynamically for issuer disclosures, exchange copies, independent analysis, regulatory context and peers. Fetch originals; bind each figure to its actual row, column, date, unit, segment and accounting scope. Derive registered calculations, propose hypotheses, then gather supporting and opposing evidence. Company names, aliases and websites are identity reference data; there are no company-specific findings, thresholds or research prompts.'),
        ('Prove, challenge and falsify',
         'Document hashes and source passages preserve lineage from claims to facts and reproducible arithmetic. Reposts and related issuer documents cannot manufacture source independence. Publication requires explicit financial periods, primary-source availability by the cutoff, independent relevant corroboration, multiple reporting periods, semantic claim review and all eight output elements. Counterarguments examine scope changes, acquisitions, reclassification, seasonality and sector effects. Each falsification rule states an observable condition, future observation window and expected source.'),
        ('Tools and output',
         'Python/FastAPI, a durable SQLite worker, registered financial calculations and a React/Vite dashboard form the local MVP. NVIDIA hosted prototype models provide research and extraction; Tavily finds public sources using included free credits. PDF, HTML and XBRL parsing plus confidence-gated local OCR retain source evidence. Hard time, token, request and source limits prevent unbounded runs; uncertain provider requests are not silently resubmitted. The dashboard shows one discovery sentence, 3-5 significance bullets, source links, timeline, necessary numbers, counterargument, falsification and evidence strength. Claim drawers expose passages and calculation inputs; JSON, CSV and evidence exports support review.'),
        ('Validation and plan to the finals',
         'The MVP runs locally. The final twelve-company live matrix, two unseen issuers, repeated runs and a sparse-data bank produced no verified discovery: ICICI and SBI retained checked facts and arithmetic; the others abstained. Engineering validation includes 320 backend tests, 14 browser tests and fresh installation. The current discovery-readiness verdict is NOT READY. Before 19 October, strengthen source coverage and temporal reasoning, inspect citations and recompute calculations, then finalise this report. From 20-24 October, repeat real validation, verify free quota and rehearse the transferable Windows setup. For 25 October, the target is eight minutes within the ten-minute presentation; fast abstention does not validate successful discovery.'),
    ]
    for label, text in sections:
        story.extend([Paragraph(label, heading), Paragraph(text, body)])
    def footer(canvas, doc):
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#687786'))
        canvas.drawString(38, 23, 'LOCAL DRAFT - not submitted or published - team review required')
        canvas.drawRightString(A4[0] - 38, 23, str(doc.page))
    SimpleDocTemplate(str(output), pagesize=A4, rightMargin=38, leftMargin=38,
                      topMargin=31, bottomMargin=36).build(story, onFirstPage=footer, onLaterPages=footer)
    from pypdf import PdfReader
    assert len(PdfReader(output).pages) <= 2, 'Brief allows two pages maximum'
    print(output.resolve())


if __name__ == '__main__':
    main()
