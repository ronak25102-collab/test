import { useEffect, useMemo, useRef, useState } from 'react'
import type { Company, Report, RunSummary } from '../api/generated'
import { RequestError, api } from '../api/client'
import { ReportPrint } from './ReportPrint'
import { ResearchResult } from './ResearchResult'
import { calculationFormulas, displayNumber, displayUnit } from './format'
import { Arrow, BeyondMark, Landing } from './Landing'
import { usePageMotion } from '../usePageMotion'
import { QueueControls } from './QueueControls'
import { ResearchProgress } from './ResearchProgress'
import { RunHistory } from './RunHistory'
import { useAppRoute } from '../appRoute'
import './research-pages.css'

const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())

export function App() {
  const { route, navigate } = useAppRoute()
  const landingVisible = route.view === 'home'
  const [motionPaused, setMotionPaused] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const { shellRef, activeSection } = usePageMotion(motionPaused, landingVisible)
  const [query, setQuery] = useState('HDFCBANK')
  const [companies, setCompanies] = useState<Company[]>([])
  const [selected, setSelected] = useState<Company | null>(null)
  const [asOf, setAsOf] = useState(today)
  const [mode, setMode] = useState('live')
  const [coldStart, setColdStart] = useState(false)
  const runId = route.runId || null
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
  const revealNewRun = useRef(false)
  const pendingCreation = useRef<{ signature: string; key: string } | null>(null)
  const runPending = Boolean(runId && (!run || run.id !== runId || !['completed', 'failed', 'cancelled'].includes(run.status)))
  const printable = new URLSearchParams(location.search).get('print') === '1'
  const reportVisible = !landingVisible && route.view !== 'workspace' && report?.run_id === runId
  const workspaceVisible = route.view === 'workspace'
  const progressVisible = !landingVisible && !workspaceVisible && !reportVisible

  useEffect(() => {
    setRun(null); setReport(null); setEvents([]); setClaimId(null); setError('')
    restoredFormRun.current = null
  }, [runId])

  useEffect(() => {
    if (!runId || !run || run.id !== runId || printable) return
    const next = run.status === 'completed' && report?.run_id === runId ? 'report' : 'progress'
    if (route.view === 'run' || (route.view === 'progress' && next === 'report') || (route.view === 'report' && run.status !== 'completed')) {
      navigate({ view: next, runId, section: route.section || 'overview' }, { replace: true, scroll: next === 'report' })
    }
  }, [run, report, runId, route.view, route.section, printable, navigate])

  useEffect(() => { setClaimId(null) }, [route.view, route.section])

  useEffect(() => {
    if (!reportVisible) return
    const frame = requestAnimationFrame(() => document.getElementById('research-page-heading')?.focus({ preventScroll: true }))
    return () => cancelAnimationFrame(frame)
  }, [reportVisible])

  useEffect(() => {
    const page = workspaceVisible ? 'Research workspace' : reportVisible ? `Report - ${route.section || 'overview'}` : progressVisible ? 'Research progress' : 'Look beyond the numbers'
    document.title = `${run?.id === runId ? `${run.company.legal_name} | ` : ''}${page} - Beyond`
  }, [workspaceVisible, reportVisible, progressVisible, route.section, run, runId])

  useEffect(() => {
    if (!revealNewRun.current || !run || run.id !== runId) return
    const panel = document.querySelector<HTMLElement>('#investigation-progress, .result-card')
    if (!panel) return
    revealNewRun.current = false
    panel.focus({ preventScroll: true })
    panel.scrollIntoView({ block: 'start', behavior: motionPaused || matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
  }, [run, runId, motionPaused, report])

  function launchWorkspace() {
    navigate({ view: 'workspace' })
    window.requestAnimationFrame(() => document.getElementById('start-heading')?.focus({ preventScroll: true }))
  }

  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const change = () => setMotionPaused(preference.matches)
    preference.addEventListener('change', change)
    return () => preference.removeEventListener('change', change)
  }, [])

  useEffect(() => {
    let active = true
    api.configuration().then(result => { if (active) setConfiguration(result) }).catch(() => {})
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!workspaceVisible) return
    let active = true
    const timer = window.setTimeout(() => api.companies(query).then((data) => { if (active) setCompanies(data.items) }).catch((err) => { if (active) setError(err.message) }), 250)
    return () => { active = false; window.clearTimeout(timer) }
  }, [query, workspaceVisible])
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
          setColdStart(Boolean(current.cold_start))
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
    const signature = JSON.stringify([company.id, cutoff, runMode, coldStart])
    if (pendingCreation.current?.signature !== signature) pendingCreation.current = { signature, key: crypto.randomUUID() }
    const previousRun = run
    const previousReport = report
    setBusy(true); setError(''); setRun(null); setClaimId(null); setReport(null); setEvents([])
    try {
      const result = await api.createRun(company.id, cutoff, runMode, pendingCreation.current.key, coldStart)
      pendingCreation.current = null
      revealNewRun.current = true
      navigate({ view: 'progress', runId: result.run_id })
      setPollVersion(value => value + 1)
    } catch (err) { setError((err as Error).message); setRun(previousRun); setReport(previousReport) }
    finally { creatingRun.current = false; setBusy(false) }
  }

  if (printable && report) return <ReportPrint report={report} />

  return <div ref={shellRef} className={`shell ${motionPaused ? 'motion-paused' : ''} ${landingVisible ? 'with-landing' : 'workspace-view'}`}>
    <a className="skip-link" href={landingVisible ? '#platform' : '#research'}>{landingVisible ? 'Skip to main content' : 'Skip to research'}</a>
    <header className="topbar"><a className="brand" href="/" aria-label="Beyond home"><BeyondMark /><span>beyond<span className="brand-period">.</span></span></a><nav aria-label="Main navigation">{[['platform', 'Platform'], ['how-it-works', 'How it works'], ['why-beyond', 'Our approach']].map(([id, label]) => <a key={id} href={landingVisible ? `#${id}` : `/#${id}`} aria-current={landingVisible && activeSection === id ? 'location' : undefined}>{label}</a>)}</nav><div className="header-actions"><button className="button-dark header-launch" onClick={launchWorkspace}>{landingVisible ? 'Launch workspace' : workspaceVisible ? 'Research workspace' : 'New research'}<Arrow diagonal /></button></div><span className="reading-progress" aria-hidden="true" /></header>
    <main className="app-main">
      {landingVisible && <Landing onLaunch={launchWorkspace} motionPaused={motionPaused} />}
      <div className={`workspace-container research-page ${reportVisible ? 'report-page' : progressVisible ? 'progress-page' : 'setup-page'}`} id="research" hidden={landingVisible}>
      {!landingVisible && <>
      {!workspaceVisible && <nav className="research-breadcrumbs" aria-label="Research navigation"><a href="?view=workspace" onClick={event => { if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); launchWorkspace() } }}>Research workspace</a><span aria-hidden="true">/</span><span>{reportVisible ? 'Saved report' : 'Live progress'}</span></nav>}
      <div className="workspace-heading"><div><span className="section-kicker">BEYOND / {workspaceVisible ? 'RESEARCH WORKSPACE' : reportVisible ? 'RESEARCH REPORT' : 'LIVE INVESTIGATION'}</span><h1 id="research-page-heading" tabIndex={-1}>{workspaceVisible ? 'The evidence starts here.' : reportVisible ? 'Your research, in focus.' : 'Following the evidence.'}</h1><p>{workspaceVisible ? 'A company. A question. A trail you can follow.' : run?.id === runId ? `${run.company.legal_name} \u00b7 Cutoff ${run.as_of} \u00b7 ${run.mode === 'replay' ? 'Synthetic replay' : run.mode === 'deep' ? 'Extended research' : 'Live research'}` : 'Opening your saved investigation...'}</p></div>{!reportVisible && <QueueControls onCleared={() => setPollVersion(v => v + 1)} />}</div>
      </>}
      {workspaceVisible && <>
      <section className="control-card" aria-labelledby="start-heading">
        <div className="control-heading"><span className="control-number">01</span><div><span className="eyebrow">SET THE DIRECTION</span><h2 id="start-heading" tabIndex={-1}>Investigate a listed financial business</h2><p className="muted">Choose the company, define your cutoff, and follow the evidence.</p></div></div>
        <div className="form-grid"><label>Company search<input value={query} onChange={(e) => { setQuery(e.target.value); setSelected(null) }} placeholder="Name or exchange symbol" /></label><label>Cutoff date<input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></label><label>Mode<select value={mode} onChange={(e) => setMode(e.target.value)}><option value="replay">Replay · synthetic fixture</option><option value="live">Live · public sources</option><option value="deep">Deep · extended research, outside demo budget</option></select></label></div>
        <div className="company-results">{companies.slice(0, 5).map((company) => <button key={company.id} className={selected?.id === company.id ? 'company selected' : 'company'} onClick={() => setSelected(company)}><strong>{company.legal_name}</strong><span>{company.symbols.join(' · ')} · {company.business_profiles.join(', ')}</span></button>)}</div>
        <div className="resolve-line"><button className="quiet" disabled={busy || !query.trim()} onClick={resolveCompany}>Resolve from exchange directory</button><span>Search by company name or NSE symbol.</span></div>
        {mode !== 'replay' && configuration?.ready === false && <div className="error" role="status"><strong>Live research needs configuration.</strong> {configuration.issues.join(' ')} Replay remains available for SYNTHBANK.</div>}
        {mode !== 'replay' && <label className="cold-start-control"><input type="checkbox" checked={coldStart} onChange={e => setColdStart(e.target.checked)} /> Cold start rehearsal · disable historical fact reuse</label>}
        <div className="research-launch"><button className="primary" disabled={!selected || busy || runPending || (mode !== 'replay' && configuration?.ready === false)} onClick={() => start()}>{busy ? 'Preparing research…' : 'Start autonomous research'} <Arrow /></button><span>Original sources. Visible reasoning.<br />Conclusions that earn their place.</span></div>
      </section>
      <RunHistory refreshKey={`${runId || ''}:${run?.status || ''}`} onOpen={saved => navigate({ view: saved.status === 'completed' ? 'report' : 'progress', runId: saved.id, section: 'overview' })} />
      </>}
      {error && <div className="error" role="alert">{error}</div>}
      {progressVisible && run?.status === 'queued' && <p role="status" className="research-queue-note">Research is queued. Your investigation starts when a worker is available; this page updates automatically.</p>}
      {progressVisible && !run && !error && <div className="research-page-loading" role="status"><span className="research-loading-line" />Opening investigation and checking its latest status...</div>}
      {progressVisible && error && <button className="quiet" onClick={() => { setError(''); setPollVersion(value => value + 1) }}>Retry loading investigation</button>}
      {progressVisible && run?.id === runId && <ResearchProgress run={run} events={events} onCancel={() => api.cancel(run.id).then(() => setPollVersion(v => v + 1)).catch(err => setError(err.message))} onResume={resume} onRestart={() => start(run.company, run.as_of, run.mode)} />}
      {reportVisible && report && <ResearchResult report={report} onClaim={setClaimId} section={route.section || 'overview'} onNavigate={section => navigate({ view: 'report', runId: report.run_id, section })} key={report.run_id} />}
      {reportVisible && report && activeClaim && <EvidenceDrawer report={report} claim={activeClaim} evidence={activeEvidence} onClose={() => setClaimId(null)} />}
      </div>
    </main>
    <footer className="site-footer"><a className="brand" href="/">beyond.</a><span>Evidence first · No investment recommendations</span><span>EVIDENCE-BOUND FINANCIAL RESEARCH</span></footer>
  </div>
}

