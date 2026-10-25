import { useId, useState } from 'react'
import type { Fact, Report } from '../api/generated'
import { displayMetric, displayNumber, displayUnit } from './format'

export function ResearchAudit({ report, onFact }: { report: Report; onFact?: (fact: Fact) => void }) {
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
    {!!report.generation_metadata?.historical_cache?.length && <details className="history-cache-note"><summary>Historical source cache was used</summary><p>Historical observations came from earlier live runs after source-hash checks. Original retrieval dates remain visible. Conclusions were not reused; searches and discovery review belong to this run.</p>{report.generation_metadata.historical_cache.map((cache, index) => <p key={index}>{cache.fact_ids.length} historical facts · source run {cache.source_run_id}</p>)}</details>}
    {!report.facts.length && <p>Retrieved documents have not established verified financial figures. Availability alone does not establish issuer identity, relevance or support for a finding.</p>}
    <FactHistory report={report} onFact={onFact} />
    {report.generation_metadata?.novelty_rationale && <div className="audit-insight"><h3>Why this adds insight</h3><p>{report.generation_metadata.novelty_rationale}</p></div>}
    {!!decisions.length && <details><summary>Candidate decisions ({decisions.length})</summary>
      <p>These investigation candidates were not published as findings.</p>
      <ol>{decisions.map((decision, index) => <li key={index}>
        <strong>{decision.disposition.replaceAll('_', ' ')}</strong>: {decision.candidate}
        <p>{decision.reason}</p>
      </li>)}</ol>
    </details>}
  </section>
}

