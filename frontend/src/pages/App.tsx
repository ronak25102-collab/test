import { useEffect, useMemo, useRef, useState } from 'react'
import type { Company, Report, RunSummary } from '../api/generated'
import { API_BASE, RequestError, api } from '../api/client'
import { ReportPrint } from './ReportPrint'
import { displayNumber, displayUnit } from './format'

const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())

export function App() {
  const [query, setQuery] = useState('HDFCBANK')
  const [companies, setCompanies] = useState<Company[]>([])
  const [selected, setSelected] = useState<Company | null>(null)
  const [asOf, setAsOf] = useState(today)
  const [mode, setMode] = useState('live')
  const [runId, setRunId] = useState<string | null>(new URLSearchParams(location.search).get('run'))
  const [run, setRun] = useState<RunSummary | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [events, setEvents] = useState<{ sequence: number; stage: string; public_summary: string }[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [configuration, setConfiguration] = useState<{ ready: boolean; issues: string[]; demo_time_warning: boolean } | null>(null)
  const [pollVersion, setPollVersion] = useState(0)
  const [claimId, setClaimId] = useState<string | null>(null)
  const restoredFormRun = useRef<string | null>(null)
  const creatingRun = useRef(false)
  const pendingCreation = useRef<{ signature: string; key: string } | null>(null)
  const runPending = Boolean(runId && (!run || run.id !== runId || !['completed', 'failed', 'cancelled'].includes(run.status)))
  const printable = new URLSearchParams(location.search).get('print') === '1'

  useEffect(() => {
    let active = true
    api.configuration().then(result => { if (active) setConfiguration(result) }).catch(() => {})
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => api.companies(query).then((data) => { if (active) setCompanies(data.items) }).catch((err) => { if (active) setError(err.message) }), 250)
    return () => { active = false; window.clearTimeout(timer) }
  }, [query])
  useEffect(() => {
    if (!runId) return
    let active = true
    let timer: number | undefined
    let failures = 0
    let pollingError: string | null = null
    const poll = async () => {
      try {
        const current = await api.run(runId)
        if (!active) return
        if (pollingError) { const recoveredError = pollingError; setError(previous => previous === recoveredError ? '' : previous) }
        pollingError = null
        failures = 0
        setRun(current)
        if (restoredFormRun.current !== runId) {
          restoredFormRun.current = runId
          setQuery(current.company.symbols[0] || current.company.legal_name)
          setCompanies([current.company]); setSelected(current.company)
          setAsOf(current.as_of); setMode(current.mode)
        }
        const eventData = await api.events(runId)
        setEvents(eventData.items)
        if (['completed', 'failed', 'cancelled'].includes(current.status)) {
          if (current.status === 'completed') { const result = await api.report(runId); if (active) setReport(result) }
          return
        }
        timer = window.setTimeout(poll, 1500)
      } catch (err) {
        if (!active) return
        pollingError = (err as Error).message
        setError(pollingError)
        // Read-only polling may recover after a local restart. Never replay a
        // creation or provider request, and stop for a nonexistent run.
        if (!(err instanceof RequestError && err.status === 404)) {
          failures += 1
          timer = window.setTimeout(poll, Math.min(15000, 1500 * 2 ** Math.min(failures, 4)))
        }
      }
    }
    poll()
    return () => { active = false; window.clearTimeout(timer) }
  }, [runId, pollVersion])

  const activeClaim = useMemo(() => report?.claims.find((claim) => claim.id === claimId) || null, [report, claimId])
  const activeEvidence = activeClaim ? activeClaim.evidence_links.map((link) => {
    const fact = report?.facts.find((f) => f.id === link.passage_or_fact_id)
    const passage = report?.passages.find((p) => p.id === (fact?.passage_id || link.passage_or_fact_id))
    const document = report?.documents.find((d) => d.id === passage?.document_id)
    return { link, passage, fact, document }
  }) : []
  async function resolveCompany() {
    setError(''); setBusy(true)
    try { const result = await api.resolve(query); setSelected(result.resolved); setCompanies([result.resolved]) }
    catch (err) { setError((err as Error).message) }
    finally { setBusy(false) }
  }
  async function resume() {
    if (!run) return
    try { await api.resume(run.id); setError(''); setPollVersion(v => v + 1) }
    catch (err) { setError((err as Error).message) }
  }

  async function start(company: Company | null = selected, cutoff = asOf, runMode = mode) {
    if (!company || creatingRun.current || runPending) return
    creatingRun.current = true
    const signature = JSON.stringify([company.id, cutoff, runMode])
    if (pendingCreation.current?.signature !== signature) pendingCreation.current = { signature, key: crypto.randomUUID() }
    const previousRun = run
    const previousReport = report
    setBusy(true); setError(''); setRun(null); setClaimId(null); setReport(null); setEvents([])
    try {
      const result = await api.createRun(company.id, cutoff, runMode, pendingCreation.current.key)
      pendingCreation.current = null
      setRunId(result.run_id)
      history.replaceState({}, '', `?run=${result.run_id}`)
    } catch (err) { setError((err as Error).message); setRun(previousRun); setReport(previousReport) }
    finally { creatingRun.current = false; setBusy(false) }
  }

  if (printable && report) return <ReportPrint report={report} />

  return <div className="shell">
    <header className="topbar"><div><span className="eyebrow">ATMOS 2026</span><h1>Beyond</h1></div><span className="track">TRACK A · FINANCIAL SERVICES</span></header>
    <main>
      <section className="control-card" aria-labelledby="start-heading">
        <div><span className="eyebrow">PUBLIC EVIDENCE WORKBENCH</span><h2 id="start-heading">Investigate a listed financial business</h2><p className="muted">The system resolves the entity, tests competing explanations and publishes only traceable findings.</p></div>
        <div className="form-grid"><label>Company search<input value={query} onChange={(e) => { setQuery(e.target.value); setSelected(null) }} placeholder="Name or exchange symbol" /></label><label>Cutoff date<input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></label><label>Mode<select value={mode} onChange={(e) => setMode(e.target.value)}><option value="replay">Replay · synthetic fixture</option><option value="live">Live · public sources</option><option value="deep">Deep · more candidates, same caps</option></select></label></div>
        <div className="company-results">{companies.slice(0, 5).map((company) => <button key={company.id} className={selected?.id === company.id ? 'company selected' : 'company'} onClick={() => setSelected(company)}><strong>{company.legal_name}</strong><span>{company.symbols.join(' · ')} · {company.business_profiles.join(', ')}</span></button>)}</div>
        <button className="quiet" disabled={busy || !query.trim()} onClick={resolveCompany}>Resolve from exchange directory</button>
        {mode !== 'replay' && configuration?.ready === false && <div className="error" role="status"><strong>Live research needs configuration.</strong> {configuration.issues.join(' ')} Replay remains available for SYNTHBANK.</div>}
        {mode !== 'replay' && configuration?.ready === true && configuration.demo_time_warning && <p className="muted">The configured research time limit exceeds eight minutes. Measure live runtime before the demo.</p>}
        <button className="primary" disabled={!selected || busy || runPending || (mode !== 'replay' && configuration?.ready === false)} onClick={() => start()}>Start autonomous research <span>→</span></button>
        {run?.status === 'queued' && <p role="status" className="muted">Research is queued. The worker processes one run at a time; another click is not needed.</p>}
      </section>
      {error && <div className="error" role="alert">{error}</div>}
      {run && !report && <Progress run={run} events={events} onCancel={() => api.cancel(run.id).then(() => setPollVersion(v => v + 1)).catch(err => setError(err.message))} onResume={resume} onRestart={() => start(run.company, run.as_of, run.mode)} />}
      {report && <Result report={report} onClaim={setClaimId} />}
      {report && activeClaim && <EvidenceDrawer report={report} claim={activeClaim} evidence={activeEvidence} onClose={() => setClaimId(null)} />}
    </main>
    <footer><span>Evidence first · No investment recommendations</span><span>{run ? `${run.mode.toUpperCase()} RUN ${run.id.slice(0, 8)}` : 'Ready for a bounded investigation'}</span></footer>
  </div>
}

