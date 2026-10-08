import { useEffect, useMemo, useState } from 'react'
import type { Company, Report, RunSummary } from '../api/generated'
import { API_BASE, api } from '../api/client'
import { ReportPrint } from './ReportPrint'

const today = new Date().toISOString().slice(0, 10)

export function App() {
  const [query, setQuery] = useState('SYNTHBANK')
  const [companies, setCompanies] = useState<Company[]>([])
  const [selected, setSelected] = useState<Company | null>(null)
  const [asOf, setAsOf] = useState(today)
  const [mode, setMode] = useState('replay')
  const [runId, setRunId] = useState<string | null>(new URLSearchParams(location.search).get('run'))
  const [run, setRun] = useState<RunSummary | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [events, setEvents] = useState<{ sequence: number; stage: string; public_summary: string }[]>([])
  const [error, setError] = useState('')
  const [claimId, setClaimId] = useState<string | null>(null)
  const printable = new URLSearchParams(location.search).get('print') === '1'

  useEffect(() => { api.companies(query).then((data) => setCompanies(data.items)).catch((err) => setError(err.message)) }, [query])
  useEffect(() => {
    if (!runId) return
    let active = true
    const poll = async () => {
      try {
        const current = await api.run(runId)
        if (!active) return
        setRun(current)
        const eventData = await api.events(runId)
        setEvents(eventData.items)
        if (['completed', 'failed', 'cancelled'].includes(current.status)) {
          if (current.status === 'completed') setReport(await api.report(runId))
          return
        }
        window.setTimeout(poll, 1500)
      } catch (err) { if (active) setError((err as Error).message) }
    }
    poll()
    return () => { active = false }
  }, [runId])

  const activeClaim = useMemo(() => report?.claims.find((claim) => claim.id === claimId) || null, [report, claimId])
  const activeEvidence = activeClaim ? activeClaim.evidence_links.map((link) => ({ link, passage: report?.passages.find((passage) => passage.id === link.passage_or_fact_id), fact: report?.facts.find((fact) => fact.id === link.passage_or_fact_id) })) : []

  async function start() {
    if (!selected) return
    setError(''); setReport(null); setEvents([])
    try {
      const result = await api.createRun(selected.id, asOf, mode)
      setRunId(result.run_id)
      history.replaceState({}, '', `?run=${result.run_id}`)
    } catch (err) { setError((err as Error).message) }
  }

  if (printable && report) return <ReportPrint report={report} />

  return <div className="shell">
    <header className="topbar"><div><span className="eyebrow">ATMOS 2026</span><h1>Signal Research</h1></div><span className="track">TRACK A · FINANCIAL SERVICES</span></header>
    <main>
      <section className="control-card" aria-labelledby="start-heading">
        <div><span className="eyebrow">PUBLIC EVIDENCE WORKBENCH</span><h2 id="start-heading">Investigate a listed financial business</h2><p className="muted">The system resolves the entity, tests competing explanations and publishes only traceable findings.</p></div>
        <div className="form-grid"><label>Company search<input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name or exchange symbol" /></label><label>Cutoff date<input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></label><label>Mode<select value={mode} onChange={(e) => setMode(e.target.value)}><option value="replay">Replay · synthetic fixture</option><option value="live">Live · public sources</option><option value="deep">Deep · extended budget</option></select></label></div>
        <div className="company-results">{companies.slice(0, 5).map((company) => <button key={company.id} className={selected?.id === company.id ? 'company selected' : 'company'} onClick={() => setSelected(company)}><strong>{company.legal_name}</strong><span>{company.symbols.join(' · ')} · {company.business_profiles.join(', ')}</span></button>)}</div>
        <button className="primary" disabled={!selected} onClick={start}>Start autonomous research <span>→</span></button>
      </section>
      {error && <div className="error" role="alert">{error}</div>}
      {run && !report && <Progress run={run} events={events} onCancel={() => api.cancel(run.id)} />}
      {report && <Result report={report} onClaim={setClaimId} />}
      {report && activeClaim && <EvidenceDrawer claim={activeClaim} evidence={activeEvidence} onClose={() => setClaimId(null)} />}
    </main>
    <footer><span>Evidence first · No investment recommendations</span><span>{run ? `${run.mode.toUpperCase()} RUN ${run.id.slice(0, 8)}` : 'Ready for a bounded investigation'}</span></footer>
  </div>
}

