"""Portable evidence report: inline assets, embedded passages, public source links only."""
import ipaddress
import json
from html import escape
from urllib.parse import urlparse

from signal_research.domain.schemas import SourceDocument
from signal_research.research.history import comparable_series
from signal_research.research.story import timeline_story
from signal_research.retrieval.quality import format_prose, indian_number

CSS = '''*{box-sizing:border-box}body{margin:0;background:#f4f1e7;color:#183c2e;font:16px/1.6 system-ui,sans-serif}main{max-width:1080px;margin:auto;padding:48px 28px}header{padding:30px 0;border-bottom:2px solid #34583f}h1{font-size:36px;line-height:1.18;max-width:28ch}h2{font-size:25px;margin:0 0 18px}section{padding:30px 0;border-bottom:1px solid #ccd2bf}button,.badge{background:#214b37;color:#fff;border:0;border-radius:8px;padding:10px 16px;cursor:pointer}a{color:#315c40;overflow-wrap:anywhere}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #d8ddcd}blockquote{white-space:pre-wrap;border-left:3px solid #8ca373;padding:14px;max-height:45vh;overflow:auto;background:#f7f7f0}dialog{max-width:900px;width:90%;max-height:90vh;border:1px solid #b6c1a8;border-radius:14px;padding:25px}dialog::backdrop{background:#17392dbb}details{margin:12px 0}summary{cursor:pointer}small{color:#647258}.timeline{border-left:2px solid #8ca373;padding-left:25px}.timeline article{margin-bottom:20px}svg{max-width:100%;height:auto}.tools{display:flex;gap:12px;flex-wrap:wrap}.peer{background:#e7eddf;padding:16px}@media print{@page{size:A4;margin:16mm}body{background:white;font-size:11px}main{padding:0}button,.tools,dialog{display:none}h1{font-size:25px}section{break-inside:avoid}details{display:block}blockquote{max-height:none;overflow:visible}a:after{content:" (" attr(href) ")";font-size:9px}svg{max-height:220px}}'''


def public_url(url):
    parsed = urlparse(str(url))
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        return None
    host = parsed.hostname.lower().rstrip('.')
    if host in {'localhost', 'localhost.localdomain'} or host.endswith('.localhost'):
        return None
    try:
        if not ipaddress.ip_address(host).is_global:
            return None
    except ValueError:
        pass
    return str(url)


def source_link(document):
    url = public_url(document.canonical_url)
    return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">{escape(document.title)}</a>' if url else escape(document.title)


