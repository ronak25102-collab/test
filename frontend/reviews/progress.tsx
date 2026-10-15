// Development-only visual review entry. Vite's production entry is index.html.
import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ResearchProgress } from '../src/pages/ResearchProgress'
import { Arrow, BeyondMark } from '../src/pages/Landing'
import type { RunSummary } from '../src/api/generated'
import '../src/styles.css'
import '../src/experience.css'
import '../src/research-progress.css'

const sequence = ['queued', 'resolving', 'planning', 'discovering', 'fetching', 'extracting', 'normalizing', 'hypothesizing', 'investigating', 'challenging', 'verifying', 'composing', 'completed', 'failed', 'cancelled', 'cancel_requested']

function MotionReview() {
  const [stage, setStage] = useState('extracting')
  const [paused, setPaused] = useState(matchMedia('(prefers-reduced-motion: reduce)').matches)
  const current = sequence.indexOf(stage)
  const previous = ['failed', 'cancelled', 'cancel_requested'].includes(stage) ? 'extracting' : stage
  const run: RunSummary = {
    id: 'design-preview', company: { id: 'synthetic-company', legal_name: 'Example financial business', symbols: ['EXAMPLE'], business_profiles: ['bank'] },
    as_of: '2026-10-15', mode: 'replay', status: stage, stage, progress: { sources_found: current > 3 ? 8 : 0, documents_parsed: current > 5 ? 4 : 0, calculations_completed: current > 8 ? 2 : 0, counterevidence_checks: current > 9 ? 1 : 0 },
    limitations: stage === 'failed' ? ['Synthetic interrupted state for visual review.'] : [],
  }
  return <div className={`shell ${paused ? 'motion-paused' : ''}`}>
    <header className="topbar" style={{ gap: 14 }}><a className="brand" style={{ flexShrink: 0 }} href="/" aria-label="Beyond home"><BeyondMark /><span>beyond.</span></a><span className="section-kicker" style={{ flex: 1, minWidth: 0, textAlign: 'center', fontSize: 7, lineHeight: 1.6 }}>DESIGN PREVIEW · SYNTHETIC WORKFLOW · NO API REQUESTS</span><button className="motion-button" style={{ flexShrink: 0 }} aria-label={paused ? 'Enable animations' : 'Pause animations'} onClick={() => setPaused(!paused)}>{paused ? '▷' : 'Ⅱ'}</button></header>
    <main className="workspace-container" style={{ paddingTop: 28 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, alignItems: 'center', marginBottom: 24 }}><label style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 11 }}>Preview stage<select value={stage} onChange={e => setStage(e.target.value)} style={{ width: 'auto' }}>{sequence.map(item => <option key={item} value={item}>{item}</option>)}</select></label><button className="quiet" style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }} onClick={() => setStage(sequence[(current + 1) % sequence.length])}>Next stage <span style={{ display: 'flex', width: 16, height: 16 }}><Arrow /></span></button></div>
      <ResearchProgress run={run} events={[{ sequence: 1, stage: previous, public_summary: 'Illustrative stage for design review. No investigation is running.' }]} onCancel={() => setStage('cancelled')} onResume={() => setStage('queued')} onRestart={() => setStage('queued')} />
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<MotionReview />)
