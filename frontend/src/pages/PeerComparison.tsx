import type { Fact, Report } from '../api/generated'
import { displayMetric, displayNumber } from './format'

export function PeerComparison({ report }: { report: Report }) {
  const benchmark = report.generation_metadata?.peer_benchmark
  if (!benchmark) return null
  const first = benchmark.comparisons[0]
  const rows = benchmark.comparisons.filter(r => r.metric === first?.metric && r.scope === first?.scope && r.comparison === first?.comparison).sort((a, b) => a.period_end.localeCompare(b.period_end))
  const all = rows.flatMap(r => [Number(r.company_value), Number(r.peer_median)]), lo = Math.min(...all, 0), range = Math.max(...all, 1) - lo || 1
  const line = (key: 'company_value' | 'peer_median') => rows.map((r, i) => `${45 + i * 510 / Math.max(1, rows.length - 1)},${150 - (Number(r[key]) - lo) * 120 / range}`).join(' ')
  const snapshot = rows.length < 2 ? benchmark.comparisons.filter((r, i, all) => r.comparison === first.comparison && r.period_end === first.period_end && all.findIndex(o => o.metric === r.metric && o.scope === r.scope && o.comparison === r.comparison && o.period_end === r.period_end) === i) : []
  const barValues = snapshot.flatMap(r => [Number(r.company_value), Number(r.peer_median)])
  const barHigh = Math.max(...barValues, 0), barLow = Math.min(...barValues, 0), barRange = barHigh - barLow || 1
  const zeroY = 30 + barHigh * 100 / barRange + (barHigh > 0 ? 14 : 0)
  return <section className="peer-comparison"><h3>Company story or sector story?</h3>{benchmark.status !== 'verified' ? <><article className="peer-inconclusive"><p>Inconclusive: matching figures from at least two peers could not be verified. Evidence strength is capped at Weak. {benchmark.missing?.join(' ')}</p></article><CompanyGrowth report={report} /></> : <>
    <p>{snapshot.length > 1 ? 'Compared metrics' : displayMetric(first.metric)} · {first.scope} · {first.comparison === 'annual_growth' ? 'Annual growth (%)' : 'Reported ratio (%)'}</p>
    {rows.length < 2 ? <>
      <svg viewBox="0 0 600 200" role="img" aria-label={`Company and peer median comparison on ${first.period_end}`}>
        <line x1="40" x2="570" y1={zeroY} y2={zeroY} stroke="#ccd7d4" />
        {snapshot.map((r, i) => {
          const cx = 40 + (i + .5) * 530 / snapshot.length
          return <g key={r.id}>{([['company_value', '#315b3e', -22], ['peer_median', '#a77a43', 22]] as const).map(([key, color, dx]) => {
            const v = Number(r[key]), h = Math.max(2, Math.abs(v) * 100 / barRange), top = v >= 0 ? zeroY - h : zeroY
            return <g key={key}><rect x={cx + dx - 18} y={top} width="36" height={h} fill={color} /><text x={cx + dx} y={v >= 0 ? top - 6 : top + h + 14} textAnchor="middle" fontSize="11">{displayNumber(r[key])}%</text></g>
          })}<text x={cx} y="192" textAnchor="middle" fontSize="11">{displayMetric(r.metric)}</text></g>
        })}
      </svg><p>Green: company · Gold: verified peer median · {first.period_end}</p>
    </> : <>
    <svg viewBox="0 0 600 190" role="img" aria-label="Company and peer median comparison"><polyline points={line('company_value')} fill="none" stroke="#315b3e" strokeWidth="3"/><polyline points={line('peer_median')} fill="none" stroke="#a77a43" strokeWidth="3" strokeDasharray="5 4"/>{rows.map((r, i) => <g key={r.id}><circle cx={45 + i * 510 / Math.max(1, rows.length - 1)} cy={150 - (Number(r.company_value) - lo) * 120 / range} r="4" fill="#315b3e"/><text x={45 + i * 510 / Math.max(1, rows.length - 1)} y="180" fontSize="11">{r.period_end}</text></g>)}</svg><p>Green: company · Dashed gold: verified peer median</p>
    </>}
    {benchmark.comparisons.map(row => <article key={row.id}><strong>{displayMetric(row.metric)} · {row.period_end} · {row.classification}</strong><p>Company {displayNumber(row.company_value)}% · Peer median {displayNumber(row.peer_median)}% · Gap {displayNumber(row.gap)} percentage points · {row.scope}</p></article>)}
    <details><summary>Peer figures and exact source passages</summary>{benchmark.sources?.map(bundle => <section key={bundle.company.id}><h4>{bundle.company.legal_name}</h4>{bundle.facts.map(f => { const p = bundle.passages.find(p => p.id === f.passage_id); const d = bundle.documents.find(d => d.id === p?.document_id); return <details key={f.id}><summary>{displayMetric(f.metric_key)}: {displayNumber(f.value_decimal)} · {f.period_end} · {f.scope}</summary>{d && <a href={d.canonical_url} target="_blank" rel="noreferrer">Original peer disclosure ↗</a>}<blockquote>{p?.text}</blockquote><small>Fact ID {f.id}</small></details>})}</section>)}</details>
  </>}</section>
}