function EvidenceDrawer({ report, claim, evidence, onClose }: { report: Report; claim: Report['claims'][number]; evidence: { link: { passage_or_fact_id: string; relation: string; reason: string }; passage?: Report['passages'][number]; fact?: Report['facts'][number]; document?: Report['documents'][number] }[]; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => { const dialog = ref.current; const previous = document.activeElement as HTMLElement | null; dialog?.showModal(); return () => { if (dialog?.open) dialog.close(); previous?.focus({ preventScroll: true }) } }, [])
  return <dialog ref={ref} className="drawer claim-drawer" aria-label="Claim evidence" onCancel={event => { event.preventDefault(); onClose() }}><button className="close" onClick={onClose} aria-label="Close evidence">×</button><span className="eyebrow">CLAIM PROVENANCE</span><h2>{claim.text}</h2><p className="pill">{claim.kind} · {claim.verification_status}</p>
    {evidence.map(({ link, passage, fact, document }) => <div className="evidence-item" key={link.passage_or_fact_id}><span className={link.relation === 'supporting' ? 'support' : 'oppose'}>{link.relation}</span><p>{link.reason}</p>
      {fact && <div className="source-fact"><strong>{fact.value_decimal}</strong> {fact.unit_normalized}<small>{fact.metric_key} · {fact.period_end} · {fact.scope}</small></div>}
      {document && <p><a href={document.canonical_url} target="_blank" rel="noreferrer">Open original source: {document.title}</a><small>{document.publisher} · published {document.published_at?.slice(0, 10) || 'unknown'} · {document.origin_family_id}</small></p>}
      {passage && <blockquote>“{passage.text}”<small>{passage.page_index != null ? `Page ${passage.page_index + 1} · ` : ''}{passage.section} · {passage.row_label} · {passage.column_label}</small></blockquote>}
    </div>)}
    {report.calculations.filter(c => claim.calculation_ids.includes(c.id)).map(calc => <section key={calc.id}><h3>{calc.formula_id.replaceAll('_', ' ')} · v{calc.formula_version}</h3><code>{calculationFormulas[calc.formula_id] || calc.formula_id}</code><ol>{calc.input_fact_ids.map(id => {
      const fact = report.facts.find(f => f.id === id)
      const passage = report.passages.find(p => p.id === fact?.passage_id)
      const document = report.documents.find(d => d.id === passage?.document_id)
      return <li key={id}>{fact?.metric_key}: {fact?.value_decimal} {fact?.unit_normalized} · {fact?.period_end} · {fact?.scope} {document && <a href={document.canonical_url} target="_blank" rel="noreferrer">Source</a>}</li>
    })}</ol><p>Output: {displayNumber(calc.output_value)} {displayUnit(calc.unit)}</p><p>{calc.comparability_checks.join('; ')}</p><p>{calc.limitations.join('; ')}</p></section>)}
  </dialog>
}
