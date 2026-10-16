import { type CSSProperties, useEffect, useId, useRef, useState } from 'react'
import type { RunSummary } from '../api/generated'

type RunEvent = { sequence: number; stage: string; public_summary: string; event_type?: string }

const stages = ['resolving', 'planning', 'discovering', 'fetching', 'extracting', 'normalizing', 'hypothesizing', 'investigating', 'challenging', 'verifying', 'composing']
const phases = [
  { title: 'Find the sources', short: 'Discover', stages: ['resolving', 'planning', 'discovering', 'fetching'], description: 'Resolve the business, plan the investigation and retrieve original financial disclosures alongside independent context.', detail: 'Issuer filings · Exchange disclosures · Independent sources' },
  { title: 'Read the numbers', short: 'Examine', stages: ['extracting', 'normalizing', 'hypothesizing', 'investigating'], description: 'Read source passages, align reporting periods and units, and investigate candidate explanations with reproducible calculations.', detail: 'Source passages · Comparable periods · Registered formulas' },
  { title: 'Challenge the case', short: 'Challenge', stages: ['challenging', 'verifying'], description: 'Search for counterevidence and alternative explanations. Check citations, financial calculations and the evidence needed to support a finding.', detail: 'Counterarguments · Citation checks · Evidence review' },
  { title: 'Build the report', short: 'Report', stages: ['composing'], description: 'Assemble the evidence trail, calculations and limitations into a report. If the evidence is insufficient, show what is still missing.', detail: 'Traceable findings · Honest uncertainty · Saved results' },
]

const stageCopy: Record<string, string> = {
  resolving: 'Identifying the business', planning: 'Planning the investigation', discovering: 'Looking for original sources',
  fetching: 'Opening financial disclosures', extracting: 'Reading the financial filings', normalizing: 'Aligning periods and units',
  hypothesizing: 'Connecting the financial signals', investigating: 'Checking the numbers', challenging: 'Testing another explanation',
  verifying: 'Reviewing the evidence', composing: 'Preparing the research report',
}

function FinanceIcon({ phase }: { phase: number }) {
  if (phase === 0) return <g><path d="M-17 3 0-7 17 3M-14 7h28M-15 29h30M-19 33h38M-11 11v14M0 11v14M11 11v14" /><circle cx="0" cy="1" r="1" /></g>
  if (phase === 1) return <g><rect x="-16" y="-7" width="28" height="37" rx="3" /><path d="M-9 2H5M-9 9H0M-9 16h6M6 28l9 9" /><circle cx="5" cy="19" r="9" /></g>
  if (phase === 2) return <g><path d="M0-8 17-1v13c0 11-8 18-17 23-9-5-17-12-17-23V-1L0-8Z" /><path d="m-8 12 6 6 11-13" /></g>
  return <g><rect x="-15" y="-7" width="30" height="41" rx="3" /><path d="M-8 2H8M-8 9h11M-8 26v-5M0 26V16M8 26V12" /><path d="M-9 38H9" /></g>
}

