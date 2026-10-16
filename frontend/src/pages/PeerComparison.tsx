import type { Report } from '../api/generated'
import { displayMetric, displayNumber } from './format'

export function PeerComparison({ report }: { report: Report }) {
  const benchmark = report.generation_metadata?.peer_benchmark
  if (!benchmark) return null
  const first = benchmark.comparisons[0]
  const rows = benchmark.comparisons.filter(r => r.metric === first?.metric && r.scope === first?.scope && r.comparison === first?.comparison).sort((a, b) => a.period_end.localeCompare(b.period_end))
  const all = rows.flatMap(r => [Number(r.company_value), Number(r.peer_median)]), lo = Math.min(...all, 0), range = Math.max(...all, 1) - lo || 1
  const line = (key: 'company_value' | 'peer_median') => rows.map((r, i) => `${45 + i * 510 / Math.max(1, rows.length - 1)},${150 - (Number(r[key]) - lo) * 120 / range}`).join(' ')
  return <section className="peer-comparison"><h3>Company story or sector story?</h3>{benchmark.status !== 'verified' ? <p>Inconclusive: matching figures from at least two peers could not be verified. Evidence strength is capped at Weak. {benchmark.missing?.join(' ')}</p> : <>
    <p>{displayMetric(first.metric)} · {first.scope} · {first.comparison === 'annual_growth' ? 'Annual growth (%)' : 'Reported ratio (%)'}</p>
    <svg viewBox="0 0 600 190" role="img" aria-label="Company and peer median comparison"><polyline points={line('company_value')} fill="none" stroke="#315b3e" strokeWidth="3"/><polyline points={line('peer_median')} fill="none" stroke="#a77a43" strokeWidth="3" strokeDasharray="5 4"/>{rows.map((r, i) => <g key={r.id}><circle cx={45 + i * 510 / Math.max(1, rows.length - 1)} cy={150 - (Number(r.company_value) - lo) * 120 / range} r="4" fill="#315b3e"/><text x={45 + i * 510 / Math.max(1, rows.length - 1)} y="180" fontSize="11">{r.period_end}</text></g>)}</svg><p>Green: company · Dashed gold: verified peer median</p>
    {benchmark.comparisons.map(row => <article key={row.id}><strong>{displayMetric(row.metric)} · {row.period_end} · {row.classification}</strong><p>Company {displayNumber(row.company_value)}% · Peer median {displayNumber(row.peer_median)}% · Gap {displayNumber(row.gap)} percentage points · {row.scope}</p></article>)}
    <details><summary>Peer figures and exact source passages</summary>{benchmark.sources?.map(bundle => <section key={bundle.company.id}><h4>{bundle.company.legal_name}</h4>{bundle.facts.map(f => { const p = bundle.passages.find(p => p.id === f.passage_id); const d = bundle.documents.find(d => d.id === p?.document_id); return <details key={f.id}><summary>{displayMetric(f.metric_key)}: {displayNumber(f.value_decimal)} · {f.period_end} · {f.scope}</summary>{d && <a href={d.canonical_url} target="_blank" rel="noreferrer">Original peer disclosure ↗</a>}<blockquote>{p?.text}</blockquote><small>Fact ID {f.id}</small></details>})}</section>)}</details>
  </>}</section>
}
