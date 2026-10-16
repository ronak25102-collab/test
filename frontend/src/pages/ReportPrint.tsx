import type { Report } from '../api/generated'
import { displayNumber, displayUnit } from './format'
import { ResearchAudit } from './ResearchAudit'

export function ReportPrint({ report }: { report: Report }) {
  const discovery = report.discoveries[0]
  return <article className="print-report">
    <button className="print-control" onClick={() => window.print()}>Print / Save as PDF</button>
    <header><span className="eyebrow">TRACK A · {report.source_coverage.mode as string}</span><h1>{report.company.legal_name}</h1><p>Research cutoff: {report.cutoff} · {report.historical_coverage}</p></header>
    {discovery ? <>
      <section><h2>Discovery</h2><p className="print-headline">{discovery.discovery_sentence}</p><p><strong>{discovery.evidence_strength} evidence.</strong> {discovery.strength_rationale}</p></section>
      <section><h2>Why it matters</h2><ul>{discovery.why_it_matters.map((item) => <li key={item.claim_id}>{item.text}</li>)}</ul></section>
      <section><h2>Key numbers</h2><table><thead><tr><th>Calculation</th><th>Value</th><th>Unit</th><th>Inputs</th></tr></thead><tbody>{report.calculations.map((calculation) => <tr key={calculation.id}><td>{calculation.formula_id}</td><td>{displayNumber(calculation.output_value)}</td><td>{displayUnit(calculation.unit)}</td><td>{calculation.input_fact_ids.map(id => { const fact = report.facts.find(f => f.id === id); return `${fact?.metric_key}: ${displayNumber(fact?.value_decimal)} ${fact?.unit_normalized} at ${fact?.period_end} (${fact?.scope})` }).join('; ')}</td></tr>)}</tbody></table></section>
      <section><h2>Timeline</h2><ul>{report.timeline_events.map(event => <li key={event.id}>{event.event_date} — {event.description} (published {event.published_at?.slice(0, 10) || 'date unknown'})</li>)}</ul></section>
      <section><h2>Counterargument</h2><p>{discovery.counterargument.statement}</p><p>{discovery.counterargument.search_summary}</p></section>
      <section><h2>Falsification</h2>{discovery.falsification_rules.map((rule) => <p key={rule.id}><strong>{rule.observable_metric_or_event}:</strong> {rule.interpretation}</p>)}</section>
    </> : <section><h2>Insufficient evidence</h2><p>No primary discovery was published.</p><ul>{report.abstention?.missing_requirements.map((item) => <li key={item}>{item}</li>)}</ul></section>}
    <section><h2>Evidence register</h2><p>{report.documents.length} documents · {report.passages.length} passages · {report.facts.length} normalized facts.</p><ul>{report.documents.map((document) => <li key={document.id}><a href={document.canonical_url}>{document.title}</a> — {document.publisher} — {document.published_at?.slice(0, 10) || 'publication date unknown'}{document.cutoff_eligibility_basis === 'verified_retrieval' && ` (public availability verified ${document.retrieved_at})`} — {document.canonical_url}</li>)}</ul></section>
    <ResearchAudit report={report} />
    <section><h2>Limitations</h2><ul>{report.limitations.map(item => <li key={item}>{item}</li>)}</ul></section>
    <footer>Public evidence research · no investment recommendation · source cutoff {report.cutoff}</footer>
  </article>
}
