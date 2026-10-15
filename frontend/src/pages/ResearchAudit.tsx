import { useState } from 'react'
import type { Fact, Report } from '../api/generated'
import { displayNumber, displayUnit } from './format'

export function ResearchAudit({ report }: { report: Report }) {
  const decisions = report.generation_metadata?.research_decisions || []
  const eligible = report.documents.filter(d => d.cutoff_eligibility === 'eligible')
  const origins = new Set(eligible.map(d => d.origin_family_id)).size
  const issuer = eligible.filter(d => d.document_type.startsWith('issuer'))
  const factPassages = new Set(report.facts.map(f => f.passage_id))
  const supporting = new Set(report.passages.filter(p => factPassages.has(p.id)).map(p => p.document_id)).size
  return <section className="research-audit" aria-label="Research coverage and decisions">
    <h3>Research coverage</h3>
    <p>{report.facts.length} verified {report.facts.length === 1 ? 'fact' : 'facts'} · {report.calculations.length} reproducible {report.calculations.length === 1 ? 'calculation' : 'calculations'} · {issuer.length} official issuer {issuer.length === 1 ? 'filing' : 'filings'}</p>
    <p className="muted">{eligible.length} documents available by the cutoff · {origins} retrieved source families · {supporting} documents supporting verified facts.</p>
    {!report.facts.length && <p>Retrieved documents have not established verified financial figures. Availability alone does not establish issuer identity, relevance or support for a finding.</p>}
    <FactHistory report={report} />
    {report.generation_metadata?.novelty_rationale && <div><h3>Why this adds insight</h3><p>{report.generation_metadata.novelty_rationale}</p></div>}
    {!!decisions.length && <details><summary>Candidate decisions ({decisions.length})</summary>
      <p>These investigation candidates were not published as findings.</p>
      <ol>{decisions.map((decision, index) => <li key={index}>
        <strong>{decision.disposition.replaceAll('_', ' ')}</strong>: {decision.candidate}
        <p>{decision.reason}</p>
      </li>)}</ol>
    </details>}
  </section>
}

function FactHistory({ report }: { report: Report }) {
  const [selected, setSelected] = useState('')
  const groups = new Map<string, Fact[]>()
  for (const fact of report.facts) {
    if (!fact.period_end || fact.value_decimal == null || !Number.isFinite(Number(fact.value_decimal))) continue
    const key = [fact.metric_key, fact.scope, fact.segment, fact.currency, fact.unit_normalized,
      fact.definition_id, fact.period_type, fact.period_start?.slice(5), fact.period_end.slice(5)].join('|')
    groups.set(key, [...(groups.get(key) || []), fact])
  }
  const series = [...groups.entries()].filter(([, facts]) => new Set(facts.map(f => f.period_end)).size >= 2)
  if (!series.length) return <p>No comparable multi-period series was verified.</p>
  const active = series.find(([key]) => key === selected) || series[0]
  const facts = [...active[1]].sort((a, b) => a.period_end!.localeCompare(b.period_end!)).slice(-5)
  const values = facts.map(f => Number(f.value_decimal))
  const lo = Math.min(...values), hi = Math.max(...values)
  const pad = Math.max((hi - lo) * .15, Math.abs(hi) * .01, .01)
  const x = (index: number) => 45 + index * 370 / (facts.length - 1)
  const y = (value: number) => 140 - (value - lo + pad) / (hi - lo + pad * 2) * 105
  return <div className="fact-history">
    <label>Comparable metric <select aria-label="Comparable metric" value={active[0]} onChange={event => setSelected(event.target.value)}>
      {series.map(([key, observations]) => <option key={key} value={key}>{observations[0].metric_key.replaceAll('_', ' ')} · {observations[0].scope} · {observations[0].segment || 'all'}</option>)}
    </select></label>
    <svg viewBox="0 0 460 185" role="img" aria-label={`${facts[0].metric_key.replaceAll('_', ' ')} across ${facts.length} comparable dates`}>
      <line x1="45" x2="415" y1="145" y2="145" stroke="#ccd7d4" />
      <polyline fill="none" stroke="#1e4b51" strokeWidth="2" points={values.map((value, index) => `${x(index)},${y(value)}`).join(' ')} />
      {facts.map((fact, index) => <g key={fact.id}>
        <circle cx={x(index)} cy={y(values[index])} r="4" fill="#1e4b51" />
        <text x={x(index)} y={y(values[index]) - 10} textAnchor="middle" fontSize="11">{displayNumber(fact.value_decimal)}</text>
        <text x={x(index)} y="165" textAnchor="middle" fontSize="10">{fact.period_end}</text>
      </g>)}
    </svg>
    <p>{displayUnit(facts[0].unit_normalized)} · {facts[0].scope} · {facts[0].definition_id || 'reported definition'}</p>
    {facts.length < 3 && <p>Two snapshots establish a comparison; they do not establish when a trend began or prove its cause.</p>}
    <ul className="history-sources">{facts.map(fact => {
      const passage = report.passages.find(p => p.id === fact.passage_id)
      const document = report.documents.find(d => d.id === passage?.document_id)
      return <li key={fact.id}>{fact.period_end}: {displayNumber(fact.value_decimal)} {document && <a href={document.canonical_url} target="_blank" rel="noreferrer">Source{passage?.page_index != null ? ` · page ${passage.page_index + 1}` : ''}</a>}</li>
    })}</ul>
  </div>
}
