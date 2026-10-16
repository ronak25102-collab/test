import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { RunSummary } from '../api/generated'
import './run-history.css'

export function RunHistory({ refreshKey }: { refreshKey: string }) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  useEffect(() => {
    let active = true
    api.history().then(data => { if (active) setRuns(Array.isArray(data.items) ? data.items : []) }).catch(() => {})
    return () => { active = false }
  }, [refreshKey])
  if (!runs.length) return null
  return <details className="run-history" aria-label="Saved investigations">
    <summary><span>Saved investigations</span><small>{runs.length} recent runs <span aria-hidden="true">↗</span></small></summary>
    <p>Open the original saved evidence. Start a new investigation to research fresh sources.</p>
    <div className="run-history-grid">{runs.map(run => <a key={run.id} href={`?run=${run.id}`}>
      <span className="history-mode">{run.mode === 'replay' ? 'Synthetic replay' : run.mode === 'deep' ? 'Extended research' : 'Live research'} · {run.cold_start ? 'Cold start' : 'Cache permitted'}</span>
      <strong>{run.company.legal_name}</strong>
      <span>{run.outcome === 'discovery' ? 'Published finding' : run.outcome === 'partial' ? 'Partial · evidence saved' : run.status === 'completed' ? 'Not established' : run.status.replaceAll('_', ' ')}</span>
      <small>Cutoff {run.as_of} · {run.progress.facts_verified || 0} verified facts <span aria-hidden="true">↗</span></small>
    </a>)}</div>
  </details>
}