function Progress({ run, events, onCancel, onResume, onRestart }: { run: RunSummary; events: { sequence: number; stage: string; public_summary: string }[]; onCancel: () => void; onResume: () => void; onRestart: () => void }) {
  const stopped = ['failed', 'cancelled'].includes(run.status)
  const expired = stopped && run.limitations.some(item => item.includes('run deadline exceeded'))
  return <section className="progress-card"><div className="section-head"><div><span className="eyebrow">{run.mode === 'replay' ? 'REPLAY' : 'LIVE'} RESEARCH</span><h2>{run.status === 'failed' ? 'Investigation failed' : run.status === 'cancelled' ? 'Investigation cancelled' : run.status === 'cancel_requested' ? 'Cancellation requested' : 'Investigation in progress'}</h2></div><button className="quiet" disabled={run.status === 'cancel_requested'} onClick={expired ? onRestart : stopped ? onResume : onCancel}>{expired ? 'Start a new run' : stopped ? 'Resume from saved work' : 'Cancel run'}</button></div><div className="progress-meta"><span>Stage <strong>{run.stage}</strong></span><span>Sources found <strong>{run.progress.sources_found || 0}</strong></span><span>Cutoff <strong>{run.as_of}</strong></span></div><p role={stopped ? 'alert' : undefined}>{expired ? 'This run reached its total time limit. Start a new run to continue research.' : run.limitations.join(' ')}</p><ol className="event-list">{events.map((event) => <li key={event.sequence} className="event"><span className="dot" /><div><strong>{event.stage}</strong><p>{event.public_summary}</p></div></li>)}</ol></section>
}

