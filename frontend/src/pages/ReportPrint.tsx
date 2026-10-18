import { useEffect } from 'react'
import type { Calculation, Document, Fact, Report } from '../api/generated'
import { displayMetric, displayNumber, displayResearchGap, displayUnit } from './format'
import './report-print.css'

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Format an ISO date (YYYY-MM-DD) as "30 Jun 2026"; pass through anything unexpected.
function longDate(value?: string) {
  if (!value) return 'Unknown'
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!match) return value
  const [, year, month, day] = match
  const monthLabel = MONTHS[Number(month) - 1] || month
  return `${Number(day)} ${monthLabel} ${year}`
}

function scopeLabel(scope?: string) {
  if (!scope) return 'Unknown'
  return scope.charAt(0).toUpperCase() + scope.slice(1)
}

function SectionHeading({ index, title }: { index: number; title: string }) {
  return (
    <div className="pr-section-heading">
      <span className="pr-section-badge">{index}</span>
      <h2>{title}</h2>
    </div>
  )
}

// Two-bar comparison drawn as inline SVG so it survives print with no scripts.
function FigureBars({ observations, unit }: { observations: { label: string; value: number }[]; unit: string }) {
  if (observations.length < 1) return null
  const max = Math.max(...observations.map(o => o.value), 1)
  const width = 760
  const slot = width / observations.length
  const barWidth = Math.min(150, slot * 0.4)
  const topPad = 34 // headroom so the value label above the tallest bar is never clipped
  const chartHeight = 184
  const palette = ['#8a9a6b', '#20372a', '#3f6049', '#58764b']
  return (
    <svg className="pr-bars" viewBox={`0 0 ${width} 244`} role="img" aria-label="Verified figure comparison">
      <line x1="0" x2={width} y1={chartHeight} y2={chartHeight} stroke="#d8ddcd" strokeWidth="1" />
      {observations.map((o, i) => {
        const barHeight = Math.max(2, (o.value / max) * (chartHeight - topPad))
        const cx = slot * i + slot / 2
        const x = cx - barWidth / 2
        const y = chartHeight - barHeight
        return (
          <g key={o.label}>
            <text x={cx} y={y - 8} textAnchor="middle" className="pr-bar-value">{o.value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</text>
            <rect x={x} y={y} width={barWidth} height={barHeight} fill={palette[i % palette.length]} />
            <text x={cx} y={chartHeight + 24} textAnchor="middle" className="pr-bar-label">{o.label}</text>
          </g>
        )
      })}
      <text x="0" y="234" className="pr-bar-unit">{unit}</text>
    </svg>
  )
}

type StatItem = { value: string; label: string }

// Group limitations into the categories the report uses, keeping anything uncategorised under a general bucket.
function groupLimitations(limitations: string[]) {
  const groups: { title: string; items: string[] }[] = [
    { title: 'EVIDENCE GATES', items: [] },
    { title: 'SOURCE ACCESS', items: [] },
    { title: 'EXTRACTION AND OCR', items: [] },
    { title: 'RESEARCH PROCESS', items: [] },
    { title: 'COVERAGE AND DATING', items: [] },
    { title: 'OTHER', items: [] },
  ]
  const match = (text: string) => {
    const t = text.toLowerCase()
    if (/(gate|discovery was published|draft|corroboration|anchor|source-only prose)/.test(t)) return 0
    if (/(403|unavailable|portal|cover|access)/.test(t)) return 1
    if (/(ocr|tesseract|scanned|extraction|passage|issuer heading|candidate indices)/.test(t)) return 2
    if (/(timed out|timeout|retrieval stopped|allowance|verification|deadline|five seconds|stopped at its)/.test(t)) return 3
    if (/(snapshot|trend onset|publication date|coverage|dating|historical)/.test(t)) return 4
    return 5
  }
  for (const item of limitations) groups[match(item)].items.push(item)
  return groups.filter(group => group.items.length > 0)
}

export function ReportPrint({ report }: { report: Report }) {
  // The export popup opens this view with autoprint=1 so PDF is one click: open the print dialog once fonts are ready.
  useEffect(() => {
    if (new URLSearchParams(location.search).get('autoprint') !== '1') return
    let active = true
    document.fonts.ready.then(() => { if (active) window.setTimeout(() => { if (active) window.print() }, 300) })
    return () => { active = false }
  }, [])
  const discovery = report.discoveries[0]
  const cutoffLong = longDate(report.cutoff)
  const cutoffShort = cutoffLong.replace(/(\d+) (\w+) (\d+)/, '$1 $2 $3').toUpperCase()
  const coverageLabel = discovery
    ? `${discovery.evidence_strength} evidence`
    : report.facts.length
      ? 'Partial research coverage'
      : 'Insufficient eligible coverage'

  const cache = report.generation_metadata?.cache_usage
  const officialFilings = report.documents.filter(d => d.cutoff_eligibility === 'official' || d.origin_family_id?.includes('issuer')).length
  const originFamilies = new Set(report.documents.map(d => d.origin_family_id)).size
  const supportingDocs = new Set(
    report.facts
      .map(f => report.passages.find(p => p.id === f.passage_id)?.document_id)
      .filter(Boolean),
  ).size

  const coverageStats: StatItem[] = [
    { value: String(report.documents.length), label: 'documents available by the cutoff' },
    { value: String(report.passages.length), label: 'passages in the evidence register' },
    { value: String(report.facts.length), label: 'verified facts' },
    { value: String(report.calculations.length), label: 'reproducible calculations' },
    { value: String(officialFilings), label: 'official issuer filings' },
    { value: String(originFamilies), label: 'retrieved source families' },
    { value: String(supportingDocs), label: 'documents supporting verified facts' },
    {
      value: cache ? `${cache.reused} / ${cache.reused + cache.fresh}` : `0 / ${report.facts.length}`,
      label: `facts reused / fetched fresh${cache?.cold_start ? ' (cold start)' : ''}`,
    },
  ]

  // Build the verified-figure comparison from the metric that has the most comparable snapshots.
  const byMetric = new Map<string, Fact[]>()
  for (const fact of report.facts) {
    if (fact.value_decimal == null || !fact.period_end) continue
    const key = `${fact.metric_key}|${fact.scope}`
    const bucket = byMetric.get(key) || []
    bucket.push(fact)
    byMetric.set(key, bucket)
  }
  let comparison: { facts: Fact[]; metric: string; scope: string; unit: string; definition: string } | null = null
  for (const [, facts] of byMetric) {
    const sorted = [...facts].sort((a, b) => (a.period_end || '').localeCompare(b.period_end || ''))
    if (sorted.length >= 2 && (!comparison || sorted.length > comparison.facts.length)) {
      comparison = {
        facts: sorted,
        metric: displayMetric(sorted[0].metric_key),
        scope: scopeLabel(sorted[0].scope),
        unit: displayUnit(sorted[0].unit_normalized),
        definition: sorted[0].definition_id || `${sorted[0].metric_key}_v1`,
      }
    }
  }

  const decisions = report.generation_metadata?.research_decisions?.length || 0
  const unknownDateDocs = report.documents.filter(d => !d.published_at).length
  const limitationGroups = groupLimitations(report.limitations)
  let sectionNo = 0
  const num = () => ++sectionNo
  const inputsOf = (calculation: Calculation) => calculation.input_fact_ids.map(id => {
    const fact = report.facts.find(f => f.id === id)
    return fact ? `${fact.metric_key}: ${displayNumber(fact.value_decimal)} ${fact.unit_normalized} at ${fact.period_end} (${fact.scope})` : id
  }).join('; ')
  const runningStrip = `PUBLIC EVIDENCE RESEARCH | NO INVESTMENT RECOMMENDATION | SOURCE CUTOFF ${cutoffShort}`

  return (
    <article className="print-report pr">
      <button className="print-control" onClick={() => window.print()}>Print / Save as PDF</button>

      <div className="pr-watermark" aria-hidden="true">
        <svg viewBox="5 1 23 28" fill="none">
          <path fillRule="evenodd" fill="currentColor" d="M7 5v22h9a8 8 0 1 0 0-16h-3V5H7ZM13 17h3a2 2 0 1 1 0 4h-3v-4Z" />
          <path d="m20 3 6 6m0-6-6 6" stroke="currentColor" strokeWidth="2" />
        </svg>
      </div>

      <table className="pr-frame" role="presentation">
        <thead>
          <tr className="pr-frame-bar"><td><div className="pr-topbar" /></td></tr>
          <tr><td><div className="pr-running-header"><span>{runningStrip}</span><span>{report.company.legal_name}</span></div></td></tr>
        </thead>
        <tfoot>
          <tr><td><div className="pr-running-footer"><span>{runningStrip}</span><span>{report.company.legal_name}</span></div></td></tr>
        </tfoot>
        <tbody>
          <tr><td className="pr-frame-body">
      <header className="pr-cover">
        <span className="pr-kicker">COMPANY EVIDENCE REPORT</span>
        <h1>{report.company.legal_name}</h1>
        <p>Overview | Research cutoff {cutoffLong} | {coverageLabel}</p>
      </header>

      <div className={`pr-callout ${discovery ? 'pr-callout-published' : ''}`}>
        <strong>{discovery ? `PUBLISHED DISCOVERY \u00b7 ${discovery.evidence_strength.toUpperCase()} EVIDENCE` : 'INSUFFICIENT EVIDENCE'}</strong>
        {discovery
          ? <div><p className="pr-headline">{discovery.discovery_sentence}</p><p>{discovery.strength_rationale}</p></div>
          : <p>No primary discovery was published because the evidence gates did not pass. Additional investigation was carried out within the configured research limits.</p>}
      </div>

      {discovery && discovery.why_it_matters.length > 0 && (
        <section className="pr-section">
          <SectionHeading index={num()} title="Why it matters" />
          <ul className="pr-list">{discovery.why_it_matters.map(item => <li key={item.claim_id}>{item.text}</li>)}</ul>
        </section>
      )}

      <section className="pr-section">
        <SectionHeading index={num()} title="Research coverage" />
        <div className="pr-stat-grid">
          {coverageStats.map(stat => (
            <div className="pr-stat" key={stat.label}>
              <strong>{stat.value}</strong>
              <small>{stat.label}</small>
            </div>
          ))}
        </div>
      </section>

      {comparison && (
        <section className="pr-section">
          <SectionHeading index={num()} title="Verified figure comparison" />
          <div className="pr-keep">
          <p className="pr-meta-line">
            <strong>Metric</strong> {comparison.metric} ({comparison.scope.toLowerCase()}), comparison
            {'  '}<strong>Unit</strong> {comparison.unit}
            {'  '}<strong>Definition</strong> {comparison.definition}
          </p>
          <FigureBars
            unit={comparison.unit}
            observations={comparison.facts.map(f => ({ label: longDate(f.period_end), value: Number(f.value_decimal) }))}
          />
          </div>
          <table className="pr-table">
            <thead>
              <tr><th>Date</th><th>Scope</th><th>{comparison.metric} ({comparison.unit})</th><th>Source</th></tr>
            </thead>
            <tbody>
              {comparison.facts.map(f => {
                const passage = report.passages.find(p => p.id === f.passage_id)
                const page = passage?.page_index != null ? `Page ${passage.page_index + 1}` : 'Source register'
                return (
                  <tr key={f.id}>
                    <td>{longDate(f.period_end)}</td>
                    <td>{scopeLabel(f.scope)}</td>
                    <td>{displayNumber(f.value_decimal)}</td>
                    <td>{page}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="pr-note">
            Figures retain their reported scope and definition. Two snapshots establish a comparison; they do not
            establish when a trend began or prove its cause.{decisions > 0 && ` ${decisions} candidate decision${decisions === 1 ? ' was' : 's were'} recorded.`}
          </p>
        </section>
      )}

      {report.calculations.length > 0 && (discovery || !comparison) && (
        <section className="pr-section">
          <SectionHeading index={num()} title="Key numbers" />
          <table className="pr-table">
            <thead><tr><th>Calculation</th><th>Value</th><th>Unit</th><th>Inputs</th></tr></thead>
            <tbody>
              {report.calculations.map((calculation: Calculation) => (
                <tr key={calculation.id}>
                  <td>{calculation.formula_id}</td>
                  <td>{displayNumber(calculation.output_value)}</td>
                  <td>{displayUnit(calculation.unit)}</td>
                  <td>{inputsOf(calculation)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {discovery && report.timeline_events.length > 0 && (
        <section className="pr-section">
          <SectionHeading index={num()} title="Timeline" />
          <ul className="pr-list">
            {report.timeline_events.map(event => (
              <li key={event.id}>
                <strong>{event.event_date ? longDate(event.event_date) : 'Date unknown'}</strong> {'\u2014'} {event.description}{' '}
                <span className="pr-muted">(published {event.published_at ? longDate(event.published_at.slice(0, 10)) : 'date unknown'})</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {discovery && (
        <section className="pr-section">
          <SectionHeading index={num()} title="Counterargument" />
          <p>{discovery.counterargument.statement}</p>
          {discovery.counterargument.search_summary && <p className="pr-note">{discovery.counterargument.search_summary}</p>}
        </section>
      )}

      {discovery && discovery.falsification_rules.length > 0 && (
        <section className="pr-section">
          <SectionHeading index={num()} title="Falsification" />
          {discovery.falsification_rules.map(rule => (
            <p key={rule.id}><strong>{rule.observable_metric_or_event}:</strong> {rule.interpretation}</p>
          ))}
        </section>
      )}

      <section className="pr-section">
        <SectionHeading index={num()} title="Evidence register" />
        <p className="pr-note">
          {report.documents.length} documents | {report.passages.length} passages | {report.facts.length} normalized facts.
          Where the original publication date is unknown, public availability is verified by a dated retrieval receipt rather
          than an inferred publication date.
        </p>
        <table className="pr-table pr-register">
          <thead>
            <tr><th className="pr-num">#</th><th>Document</th><th>Publisher</th><th>Published</th></tr>
          </thead>
          <tbody>
            {report.documents.map((document: Document, index) => (
              <tr key={document.id}>
                <td className="pr-num">{index + 1}</td>
                <td>
                  {document.canonical_url ? <a href={document.canonical_url}>{document.title}</a> : document.title}
                </td>
                <td>{document.publisher}</td>
                <td>
                  {document.published_at
                    ? longDate(document.published_at.slice(0, 10))
                    : <span className="pr-unknown">Unknown<sup>*</sup></span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {unknownDateDocs > 0 && (
          <p className="pr-footnote">
            * Original publication date unknown for {unknownDateDocs} document{unknownDateDocs === 1 ? '' : 's'};
            public availability verified by retrieval receipt.
          </p>
        )}
      </section>

      {limitationGroups.length > 0 && (
        <section className="pr-section">
          <SectionHeading index={num()} title="Limitations" />
          {limitationGroups.map(group => (
            <div className="pr-limitation-group" key={group.title}>
              <h3>{group.title}</h3>
              <ul>{group.items.map(item => <li key={item}>{displayResearchGap(item)}</li>)}</ul>
            </div>
          ))}
        </section>
      )}

      <div className="pr-closing-strip" aria-hidden="true">{runningStrip}</div>
          </td></tr>
        </tbody>
      </table>
    </article>
  )
}
