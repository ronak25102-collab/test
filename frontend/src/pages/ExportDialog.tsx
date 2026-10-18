import { useEffect, useState } from 'react'
import type { Report } from '../api/generated'
import { API_BASE } from '../api/client'
import { EvidenceModal } from './EvidenceModal'
import { Arrow } from './Landing'

type Format = 'pdf' | 'html' | 'json' | 'csv'
type Status = 'idle' | 'working' | 'done' | 'error'
type Prepared = { blob: Blob; facts: number; calculations: number; documents: number }

const formats: { id: Format; label: string; tag: string; description: string; done: string }[] = [
  { id: 'pdf', label: 'PDF', tag: 'PDF', description: 'Print-ready A4 report. Opens the print view to save as PDF.', done: 'Opened' },
  { id: 'html', label: 'Self-contained HTML', tag: 'HTML', description: 'The full report in one file that opens offline.', done: 'Downloaded' },
  { id: 'json', label: 'JSON', tag: 'JSON', description: 'Structured data: facts, passages, calculations and claims.', done: 'Downloaded' },
  { id: 'csv', label: 'CSV', tag: 'CSV', description: 'Verified facts as a spreadsheet-safe table.', done: 'Downloaded' },
]

// The loading step stays on screen briefly so a fast local export does not flash past unread.
const MIN_PREPARE_MS = 600

const exportUrl = (runId: string, file: string) => `${API_BASE}/api/v1/runs/${runId}/exports/${file}`

async function fetchExport(url: string, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail?.message || body.message || `Export failed (${response.status})`)
  }
  return response.blob()
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  // Give the browser time to start the download before releasing the object URL.
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
}

function filenameFor(report: Report, suffix: string) {
  const company = report.company.legal_name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'report'
  return `beyond-${company}-${report.cutoff}-${suffix}`
}

/** Export popup: generates the report on open, then offers each download format. */
export function ExportDialog({ report, onClose }: { report: Report; onClose: () => void }) {
  const [prepared, setPrepared] = useState<Prepared | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [status, setStatus] = useState<Record<Format, Status>>({ pdf: 'idle', html: 'idle', json: 'idle', csv: 'idle' })
  const [formatError, setFormatError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    setPrepared(null)
    setError('')
    // Start on the next tick: a mount that is immediately torn down (React StrictMode) sends no request.
    const start = window.setTimeout(() => {
      const minimum = new Promise(resolve => window.setTimeout(resolve, MIN_PREPARE_MS))
      Promise.all([fetchExport(exportUrl(report.run_id, 'report.json'), controller.signal), minimum])
        .then(async ([blob]) => {
          const data = JSON.parse(await blob.text()) as Partial<Report>
          if (!controller.signal.aborted) setPrepared({ blob, facts: data.facts?.length ?? 0, calculations: data.calculations?.length ?? 0, documents: data.documents?.length ?? 0 })
        })
        .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'The report could not be generated.') })
    }, 0)
    return () => { window.clearTimeout(start); controller.abort() }
  }, [report.run_id, attempt])

  const run = async (format: Format) => {
    if (!prepared) return
    setFormatError('')
    setStatus(current => ({ ...current, [format]: 'working' }))
    try {
      if (format === 'pdf') window.open(`?run=${report.run_id}&print=1&autoprint=1`, '_blank', 'noopener')
      else if (format === 'json') saveBlob(prepared.blob, filenameFor(report, 'report.json'))
      else if (format === 'html') saveBlob(await fetchExport(exportUrl(report.run_id, 'report.html')), filenameFor(report, 'report.html'))
      else saveBlob(await fetchExport(exportUrl(report.run_id, 'facts.csv')), filenameFor(report, 'facts.csv'))
      setStatus(current => ({ ...current, [format]: 'done' }))
    } catch (reason) {
      setStatus(current => ({ ...current, [format]: 'error' }))
      setFormatError(reason instanceof Error ? reason.message : 'This format could not be generated.')
    }
  }

  return <EvidenceModal className="export-modal" label="Export report" kicker="EXPORT REPORT" closeLabel="Close export" onClose={onClose}>
    {!prepared && !error && <div className="export-preparing" role="status" aria-live="polite">
      <span className="export-spinner" aria-hidden="true" />
      <h2>Generating your report</h2>
      <p>Assembling verified figures, calculations and sources for {report.company.legal_name}.</p>
      <div className="export-progress" aria-hidden="true"><span /></div>
    </div>}
    {error && <div className="export-preparing export-failed" role="alert">
      <h2>The report could not be generated</h2>
      <p>{error}</p>
      <button className="quiet" onClick={() => setAttempt(value => value + 1)}>Try again</button>
    </div>}
    {prepared && <>
      <div className="export-ready" role="status">
        <h2>Your report is ready</h2>
        <div className="export-meta">
          <p>{report.company.legal_name} · Cutoff {report.cutoff}</p>
          <ul className="export-summary">
            <li><strong>{prepared.facts}</strong> verified facts</li>
            <li><strong>{prepared.calculations}</strong> calculations</li>
            <li><strong>{prepared.documents}</strong> sources</li>
          </ul>
        </div>
      </div>
      <h3 className="export-choose">Choose a format</h3>
      <ul className="export-formats">{formats.map(format => {
        const state = status[format.id]
        return <li key={format.id}><button className={`export-format export-${state}`} onClick={() => run(format.id)} disabled={state === 'working'} aria-describedby={`export-${format.id}-description`}>
          <span className="export-tag" aria-hidden="true">{format.tag}</span>
          <span className="export-text">
            <span className="export-title"><strong>{format.label}</strong><span className="export-action">{state === 'working' ? <><span className="export-spinner small" aria-hidden="true" />Generating</> : state === 'done' ? <>✓ {format.done}</> : state === 'error' ? 'Retry' : <>{format.id === 'pdf' ? 'Open' : 'Download'} <Arrow diagonal /></>}</span></span>
            <small id={`export-${format.id}-description`}>{format.description}</small>
          </span>
        </button></li>
      })}</ul>
      {formatError && <p className="export-error" role="alert">{formatError}</p>}
    </>}
  </EvidenceModal>
}