function Progress({ run, events, onCancel }: { run: RunSummary; events: { sequence: number; stage: string; public_summary: string }[]; onCancel: () => void }) {
  return <section className="progress-card"><div className="section-head"><div><span className="eyebrow">{run.mode === 'replay' ? 'REPLAY' : 'LIVE'} RESEARCH</span><h2>Investigation in progress</h2></div><button className="quiet" onClick={onCancel}>Cancel run</button></div><div className="progress-meta"><span>Stage <strong>{run.stage}</strong></span><span>Sources found <strong>{run.progress.sources_found || 0}</strong></span><span>Cutoff <strong>{run.as_of}</strong></span></div><ol className="event-list">{events.map((event) => <li key={event.sequence} className="event"><span className="dot" /><div><strong>{event.stage}</strong><p>{event.public_summary}</p></div></li>)}</ol></section>
}

function Result({ report, onClaim }: { report: Report; onClaim: (id: string) => void }) {
  const discovery = report.discoveries[0]
  if (!discovery) return <section className="result-card abstention"><span className="eyebrow">INSUFFICIENT EVIDENCE</span><h2>No primary discovery published</h2><p>The system preserved the research gap rather than filling it with an unsupported narrative.</p><h3>What was missing</h3><ul>{report.abstention?.missing_requirements.map((item) => <li key={item}>{item}</li>)}</ul><p className="muted">{report.limitations.join(' ')}</p></section>
  return <section className="result-card"><div className="result-banner"><span className="eyebrow">PRIMARY DISCOVERY · {report.source_coverage.mode as string}</span><div className="result-actions"><a className="quiet" href={`?run=${report.run_id}&print=1`}>Print view</a><a className="quiet" href={`${API_BASE}/api/v1/runs/${report.run_id}/exports/report.json`}>JSON</a><a className="quiet" href={`${API_BASE}/api/v1/runs/${report.run_id}/exports/facts.csv`}>CSV</a><span className={`strength ${discovery.evidence_strength.toLowerCase()}`}>{discovery.evidence_strength} evidence</span></div></div><h2>{discovery.discovery_sentence}</h2><p className="rationale">{discovery.strength_rationale}</p><div className="two-col"><section><h3>Why it matters</h3><ul className="linked-list">{discovery.why_it_matters.map((item) => <li key={item.claim_id}><button onClick={() => onClaim(item.claim_id)}>{item.text}<span>↗</span></button></li>)}</ul></section><section className="counter"><h3>Strongest counterargument</h3><p>{discovery.counterargument.statement}</p><small>{discovery.counterargument.search_summary}</small><span className="pill">Active challenge {discovery.counterargument.search_attempted ? 'completed' : 'not run'}</span></section></div><section><h3>Key numbers <span className="muted">· verified inputs</span></h3><div className="facts-grid">{report.calculations.map((calc) => <button className="fact" key={calc.id} onClick={() => onClaim(report.claims.find((claim) => claim.calculation_ids.includes(calc.id))?.id || report.claims[0].id)}><span>{calc.formula_id.replaceAll('_', ' ')}</span><strong>{calc.output_value ?? 'Unavailable'} <small>{calc.unit}</small></strong><em>{calc.limitations.length ? calc.limitations[0] : 'Reproducible calculation'}</em></button>)}</div></section><section className="timeline"><h3>Timeline</h3>{report.timeline_events.map((event) => <div className="timeline-row" key={event.id}><time>{event.event_date}</time><p>{event.description}<small>Disclosed {event.published_at?.slice(0, 10)} · {event.source_ids.length} source</small></p></div>)}</section><section className="falsification"><h3>What would change this conclusion</h3>{discovery.falsification_rules.map((rule) => <p key={rule.id}><strong>{rule.observable_metric_or_event}</strong> — {rule.operator}. {rule.interpretation}</p>)}</section><details className="limitations"><summary>Coverage and limitations</summary><ul>{report.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul><p>Source cutoff: {report.cutoff} · {report.documents.length} documents · {report.source_coverage.eligible_origin_families as number} independent origins</p></details></section>
}

function EvidenceDrawer({ claim, evidence, onClose }: { claim: Report['claims'][number]; evidence: { link: { passage_or_fact_id: string; relation: string; reason: string }; passage?: Report['passages'][number]; fact?: Report['facts'][number] }[]; onClose: () => void }) {
  return <aside className="drawer" aria-label="Claim evidence"><button className="close" onClick={onClose} aria-label="Close evidence">×</button><span className="eyebrow">CLAIM PROVENANCE</span><h2>{claim.text}</h2><p className="pill">{claim.kind} · {claim.verification_status}</p>{evidence.map(({ link, passage, fact }) => <div className="evidence-item" key={link.passage_or_fact_id}><span className={link.relation === 'supporting' ? 'support' : 'oppose'}>{link.relation}</span><p>{link.reason}</p>{fact && <div className="source-fact"><strong>{fact.value_decimal}</strong> {fact.unit_normalized}<small>{fact.metric_key} · {fact.period_end} · {fact.scope}</small></div>}{passage && <blockquote>“{passage.text}”<small>{passage.section} · passage {passage.id.slice(0, 8)}</small></blockquote>}</div>)}</aside>
}