function Result({ report, onClaim }: { report: Report; onClaim: (id: string) => void }) {
  const discovery = report.discoveries[0]
  if (!discovery) return <section className="result-card abstention">
    <span className="eyebrow">{report.outcome === 'partial' ? 'PARTIAL RESEARCH' : 'RESEARCH COMPLETE'}</span>
    <h2>{report.facts.length ? 'Verified evidence collected' : 'More evidence needed'}</h2>
    {report.outcome === 'partial' && <p role="status">Research stopped before discovery verification finished. See source access and coverage details for the reason. Further investigation needs a new run.</p>}
    <p>{report.facts.length ? `${report.facts.length} verified facts from ${report.documents.length} documents. A primary discovery remains withheld until independent evidence supports it.` : 'The run completed, but the available sources did not establish a supported finding.'}</p>
    {!!report.facts.length && <section><h3>Verified source figures</h3><div className="facts-grid">{report.facts.map(fact => {
      const passage = report.passages.find(p => p.id === fact.passage_id)
      const document = report.documents.find(d => d.id === passage?.document_id)
      return <div className="fact" key={fact.id}><span>{fact.metric_key.replaceAll('_', ' ')}</span><strong>{displayNumber(fact.value_decimal)} <small>{displayUnit(fact.unit_normalized)}</small></strong><em>{fact.period_end} · {fact.scope}</em>{document && <a href={document.canonical_url} target="_blank" rel="noreferrer">Original source{passage?.page_index != null ? ` · page ${passage.page_index + 1}` : ''}</a>}{passage && <details><summary>Source passage</summary><blockquote>{passage.text}</blockquote><small>Raw unit: {fact.unit_raw} · Published: {document?.published_at?.slice(0, 10) || 'unknown'}{document?.cutoff_eligibility_basis === 'verified_retrieval' && ` · Public availability verified: ${document.retrieved_at}`}</small></details>}</div>
    })}</div></section>}
    {!!report.calculations.length && <section><h3>Reproducible calculations</h3><div className="facts-grid">{report.calculations.map(calc => <div className="fact" key={calc.id}><span>{calc.formula_id.replaceAll('_', ' ')}</span><strong>{displayNumber(calc.output_value)} <small>{displayUnit(calc.unit)}</small></strong><details><summary>Calculation inputs</summary><ol>{calc.input_fact_ids.map(id => { const fact = report.facts.find(f => f.id === id); return <li key={id}>{fact?.metric_key}: {displayNumber(fact?.value_decimal)} {displayUnit(fact?.unit_normalized)} · {fact?.period_end} · {fact?.scope}</li> })}</ol></details></div>)}</div></section>}
    <h3>What is still missing</h3><ul>{report.abstention?.missing_requirements.map((item) => <li key={item}>{item}</li>)}</ul>
    {!!report.abstention?.next_evidence_needed.length && <><h3>Next evidence needed</h3><ul>{report.abstention.next_evidence_needed.map(item => <li key={item}>{item}</li>)}</ul></>}
    <details className="limitations"><summary>Source access and coverage details</summary><ul>{report.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
  </section>
  return <section className="result-card"><div className="result-banner"><span className="eyebrow">PRIMARY DISCOVERY · {report.source_coverage.mode as string}</span><div className="result-actions"><a className="quiet" href={`?run=${report.run_id}&print=1`}>Print view</a><a className="quiet" href={`${API_BASE}/api/v1/runs/${report.run_id}/exports/report.json`}>JSON</a><a className="quiet" href={`${API_BASE}/api/v1/runs/${report.run_id}/exports/facts.csv`}>CSV</a><span className={`strength ${discovery.evidence_strength.toLowerCase()}`}>{discovery.evidence_strength} evidence</span></div></div><h2>{discovery.discovery_sentence}</h2><p className="rationale">{discovery.strength_rationale}</p><div className="two-col"><section><h3>Why it matters</h3><ul className="linked-list">{discovery.why_it_matters.map((item) => <li key={item.claim_id}><button onClick={() => onClaim(item.claim_id)}>{item.text}<span>↗</span></button></li>)}</ul></section><section className="counter"><h3>Strongest counterargument</h3><p>{discovery.counterargument.statement}</p><small>{discovery.counterargument.search_summary}</small><span className="pill">Active challenge {discovery.counterargument.search_attempted ? 'completed' : 'not run'}</span></section></div><section><h3>Key numbers <span className="muted">· verified inputs</span></h3><div className="facts-grid">{report.calculations.map((calc) => <button className="fact" key={calc.id} onClick={() => onClaim(report.claims.find((claim) => claim.calculation_ids.includes(calc.id))?.id || report.claims[0].id)}><span>{calc.formula_id.replaceAll('_', ' ')}</span><strong>{displayNumber(calc.output_value)} <small>{displayUnit(calc.unit)}</small></strong><em>{calc.limitations.length ? calc.limitations[0] : 'Reproducible calculation'}</em></button>)}</div></section><section className="timeline"><h3>Timeline</h3>{report.timeline_events.map((event) => <div className="timeline-row" key={event.id}><time>{event.event_date}</time><p>{event.description}<small>Publication {event.published_at?.slice(0, 10) || 'date unknown'} · {event.source_ids.length} source</small></p></div>)}</section><section className="falsification"><h3>What would change this conclusion</h3>{discovery.falsification_rules.map((rule) => <p key={rule.id}><strong>{rule.observable_metric_or_event}</strong> — {rule.operator}. {rule.interpretation}</p>)}</section><details className="limitations"><summary>Coverage and limitations</summary><ul>{report.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul><p>Source cutoff: {report.cutoff} · {report.documents.length} documents · {report.source_coverage.eligible_origin_families as number} independent origins</p></details></section>
}

const formulas: Record<string, string> = {
  yoy_growth: '(current / prior − 1) × 100', change_pp: 'current − prior', change_bps: '(current − prior) × 100',
  growth_gap: 'growth of A − growth of B', ldr_change: 'current advances / deposits × 100 − prior advances / deposits × 100',
  vnb_to_ape: 'VNB / APE × 100', fee_yield: 'fee revenue / average AUM × 100', loan_to_deposit: 'advances / deposits × 100', share_pct: 'component / total × 100', cagr: '((end / start) ^ (1 / years) − 1) × 100',
}

function EvidenceDrawer({ report, claim, evidence, onClose }: { report: Report; claim: Report['claims'][number]; evidence: { link: { passage_or_fact_id: string; relation: string; reason: string }; passage?: Report['passages'][number]; fact?: Report['facts'][number]; document?: Report['documents'][number] }[]; onClose: () => void }) {
  return <aside className="drawer" aria-label="Claim evidence"><button className="close" onClick={onClose} aria-label="Close evidence">×</button><span className="eyebrow">CLAIM PROVENANCE</span><h2>{claim.text}</h2><p className="pill">{claim.kind} · {claim.verification_status}</p>
    {evidence.map(({ link, passage, fact, document }) => <div className="evidence-item" key={link.passage_or_fact_id}><span className={link.relation === 'supporting' ? 'support' : 'oppose'}>{link.relation}</span><p>{link.reason}</p>
      {fact && <div className="source-fact"><strong>{fact.value_decimal}</strong> {fact.unit_normalized}<small>{fact.metric_key} · {fact.period_end} · {fact.scope}</small></div>}
      {document && <p><a href={document.canonical_url} target="_blank" rel="noreferrer">Open original source: {document.title}</a><small>{document.publisher} · published {document.published_at?.slice(0, 10) || 'unknown'} · {document.origin_family_id}</small></p>}
      {passage && <blockquote>“{passage.text}”<small>{passage.page_index != null ? `Page ${passage.page_index + 1} · ` : ''}{passage.section} · {passage.row_label} · {passage.column_label}</small></blockquote>}
    </div>)}
    {report.calculations.filter(c => claim.calculation_ids.includes(c.id)).map(calc => <section key={calc.id}><h3>{calc.formula_id.replaceAll('_', ' ')} · v{calc.formula_version}</h3><code>{formulas[calc.formula_id] || calc.formula_id}</code><ol>{calc.input_fact_ids.map(id => {
      const fact = report.facts.find(f => f.id === id)
      const passage = report.passages.find(p => p.id === fact?.passage_id)
      const document = report.documents.find(d => d.id === passage?.document_id)
      return <li key={id}>{fact?.metric_key}: {fact?.value_decimal} {fact?.unit_normalized} · {fact?.period_end} · {fact?.scope} {document && <a href={document.canonical_url} target="_blank" rel="noreferrer">Source</a>}</li>
    })}</ol><p>Output: {displayNumber(calc.output_value)} {displayUnit(calc.unit)}</p><p>{calc.comparability_checks.join('; ')}</p><p>{calc.limitations.join('; ')}</p></section>)}
  </aside>
}