function MoneyJourney({ run, events }: { run: RunSummary; events: RunEvent[] }) {
  const [inspectedPhase, setInspectedPhase] = useState<number | null>(null)
  const [clock, setClock] = useState(Date.now())
  useEffect(() => { const timer = window.setInterval(() => setClock(Date.now()), 1000); return () => window.clearInterval(timer) }, [])
  const timestamp = (value: string) => Date.parse(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z')
  const elapsed = run.started_at ? Math.max(0, Math.floor(((run.ended_at ? timestamp(run.ended_at) : clock) - timestamp(run.started_at)) / 1000)) : 0
  const id = useId()
  const scene = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const element = scene.current
    if (!element) return
    let visible = false
    const update = () => element.classList.toggle('scene-awake', visible && !document.hidden)
    const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; update() })
    observer.observe(element)
    document.addEventListener('visibilitychange', update)
    return () => { observer.disconnect(); document.removeEventListener('visibilitychange', update) }
  }, [])
  const finished = run.status === 'completed'
  const stopped = ['failed', 'cancelled', 'cancel_requested'].includes(run.status)
  const queued = run.status === 'queued'
  const knownStage = stages.includes(run.stage) ? run.stage : [...events].reverse().find(event => stages.includes(event.stage))?.stage
  const stage = queued ? undefined : knownStage
  const stageIndex = stage ? stages.indexOf(stage) : -1
  const currentPhase = finished ? 3 : Math.max(0, phases.findIndex(phase => phase.stages.includes(stage || '')))
  const selected = inspectedPhase ?? currentPhase
  const completedStages = finished ? stages.length : Math.max(0, stageIndex)
  const moving = !stopped && !queued && !finished && stageIndex >= 0
  const state = queued ? 'Waiting for a worker' : run.status === 'failed' ? 'Research stopped' : run.status === 'cancelled' ? 'Research cancelled' : run.status === 'cancel_requested' ? 'Stopping research' : finished ? 'Research finished' : 'Research in motion'
  const caption = queued ? 'Your investigation is in the queue. The journey begins when a worker is available.'
    : stopped ? `${stage ? stageCopy[stage] : 'The investigation'} · Saved work is retained.`
    : finished ? 'The research workflow has finished. The report records the findings and limitations.'
    : stage ? stageCopy[stage] : 'Waiting for the next stage update'

  return <div className={`money-journey ${moving ? 'journey-moving' : 'journey-still'} ${stopped ? 'journey-stopped' : ''}`}>
    <div className="journey-heading"><div><span className="journey-kicker">FOLLOW THE EVIDENCE</span><h3>Following the money.<br /><span>Checking the story.</span></h3></div><span className="journey-live"><i />{state}</span></div>
    <p className="journey-live-metrics" role="timer" aria-label="Live research measurements">Stage: {run.stage} · {Math.floor(elapsed / 60)}:{String(elapsed % 60).padStart(2, '0')} elapsed · {run.progress.facts_verified || 0} facts verified · {run.progress.facts_reused || 0} reused / {run.progress.facts_fresh || 0} fresh</p>
    <div className="journey-caption" aria-live="polite"><strong>{caption}</strong><span>{run.company.legal_name} · {run.mode === 'replay' ? 'Synthetic replay' : 'Public financial research'}</span></div>
    <div className="finance-scene" aria-hidden="true" ref={scene}>
      <svg viewBox="0 0 960 280" fill="none">
        <defs><linearGradient id={`${id}-ribbon`} x1="135" y1="180" x2="825" y2="180" gradientUnits="userSpaceOnUse"><stop stopColor="#71945a" /><stop offset="1" stopColor="#254f39" /></linearGradient><clipPath id={`${id}-flow`}><rect x="0" y="0" width={finished ? 960 : 135 + currentPhase * 230} height="280" /></clipPath></defs>
        <path className="finance-ribbon-shadow" d="m135 210 115-58 115 58 115-58 115 58 115-58 115 58" />
        <path className="finance-ribbon" d="m135 202 115-58 115 58 115-58 115 58 115-58 115 58" />
        <g clipPath={`url(#${id}-flow)`}><path className="finance-ribbon-fill" d="m135 202 115-58 115 58 115-58 115 58 115-58 115 58" stroke={`url(#${id}-ribbon)`} /><path className="finance-flow-dots" d="m135 202 115-58 115 58 115-58 115 58 115-58 115 58" /></g>
        {phases.map((phase, index) => {
          const done = finished || (!queued && stageIndex >= 0 && index < currentPhase)
          const active = !queued && stageIndex >= 0 && index === currentPhase && !finished
          const withinPhase = phase.stages.indexOf(stage || '')
          const scale = done ? 1 : active ? .42 + .43 * (withinPhase + 1) / phase.stages.length : .12
          return <g key={phase.short} transform={`translate(${135 + index * 230},0)`} className={`finance-pillar ${done ? 'pillar-done' : active ? 'pillar-active' : 'pillar-pending'} ${selected === index ? 'pillar-inspected' : ''}`}>
            <ellipse className="pillar-shadow" cx="0" cy="238" rx="59" ry="14" />
            <g className="finance-pillar-fill" style={{ '--pillar-scale': scale } as CSSProperties}><path className="pillar-left" d="m-45 92 45 24v110l-45-24Z" /><path className="pillar-right" d="m0 116 45-24v110L0 226Z" /><path className="pillar-top" d="m-45 92 45-24 45 24-45 24Z" /></g>
            <path className="pillar-wire" d="m-45 92 45-24 45 24v110L0 226l-45-24V92l45 24 45-24M0 116v110" />
            <g className="pillar-symbol" transform="translate(0,35)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><FinanceIcon phase={index} /></g>
            {active && <g className="finance-coin"><ellipse cx="29" cy="27" rx="13" ry="15" /><ellipse cx="27" cy="26" rx="11" ry="14" /><text x="27" y="31" textAnchor="middle">₹</text></g>}
            {done && <g className="pillar-check"><circle cy="17" r="12" /><path d="m-5 17 4 4 7-8" /></g>}
          </g>
        })}
      </svg>
    </div>
    <div className="journey-phases" aria-label="Explore research milestones">{phases.map((phase, index) => <button key={phase.short} className={`${index === currentPhase && !queued ? 'phase-current' : ''} ${finished || (!queued && stageIndex >= 0 && index < currentPhase) ? 'phase-done' : ''}`} aria-pressed={selected === index} aria-controls={`${id}-detail`} onClick={() => setInspectedPhase(index)}><span>{String(index + 1).padStart(2, '0')}</span><strong>{phase.short}</strong><small>{finished || (!queued && stageIndex >= 0 && index < currentPhase) ? 'Passed' : index === currentPhase ? queued ? 'Waiting' : stopped ? 'Stopped' : 'Current stage' : 'Ahead'}</small></button>)}</div>
    <div className="journey-stage-track" role="progressbar" aria-label="Research stage progress" aria-valuemin={0} aria-valuemax={stages.length} aria-valuenow={stageIndex >= 0 || queued || finished ? completedStages : undefined} aria-valuetext={`${state}. ${stage ? `${stage}. Stage ${stageIndex + 1} of ${stages.length}.` : queued ? 'No stages started.' : finished ? 'All workflow stages finished.' : 'Stage update unavailable.'} Stage count, not time remaining.`}><span style={{ width: `${completedStages / stages.length * 100}%` }} /></div>
    <div className="journey-stage-legend"><span>{finished ? `${stages.length} / ${stages.length} stages finished` : queued ? 'Waiting to begin' : stageIndex >= 0 ? `Stage ${stageIndex + 1} / ${stages.length} · ${stage}` : 'Awaiting stage update'}</span><span>Stages vary in duration</span></div>
    <div className="journey-detail" id={`${id}-detail`} aria-live="polite"><div key={selected}><span className="journey-kicker">{inspectedPhase === null ? 'CURRENT MILESTONE' : 'EXPLORE THE PROCESS'}</span><h4>{phases[selected].title}</h4><p>{phases[selected].description}</p><small>{phases[selected].detail}</small></div>{inspectedPhase !== null && <button className="journey-follow" onClick={() => setInspectedPhase(null)}>Follow live stage <span>↗</span></button>}</div>
    <div className="journey-counters">{[['Sources located', 'sources_found'], ['Documents read', 'documents_parsed'], ['Calculations', 'calculations_completed'], ['Challenge checks', 'counterevidence_checks']].map(([label, key]) => <div key={key}><strong>{run.progress[key] || 0}</strong><span>{label}</span></div>)}</div>
  </div>
}

