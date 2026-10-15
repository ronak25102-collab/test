import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

export function QueueControls({ onCleared }: { onCleared: () => void }) {
  const [count, setCount] = useState<number | null>(null)
  const [clearing, setClearing] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [statusError, setStatusError] = useState('')
  const [revision, setRevision] = useState(0)
  const clearingRef = useRef(false)
  const mounted = useRef(false)

  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  useEffect(() => {
    let active = true
    let timer: number | undefined
    const refresh = async () => {
      try {
        const result = await api.queue()
        if (!Number.isInteger(result.queued_count) || result.queued_count < 0) throw new Error('Queue status is unavailable.')
        if (active && !clearingRef.current) { setCount(result.queued_count); setStatusError('') }
      } catch {
        if (active && !clearingRef.current) { setCount(null); setStatusError('Queue status is unavailable.') }
      } finally {
        if (active) timer = window.setTimeout(refresh, 5000)
      }
    }
    refresh()
    return () => { active = false; window.clearTimeout(timer) }
  }, [revision])

  async function clear() {
    if (clearingRef.current || !count) return
    clearingRef.current = true
    setClearing(true); setError(''); setMessage('')
    try {
      const result = await api.clearQueue()
      if (!mounted.current) return
      setMessage(result.cancelled_count === 0 ? 'No waiting runs to clear.' : `${result.cancelled_count} waiting ${result.cancelled_count === 1 ? 'run' : 'runs'} cancelled. Saved work is available to resume.`)
      onCleared()
    } catch (err) {
      if (mounted.current) setError((err as Error).message)
    } finally {
      clearingRef.current = false
      if (mounted.current) { setClearing(false); setRevision(v => v + 1) }
    }
  }

  return <section className="queue-controls" aria-label="Research queue">
    <div className="queue-actions"><span className="queue-count">{count === null ? 'Research queue' : `${count} waiting ${count === 1 ? 'run' : 'runs'}`}</span><button className="quiet" onClick={clear} disabled={clearing || count === null || count === 0}>{clearing ? 'Clearing queue…' : 'Clear queue'}</button></div>
    <small>Active research continues. Only waiting runs are cancelled.</small>
    <div className="queue-feedback" aria-live="polite">{error || statusError ? <p className="queue-error">{error || statusError} <button className="queue-retry" onClick={() => error ? clear() : setRevision(v => v + 1)} disabled={clearing}>Retry</button></p> : message && <p>{message}</p>}</div>
  </section>
}