def report_html(report):
    facts, passages, docs = {f.id: f for f in report.facts}, {p.id: p for p in report.passages}, {d.id: d for d in report.documents}
    discovery = report.discoveries[0] if report.discoveries else None
    meta = report.generation_metadata
    def text(value):
        return escape(format_prose(str(value)))
    def lineage(claim):
        pieces = [f'<p>{text(claim.text)}</p>']
        for identifier in claim.calculation_ids:
            c = next(c for c in report.calculations if c.id == identifier)
            pieces.append(f'<p>Calculation {text(c.formula_id)}: {indian_number(c.output_value)} {text(c.unit)} · ID {c.id}</p>')
        bound_ids = {link.passage_or_fact_id for link in claim.evidence_links}
        bound_ids.update(i for c in report.calculations if c.id in claim.calculation_ids for i in c.input_fact_ids)
        bound = [facts.get(i) for i in bound_ids]
        ids = {link.passage_or_fact_id for link in claim.evidence_links if link.passage_or_fact_id in passages}
        for f in bound:
            if f:
                ids.add(f.passage_id)
                pieces.append(f'<p>Fact {f.id}: {text(f.metric_key)} · {indian_number(f.value_decimal)} {text(f.unit_normalized)} · {f.period_end} · {text(f.scope)}</p>')
        for pid in ids:
            p = passages[pid]
            pieces.append(f'<p>{source_link(docs[p.document_id])} · page {(p.page_index + 1) if p.page_index is not None else "unpaginated"}</p><small>Verbatim original passage · {p.id}</small><blockquote>{escape(p.text)}</blockquote>')
        return ''.join(pieces)
    headline = discovery.discovery_sentence if discovery else meta.get('best_candidate', {}).get('text', 'No discovery established from the verified evidence.')
    mode_label = 'SYNTHETIC REPLAY' if report.source_coverage.get('synthetic') else str(report.source_coverage.get('mode', 'mode unrecorded')).upper()
    body = [f'<header><small>BEYOND / {text(mode_label)} · CUTOFF {report.cutoff}</small><h1>{text(headline)}</h1><span class="badge">{discovery.evidence_strength.value if discovery else "Not established"}</span><p>{text(report.company.legal_name)}</p><div class="tools"><button id="print">Print / Save as PDF</button><small>Portable report · source passages embedded · no server required</small></div>']
    trace = meta.get('strength_trace', {})
    body.append('<details><summary>Evidence strength rule trace</summary><ul>' + ''.join(f'<li>{"✓" if v else "○"} {text(k.replace("_", " "))}</li>' for k, v in trace.get('rules', {}).items()) + '</ul>' + ''.join(f'<p>{text(c)}</p>' for c in trace.get('caps', [])) + '</details>')
    if meta.get('headline'):
        body.append('<details><summary>Technical detail</summary><p>' + text(meta['headline']['technical_detail']) + '</p></details>')
    body.append('</header><section><h2>Why it matters</h2><ul>')
    if discovery:
        body.extend(f'<li><button data-open="{w.claim_id}">{text(w.text)}</button></li>' for w in discovery.why_it_matters)
    else:
        body.append('<li>Not established; inspect the missing evidence and retained observations.</li>')
    body.append('</ul></section><section><h2>Key numbers and peer comparison</h2>')
    series = report.source_coverage.get('historical_series') or comparable_series(report.facts)
    if series:
        selected_series = max(series, key=lambda s: s['comparable_periods'])
        observations = selected_series['observations']
        body.append('<p>' + text(selected_series['metric'].replace('_', ' ')) + ' · ' + text(selected_series['scope']) + ' · ' + text(selected_series['unit'].replace('_', ' ')) + ' · verified observations</p>')
        values = [float(o['value']) for o in observations]
        low, high = min(values), max(values)
        points = ' '.join(f'{35 + i * 730 / max(1, len(values) - 1):.2f},{180 - (v - low) / (high - low or 1) * 130:.2f}' for i, v in enumerate(values))
        body.append(f'<svg viewBox="0 0 800 240" role="img" aria-label="Verified historical series"><polyline fill="none" stroke="#315b3e" stroke-width="3" points="{points}"/>')
        for index, o in enumerate(observations):
            x = 35 + index * 730 / max(1, len(values) - 1)
            anchor = 'start' if index == 0 else 'end' if index == len(observations) - 1 else 'middle'
            body.append(f'<text x="{x:.2f}" y="220" text-anchor="{anchor}" font-size="10">{text(o["period_end"])}</text>')
            if any(b['end'] == str(o['period_end']) for b in meta.get('structural_breaks', [])):
                body.append(f'<line x1="{x}" x2="{x}" y1="30" y2="190" stroke="#ae7645" stroke-dasharray="4 4"/><text x="{x}" y="22" font-size="12">Break flagged</text>')
        body.append('</svg>')
    peers = meta.get('peer_benchmark', {})
    body.append('<p>Peer comparison: ' + text(peers.get('status', 'inconclusive')) + '</p><table><tr><th>Metric / period / scope</th><th>Company</th><th>Peer median</th><th>Gap</th><th>Verdict</th></tr>')
    for r in peers.get('comparisons', []):
        body.append(f'<tr><td>{text(r["metric"])} / {r["period_end"]} / {text(r["scope"])}</td><td>{indian_number(r["company_value"])}</td><td>{indian_number(r["peer_median"])}</td><td>{indian_number(r["gap"])} percentage points</td><td>{text(r["classification"])}</td></tr>')
    body.append('</table>')
    comparisons = peers.get('comparisons', [])
    if comparisons:
        first = comparisons[0]
        rows = sorted([r for r in comparisons if (r['metric'], r['scope'], r['comparison']) ==
                       (first['metric'], first['scope'], first['comparison'])], key=lambda r: r['period_end'])
        values = [float(r[k]) for r in rows for k in ('company_value', 'peer_median')]
        low, high = min(*values, 0), max(*values, 1)
        body.append('<svg viewBox="0 0 800 220" role="img" aria-label="Company and verified peer median overlay">')
        for key, color in [('company_value', '#315b3e'), ('peer_median', '#a77a43')]:
            points = [(40 + i * 700 / max(1, len(rows) - 1), 170 - (float(r[key]) - low) / (high - low or 1) * 130) for i, r in enumerate(rows)]
            body.append('<polyline fill="none" stroke="' + color + '" stroke-width="3" points="' + ' '.join(f'{x:.2f},{y:.2f}' for x, y in points) + '"/>')
            body.extend(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="{color}"/>' for x, y in points)
        for i, row in enumerate(rows):
            anchor = 'start' if i == 0 else 'end' if i == len(rows) - 1 else 'middle'
            body.append(f'<text x="{40 + i * 700 / max(1, len(rows) - 1):.2f}" y="205" text-anchor="{anchor}" font-size="12">{row["period_end"]}</text>')
        body.append('</svg><p>Green: company · Gold: verified peer median · ' + text(first['metric']) + ' (%) · ' + text(first['scope']) + '</p>')
    body.append('<details id="peer-evidence"><summary>Peer inputs and exact source passages</summary>')
    for bundle in peers.get('sources', []):
        peer_passages = {p['id']: p for p in bundle['passages']}
        peer_docs = {d['id']: SourceDocument.model_validate(d) for d in bundle['documents']}
        body.append('<h3>' + text(bundle['company']['legal_name']) + '</h3>')
        for fact in bundle['facts']:
            passage = peer_passages.get(fact['passage_id'])
            document = peer_docs.get(passage['document_id']) if passage else None
            body.append('<details><summary>' + text(fact['metric_key']) + ': ' + indian_number(fact['value_decimal']) + ' · ' + text(fact['period_end']) + ' · ' + text(fact['scope']) + '</summary>')
            if passage and document:
                body.append(f'<p>Fact ID {text(fact["id"])} · {source_link(document)}</p><blockquote>{escape(passage["text"])}</blockquote>')
            body.append('</details>')
    body.append('</details></section><section><h2>Timeline and onset</h2><div class="timeline">')
    story = meta.get('timeline_story') or timeline_story(report.facts, report.calculations, report.passages, report.documents, meta.get('structural_breaks', []))
    for o in story.get('onsets', []):
        estimate = o.get('estimate')
        label = (estimate['date'] + ' · ' + estimate['confidence'] + ' · ' + estimate['reason']) if estimate else 'Needed: ' + ' '.join(o['missing'])
        body.append('<p>' + text(o['metric']) + ': ' + text(label) + '</p>')
    for e in story.get('events', []):
        body.append(f'<article><time>{e["date"]}</time><strong> {text(e["what_changed"])}</strong><p>{indian_number(e["value"])} {text(e["unit"])} · {text(e["why_it_matters"])}</p><details><summary>Exact source passage</summary><blockquote>{escape(next((p.text for p in report.passages if str(p.id) == e["passage_id"]), "Unavailable"))}</blockquote></details></article>')
    for b in meta.get('structural_breaks', []):
        body.append(f'<article><strong>{b["end"]} · Structural break · {text(b["metric"])}</strong><p>{text(b["reason"])}</p></article>')
        for pid in b.get('passage_ids', []):
            passage = next((p for p in report.passages if str(p.id) == pid), None)
            if passage:
                body.append('<details><summary>Event source passage</summary>' + source_link(docs[passage.document_id]) + '<blockquote>' + escape(passage.text) + '</blockquote></details>')
    body.append('</div></section><section id="evidence"><h2>Evidence trail</h2>')
    for claim in report.claims:
        body.append(f'<details id="evidence-{claim.id}"><summary>{text(claim.text)}</summary>{lineage(claim)}</details><dialog id="claim-{claim.id}"><button data-close>Close</button>{lineage(claim)}</dialog>')
    body.append('</section><section><h2>Counterargument</h2><p>' + text(discovery.counterargument.statement if discovery else 'No discovery-level counterargument was verified.') + '</p></section><section><h2>Falsification</h2>')
    for condition in meta.get('falsification_tests', {}).get('conditions', []):
        body.append(f'<article><strong>{text(condition["kind"])}</strong><p>{text(condition["metric"])} {text(condition["operator"])} {text(condition["threshold"])} {text(condition["unit"])}</p><p>Window {text(condition.get("window"))} · expected disclosure {text(condition.get("expected_disclosure_date") or "Unknown")}</p><p>Checkable now: {condition["checkable_now"]} · {text(condition["status"])}</p><p>{text(condition.get("reason") or condition.get("interpretation", ""))}</p></article>')
        for pid in condition.get('passage_ids', []):
            passage = next((p for p in report.passages if str(p.id) == pid), None)
            if passage:
                body.append('<details><summary>Checked original passage</summary>' + source_link(docs[passage.document_id]) + '<blockquote>' + escape(passage.text) + '</blockquote></details>')
    if discovery and not meta.get('falsification_tests'):
        body.extend(f'<p>{text(rule.interpretation)}</p><small>Expected source: {text(rule.expected_source_type)}</small>' for rule in discovery.falsification_rules)
    body.append('</section><section><h2>Limitations</h2><ul>' + ''.join(f'<li>{text(l)}</li>' for l in report.limitations) + '</ul></section><section id="original-sources"><h2>Original sources and embedded passages</h2>')
    for d in report.documents:
        body.append(f'<details><summary>{source_link(d)} · {text(d.document_type)} · published {text(d.published_at.date() if d.published_at else "unknown")}</summary>' + ''.join(f'<blockquote>{escape(p.text)}</blockquote>' for p in report.passages if p.document_id == d.id) + '</details>')
    body.append('</section>')
    # Only portable presentation fields; private object paths and service URLs are excluded.
    data = {'run_id': str(report.run_id), 'company': report.company.legal_name, 'cutoff': str(report.cutoff),
            'facts': [{k: v for k, v in f.model_dump(mode='json').items() if k != 'local_object_key'} for f in report.facts]}
    embedded = json.dumps(data).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    js = "document.getElementById('print').onclick=()=>window.print();document.querySelectorAll('[data-open]').forEach(b=>b.onclick=()=>document.getElementById('claim-'+b.dataset.open)?.showModal());document.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());let opened=[];addEventListener('beforeprint',()=>{opened=[...document.querySelectorAll('main details:not([open])')];opened.forEach(d=>d.open=true)});addEventListener('afterprint',()=>{opened.forEach(d=>d.open=false)});"
    print_css = '@media print{body{line-height:1.45}header h1{max-width:none;font-size:23px}section{padding:18px 0;break-inside:auto}h2{break-after:avoid}button[data-open]{display:inline;background:transparent;color:#183c2e;padding:0;text-align:left;font:inherit}#original-sources{display:none}#evidence{break-inside:auto}#evidence details{break-inside:avoid}}'
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Beyond evidence report</title><style>' + CSS + print_css + '</style><main>' + ''.join(body) + '</main><script type="application/json" id="report-data">' + embedded + '</script><script>' + js + '</script></html>'