export function ResearchProgress({ run, events, onCancel, onResume, onRestart }: { run: RunSummary; events: RunEvent[]; onCancel: () => void; onResume: () => void; onRestart: () => void }) {
  const stopped = ['failed', 'cancelled'].includes(run.status)
  const expired = stopped && run.limitations.some(item => item.includes('run deadline exceeded'))
  const heading = run.status === 'failed' ? 'Investigation failed' : run.status === 'cancelled' ? 'Investigation cancelled' : run.status === 'cancel_requested' ? 'Cancellation requested' : run.status === 'completed' ? 'Research complete' : 'Investigation in progress'
  const agents = new Map<string, { status: string; detail: string }>()
  for (const event of events) {
    if (!event.event_type?.startsWith('research_agent_')) continue
    const match = event.public_summary.match(/^(.+): (started|completed|failed)(.*)$/)
    if (match) agents.set(match[1], { status: match[2], detail: match[3].trim() })
  }
  return <section className="progress-card" id="investigation-progress" aria-labelledby="progress-heading" tabIndex={-1}>
    <div className="section-head"><div><span className="eyebrow">{run.mode === 'replay' ? 'REPLAY' : 'LIVE'} RESEARCH</span><h2 id="progress-heading">{heading}</h2></div>{run.status !== 'completed' && <button className="quiet" disabled={run.status === 'cancel_requested'} onClick={expired ? onRestart : stopped ? onResume : onCancel}>{expired ? 'Start a new run' : stopped ? 'Resume from saved work' : 'Cancel run'}</button>}</div>
    <MoneyJourney run={run} events={events} key={run.id} />
    {agents.size > 0 && <div className="research-agents"><h3>Research team</h3><ul aria-label="Research agents">{[...agents].map(([name, agent]) => {
      const status = agent.status === 'started' ? stopped || run.status === 'completed' ? 'Incomplete' : 'Working' : agent.status === 'completed' ? 'Complete' : 'Incomplete'
      return <li key={name} data-agent-status={status.toLowerCase()}><span>{name}</span><strong>{status}</strong>{agent.detail && <small>{agent.detail}</small>}</li>
    })}</ul><p>Parallel workers share one research budget. Every figure still passes source and calculation checks.</p></div>}
    <div className="progress-meta"><span>Stage <strong>{run.stage}</strong></span><span>Sources found <strong>{run.progress.sources_found || 0}</strong></span><span>Cutoff <strong>{run.as_of}</strong></span></div>
    <p role={stopped ? 'alert' : undefined}>{expired ? 'This run reached its total time limit. Start a new run to continue research.' : run.limitations.join(' ')}</p>
    <details className="run-activity" open={stopped || undefined}><summary>Activity log <span>{events.length} {events.length === 1 ? 'update' : 'updates'}</span></summary><ol className="event-list">{events.map(event => <li key={event.sequence} className="event"><span className="dot" /><div><strong>{event.stage}</strong><p>{event.public_summary}</p></div></li>)}</ol></details>
  </section>
}