function FactHistory({ report, onFact }: { report: Report; onFact?: (fact: Fact) => void }) {
  const [selected, setSelected] = useState('')
  const [pointId, setPointId] = useState('')
  const gradient = useId()
  const groups = new Map<string, Fact[]>()
  for (const fact of report.facts) {
    if (!fact.period_end || fact.value_decimal == null || !Number.isFinite(Number(fact.value_decimal))) continue
    const key = [fact.metric_key, fact.scope, fact.segment, fact.currency, fact.unit_normalized,
      fact.definition_id, fact.period_type, fact.period_start?.slice(5), fact.period_end.slice(5)].join('|')
    groups.set(key, [...(groups.get(key) || []), fact])
  }
  const recorded = report.source_coverage.historical_series
  if (Array.isArray(recorded)) {
    for (const [index, value] of recorded.entries()) {
      if (!value || value.cadence !== 'quarterly' || !Array.isArray(value.observations)) continue
      const ids = new Set(value.observations.map((o: { fact_id?: string }) => o.fact_id))
      const observations = report.facts.filter(f => ids.has(f.id))
      if (observations.length >= 3) groups.set(`quarterly-${index}`, observations)
    }
  }
  const series = [...groups.entries()].filter(([, facts]) => new Set(facts.map(f => f.period_end)).size >= 2)
  if (!series.length) return <div className="history-empty"><span aria-hidden="true">↳</span><p>No comparable multi-period series was verified.</p><small>The comparison view appears when compatible reporting dates are available.</small></div>
  const active = series.find(([key]) => key === selected) || series[0]
  const facts = [...active[1]].sort((a, b) => a.period_end!.localeCompare(b.period_end!))
  const values = facts.map(f => Number(f.value_decimal))
  const lo = Math.min(...values), hi = Math.max(...values)
  const pad = Math.max((hi - lo) * .15, Math.abs(hi) * .01, .01)
  const x = (index: number) => 45 + index * 370 / (facts.length - 1)
  const y = (value: number) => 140 - (value - lo + pad) / (hi - lo + pad * 2) * 105
  const inspected = facts.find(fact => fact.id === pointId) || facts[facts.length - 1]
  const points = values.map((value, index) => `${x(index)},${y(value)}`).join(' ')
  return <div className="fact-history">
    <div className="history-heading"><div><span className="section-kicker">COMPARE THE VERIFIED FIGURES</span><h4>How the numbers moved.</h4></div><span>{facts.length} {active[0].startsWith('quarterly-') ? (facts.length === 1 ? 'quarter' : 'quarters') : (facts.length === 1 ? 'year' : 'years')} observed</span></div>
    <label>Comparable metric <select aria-label="Comparable metric" value={active[0]} onChange={event => setSelected(event.target.value)}>
      {series.map(([key, observations]) => <option key={key} value={key}>{observations[0].metric_key.replaceAll('_', ' ')} · {observations[0].scope} · {observations[0].segment || 'all'}{key.startsWith('quarterly-') ? ' · consecutive quarters' : ' · annual comparison'}</option>)}
    </select></label>
    <div className="history-chart-frame"><svg viewBox="0 0 460 185" role="img" aria-label={`${facts[0].metric_key.replaceAll('_', ' ')} across ${facts.length} comparable dates`} key={active[0]}>
      <defs><linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#7c9e61" stopOpacity=".18" /><stop offset="1" stopColor="#7c9e61" stopOpacity="0" /></linearGradient></defs>
      {[40, 75, 110].map(level => <line key={level} x1="45" x2="415" y1={level} y2={level} stroke="#dce4d2" strokeDasharray="2 5" />)}
      <line x1="45" x2="415" y1="145" y2="145" stroke="#ccd7d4" />
      <polygon points={`45,145 ${points} 415,145`} fill={`url(#${gradient})`} />
      <polyline className="history-line" pathLength="1" fill="none" stroke="#315b3e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" points={points} />
      {(report.generation_metadata?.structural_breaks || []).filter(b => b.metric === facts[0].metric_key && b.scope === facts[0].scope).map(b => { const index = facts.findIndex(f => f.period_end === b.end); return index < 0 ? null : <g key={b.id}><line x1={x(index)} x2={x(index)} y1="20" y2="145" stroke="#a77a43" strokeDasharray="4 4"/><text x={x(index)} y="15" fontSize="10">Structural break</text></g> })}
      {facts.map((fact, index) => <g key={fact.id}>
        <circle cx={x(index)} cy={y(values[index])} r="4" fill="#1e4b51" />
        {(facts.length <= 6 || index === 0 || index === facts.length - 1) && <text x={x(index)} y={y(values[index]) - 10} textAnchor="middle" fontSize="11">{displayNumber(fact.value_decimal)}</text>}
        {(facts.length <= (active[0].startsWith('quarterly-') ? 6 : 7) || index % 4 === 0 || index === facts.length - 1) && <text x={x(index)} y="165" textAnchor="middle" fontSize="10">{fact.period_end}</text>}
      </g>)}
    </svg>{facts.map((fact, index) => <button className={`history-point ${inspected.id === fact.id ? 'point-selected' : ''}`} key={fact.id} style={{ left: `${x(index) / 460 * 100}%`, top: `${y(values[index]) / 185 * 100}%` }} aria-label={`${displayMetric(fact.metric_key)} on ${fact.period_end}: ${displayNumber(fact.value_decimal)} ${displayUnit(fact.unit_normalized)}`} aria-pressed={inspected.id === fact.id} onClick={() => setPointId(fact.id)} onFocus={() => setPointId(fact.id)} onPointerEnter={() => setPointId(fact.id)} onKeyDown={event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
      event.preventDefault()
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? facts.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + facts.length) % facts.length
      const buttons = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('.history-point')
      buttons?.[next]?.focus()
    }}><span /></button>)}</div>
    <div className="history-inspected" aria-live="polite"><div><span>{inspected.period_end} · {inspected.scope}</span><strong>{displayNumber(inspected.value_decimal)} <small>{displayUnit(inspected.unit_normalized)}</small></strong></div>{onFact && <button onClick={() => onFact(inspected)}>Inspect selected source <span>↗</span></button>}</div>
    <p>{displayUnit(facts[0].unit_normalized)} · {facts[0].scope} · {facts[0].definition_id || 'reported definition'}</p>
    <small className="history-axis-note">Axis fitted to displayed values. Figures retain their reported scope and definition.</small>
    {facts.length < 3 && <p>Two snapshots establish a comparison; they do not establish when a trend began or prove its cause.</p>}
    <ul className="history-sources">{facts.map(fact => {
      const passage = report.passages.find(p => p.id === fact.passage_id)
      const document = report.documents.find(d => d.id === passage?.document_id)
      return <li key={fact.id}>{fact.period_end}: {displayNumber(fact.value_decimal)} {document && <a href={document.canonical_url} target="_blank" rel="noreferrer">Source{passage?.page_index != null ? ` · page ${passage.page_index + 1}` : ''}</a>}</li>
    })}</ul>
  </div>
}
