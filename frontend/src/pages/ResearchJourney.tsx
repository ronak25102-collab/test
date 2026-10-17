import { useEffect, useRef, useState } from 'react'
import './research-journey.css'

const chapters = [
  { title: 'Find the original evidence.', text: 'Start with a listed financial business and a cutoff date. Beyond searches issuer disclosures, exchange filings and independent context.', label: 'DISCOVER', caption: 'Every investigation starts with an original source.', tags: ['Issuer disclosures', 'Exchange filings', 'Independent context'] },
  { title: 'Connect the numbers.', text: 'Bind each figure to its source, reporting period, unit and scope. Registered formulas turn verified inputs into calculations you can reproduce.', label: 'INVESTIGATE', caption: 'From individual figures to a calculation you can follow.', tags: ['Source-bound facts', 'Comparable periods', 'Reproducible calculations'] },
  { title: 'Challenge the explanation.', text: 'Test the strongest alternative and search for counterevidence. Publish only when the finding survives review; otherwise, show what is still missing.', label: 'VERIFY', caption: 'A finding earns its place by surviving the other side.', tags: ['Alternative explanation', 'Counterevidence search', 'Independent claim review'] },
]

const clamp = (value: number) => Math.min(1, Math.max(0, value))

export function ResearchJourney({ motionPaused }: { motionPaused: boolean }) {
  const trackRef = useRef<HTMLDivElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)
  const [chapter, setChapter] = useState(0)

  useEffect(() => {
    if (motionPaused) return
    const track = trackRef.current
    const stage = stageRef.current
    if (!track || !stage) return
    let frame = 0
    const update = () => {
      frame = 0
      const bounds = track.getBoundingClientRect()
      const inset = Number.parseFloat(getComputedStyle(stage).top) || 0
      const travel = Math.max(1, bounds.height - stage.offsetHeight)
      const progress = clamp((inset - bounds.top) / travel)
      stage.style.setProperty('--scroll-journey-progress', String(progress))
      stage.style.setProperty('--scroll-journey-turn', `${(progress * 110).toFixed(2)}deg`)
      stage.style.setProperty('--scroll-journey-drift', `${((progress - .5) * 40).toFixed(2)}px`)
      // Native scrolling owns the timeline; only chapter boundaries update React.
      const next = Math.min(2, Math.floor(progress * 3))
      setChapter(previous => previous === next ? previous : next)
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update) }
    const resize = new ResizeObserver(schedule)
    resize.observe(track)
    resize.observe(stage)
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule, { passive: true })
    update()
    return () => {
      cancelAnimationFrame(frame)
      resize.disconnect()
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
    }
  }, [motionPaused])

  function selectChapter(index: number) {
    setChapter(index)
    const track = trackRef.current
    const stage = stageRef.current
    if (motionPaused || !track || !stage) return
    const inset = Number.parseFloat(getComputedStyle(stage).top) || 0
    const travel = Math.max(0, track.offsetHeight - stage.offsetHeight)
    const target = scrollY + track.getBoundingClientRect().top - inset + travel * ((index + .45) / 3)
    window.scrollTo({ top: target, behavior: 'smooth' })
  }

  return <div className="scroll-journey-track" ref={trackRef}>
    <div className="scroll-journey-stage" ref={stageRef} data-chapter={chapter}>
      <div className="scroll-journey-heading"><span><i /> FOLLOW THE EVIDENCE</span><span>0{chapter + 1} / 03 <span className="scroll-journey-heading-rule" /> {chapters[chapter].label}</span></div>
      <div className="scroll-journey-copy">
        <span className="scroll-journey-chapter-number" aria-hidden="true">0{chapter + 1}<span> / THE RESEARCH JOURNEY</span></span>
        <div className="method-steps">{chapters.map((item, index) => <div className={`method-step ${chapter === index ? 'active' : ''}`} key={item.label}>
          <button aria-expanded={chapter === index} aria-controls={`step-detail-${index}`} onClick={() => selectChapter(index)}><span>0{index + 1}</span><strong>{item.title}</strong><span className="step-toggle" aria-hidden="true"><i /><i /></span></button>
          <div className="step-detail" id={`step-detail-${index}`} aria-hidden={chapter !== index} inert={chapter !== index}><div><p>{item.text}</p></div></div>
        </div>)}</div>
        <div className="scroll-journey-tags" key={chapter}>{chapters[chapter].tags.map(tag => <span key={tag}>{tag}</span>)}</div>
      </div>
      <div className="scroll-journey-art" aria-hidden="true">
        <div className="scroll-journey-orbits"><span /><span /><span /><i /><i /></div>
        <span className="scroll-journey-art-index">0{chapter + 1}</span>
        <div className={`scroll-journey-art-layer scroll-journey-sources ${chapter === 0 ? 'is-active' : ''}`}>
          <div className="scroll-journey-paper scroll-journey-paper-back"><span>EXCHANGE FILING</span><i /><i /><i /><i /></div>
          <div className="scroll-journey-paper scroll-journey-paper-front"><div className="scroll-journey-paper-head"><span>ORIGINAL DISCLOSURE</span><b>↗</b></div><strong>Every number.<br />A source.</strong><div className="scroll-journey-paper-lines"><i /><i /><i /><i /></div><div className="scroll-journey-highlight"><span /> Exact passage identified</div><small>REPORTING PERIOD · UNIT · SCOPE</small></div>
          <div className="scroll-journey-floating-tag scroll-journey-source-tag"><span>↳</span> Evidence, connected.</div>
        </div>
        <div className={`scroll-journey-art-layer scroll-journey-calculations ${chapter === 1 ? 'is-active' : ''}`}>
          <div className="scroll-journey-input scroll-journey-input-a"><span>VERIFIED INPUT</span><strong>A</strong><small>Original source ↗</small></div>
          <div className="scroll-journey-input scroll-journey-input-b"><span>COMPARABLE INPUT</span><strong>B</strong><small>Matching scope ↗</small></div>
          <svg className="scroll-journey-connectors" viewBox="0 0 420 360" fill="none"><path d="M100 110V160Q100 180 120 180H190M320 110V160Q320 180 300 180H230" /><circle cx="210" cy="180" r="20" /><path d="M210 200V230" /></svg>
          <div className="scroll-journey-formula"><span>REPRODUCIBLE CALCULATION</span><strong>Δ = <span>(B − A)</span> / A</strong><small>Every input has a paper trail.</small></div>
        </div>
        <div className={`scroll-journey-art-layer scroll-journey-verification ${chapter === 2 ? 'is-active' : ''}`}>
          <div className="scroll-journey-review-ring"><svg viewBox="0 0 120 120" fill="none"><circle cx="60" cy="60" r="52" /><path d="m40 60 14 14 28-30" /></svg></div>
          <div className="scroll-journey-review-card"><span>THE OTHER SIDE OF THE STORY</span><strong>Built to question.</strong><div><i>↔</i> Alternative explanation</div><div><i>↗</i> Counterevidence search</div><div><i>✓</i> Independent claim review</div><small>Publish only what survives review.</small></div>
        </div>
        <span className="scroll-journey-art-label">ILLUSTRATIVE PROCESS / EVIDENCE BEFORE EXPLANATION</span>
      </div>
      <div className="scroll-journey-footer"><span className="scroll-journey-scroll-hint">{motionPaused ? 'SELECT A CHAPTER TO EXPLORE' : 'SCROLL TO CONNECT THE DOTS'} <span aria-hidden="true">↓</span></span><div className="scroll-journey-timeline" aria-hidden="true"><span /><i className={chapter === 0 ? 'is-current' : ''} /><i className={chapter === 1 ? 'is-current' : ''} /><i className={chapter === 2 ? 'is-current' : ''} /></div><span className="scroll-journey-caption">{chapters[chapter].caption}</span></div>
    </div>
  </div>
}