// Without verified peers there is no sector median, but the company's own verified
// annual growth (registered yoy_growth calculations) can still be charted honestly.
function CompanyGrowth({ report }: { report: Report }) {
  const facts = new Map(report.facts.map(fact => [fact.id, fact]))
  const latest = new Map<string, { metric: string; scope: string; period: string; value: number }>()
  for (const calc of report.calculations) {
    if (calc.formula_id !== 'yoy_growth' || calc.output_value == null || !Number.isFinite(Number(calc.output_value))) continue
    const inputs = calc.input_fact_ids.map(id => facts.get(id)).filter((fact): fact is Fact => Boolean(fact?.period_end))
    if (!inputs.length) continue
    const current = inputs.reduce((a, b) => (a.period_end! >= b.period_end! ? a : b))
    const key = `${current.metric_key}|${current.scope}`
    const previous = latest.get(key)
    if (!previous || current.period_end! > previous.period) latest.set(key, { metric: current.metric_key, scope: current.scope, period: current.period_end!, value: Number(calc.output_value) })
  }
  const bars = [...latest.values()].sort((a, b) => a.scope.localeCompare(b.scope) || a.metric.localeCompare(b.metric))
  if (!bars.length) return null
  const scopes = new Set(bars.map(bar => bar.scope))
  const periods = [...new Set(bars.map(bar => bar.period))]
  const high = Math.max(...bars.map(bar => bar.value), 0), low = Math.min(...bars.map(bar => bar.value), 0), span = high - low || 1
  const plot = 110, top = 24
  const zeroY = top + high * plot / span
  const width = 600, slot = (width - 80) / bars.length, barWidth = Math.min(48, slot * .45)
  return <div className="company-growth">
    <p>Company only · verified annual growth (%){scopes.size === 1 ? ` · ${[...scopes][0]}` : ''}</p>
    <svg viewBox={`0 0 ${width} 190`} role="img" aria-label={`Verified annual growth for ${report.company.legal_name}; no verified peer median`}>
      <line x1="40" x2={width - 40} y1={zeroY} y2={zeroY} stroke="#ccd7d4" />
      {bars.map((bar, index) => {
        const cx = 40 + (index + .5) * slot
        const h = Math.max(2, Math.abs(bar.value) * plot / span), y = bar.value >= 0 ? zeroY - h : zeroY
        return <g key={`${bar.metric}|${bar.scope}`}>
          <rect x={cx - barWidth / 2} y={y} width={barWidth} height={h} fill="#315b3e" />
          <text x={cx} y={bar.value >= 0 ? y - 6 : y + h + 14} textAnchor="middle" fontSize="11">{displayNumber(String(bar.value))}%</text>
          <text x={cx} y="182" textAnchor="middle" fontSize="11">{displayMetric(bar.metric)}{scopes.size > 1 ? ` · ${bar.scope}` : ''}</text>
        </g>
      })}
    </svg>
    <p>Green: company · No verified peer median to compare · {periods.length === 1 ? periods[0] : `latest of ${periods.join(', ')}`}</p>
  </div>
}
