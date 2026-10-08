import type { Report } from '../api/generated'

export function ReportPrint({ report }: { report: Report }) {
  const discovery = report.discoveries[0]
  return <article className="print-report">
    <header><span className="eyebrow">TRACK A · {report.source_coverage.mode as string}</span><h1>{report.company.legal_name}</h1><p>Research cutoff: {report.cutoff} · {report.historical_coverage}</p></header>
    {discovery ? <>
      <section><h2>Discovery</h2><p className="print-headline">{discovery.discovery_sentence}</p><p><strong>{discovery.evidence_strength} evidence.</strong> {discovery.strength_rationale}</p></section>
      <section><h2>Why it matters</h2><ul>{discovery.why_it_matters.map((item) => <li key={item.claim_id}>{item.text}</li>)}</ul></section>
      <section><h2>Key numbers</h2><table><thead><tr><th>Calculation</th><th>Value</th><th>Unit</th><th>Inputs</th></tr></thead><tbody>{report.calculations.map((calculation) => <tr key={calculation.id}><td>{calculation.formula_id}</td><td>{calculation.output_value ?? 'Unavailable'}</td><td>{calculation.unit}</td><td>{calculation.input_fact_ids.length} verified facts</td></tr>)}</tbody></table></section>
      <section><h2>Counterargument</h2><p>{discovery.counterargument.statement}</p><p>{discovery.counterargument.search_summary}</p></section>
      <section><h2>Falsification</h2>{discovery.falsification_rules.map((rule) => <p key={rule.id}><strong>{rule.observable_metric_or_event}:</strong> {rule.interpretation}</p>)}</section>
    </> : <section><h2>Insufficient evidence</h2><p>No primary discovery was published.</p><ul>{report.abstention?.missing_requirements.map((item) => <li key={item}>{item}</li>)}</ul></section>}
    <section><h2>Evidence register</h2><p>{report.documents.length} documents · {report.passages.length} passages · {report.facts.length} normalized facts.</p><ul>{report.documents.map((document) => <li key={document.id}>{document.title} — {document.publisher} — {document.canonical_url}</li>)}</ul></section>
    <footer>Public evidence research · no investment recommendation · source cutoff {report.cutoff}</footer>
  </article>
}
