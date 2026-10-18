import { type CSSProperties, type ReactNode, useEffect, useId, useRef, useState } from 'react'
import { ResearchJourney } from './ResearchJourney'
import { FinanceBackdrop } from './FinanceBackdrop'

export function BeyondMark() {
  return <svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M7 5v22h9a8 8 0 1 0 0-16h-3V5H7Z" fill="currentColor"/><path d="M13 17h3a2 2 0 1 1 0 4h-3v-4Z" fill="var(--paper, #f6f5ef)"/><path d="m20 3 6 6m0-6-6 6" stroke="currentColor" strokeWidth="2"/></svg>
}

export function Arrow({ diagonal = false }: { diagonal?: boolean }) {
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d={diagonal ? 'M6 18 18 6M6 6h12v12' : 'M4 12h15m-6-6 6 6-6 6'} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>
}

function HeadingLine({ children, muted = false }: { children: ReactNode; muted?: boolean }) {
  return <span className={`scroll-heading-line${muted ? ' is-muted' : ''}`}><span className="scroll-heading-text">{children}</span></span>
}

const researchAngles = [
  { title: 'Growth & asset quality', question: 'Are loan growth and asset quality telling different stories?', detail: 'Compare lending growth with non-performing assets and provisions. Check whether reporting scope or portfolio changes offer another explanation.', sources: 'Financial results · Asset-quality disclosures · Peer context' },
  { title: 'Funding mix', question: 'What changed in the way the business funds itself?', detail: 'Investigate deposits, borrowings and funding composition over comparable periods. Trace when a change emerged and what evidence could explain it.', sources: 'Annual reports · Borrowing notes · Management commentary' },
  { title: 'Financial dependencies', question: 'Which relationships sit behind the headline numbers?', detail: 'Follow disclosed banking, co-lending and funding relationships. Connect issuer filings with independently originated evidence before drawing a conclusion.', sources: 'Exchange filings · Partner disclosures · Independent context' },
]

function ProductPreview() {
  const [tab, setTab] = useState('Overview')
  const [source, setSource] = useState(false)
  const [period, setPeriod] = useState('FY26')
  const chartGradient = useId()
  const values = period === 'FY26' ? [82, 88, 86, 94, 93, 100, 98, 108, 105, 114, 112, 120] : [68, 72, 71, 77, 76, 82, 80, 87, 85, 93, 91, 100]
  const months = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar']
  const linePoints = values.map((value, i) => `${50 + i * 100},${140 - value}`).join(' ')
  return <div className="preview-window">
    <div className="preview-sidebar"><span className="preview-symbol"><BeyondMark /></span><span className="preview-nav-icon active">▦</span><span className="preview-nav-icon">⌕</span><span className="preview-nav-icon">◫</span><span className="preview-nav-icon">↗</span><span className="preview-sidebar-bottom">b.</span></div>
    <div className="preview-content">
      <div className="preview-topline"><span><span className="tiny-dot" /> Research overview</span><span className="preview-demo">ILLUSTRATIVE DEMO</span></div>
      <div className="preview-title"><div><span className="micro-label">BANKING & FINANCIAL SERVICES</span><h3>Every number. A source.</h3></div><span className="preview-avatar">B</span></div>
      <div className="preview-tabs" role="tablist" aria-label="Research preview" style={{ '--selected-index': ['Overview', 'Evidence', 'Challenge'].indexOf(tab) } as CSSProperties}>
        <span className="preview-tab-indicator" aria-hidden="true" />
        {['Overview', 'Evidence', 'Challenge'].map((item, index, items) => <button key={item} id={`preview-tab-${item}`} role="tab" tabIndex={tab === item ? 0 : -1} aria-selected={tab === item} aria-controls="preview-panel" onClick={() => setTab(item)} onKeyDown={e => {
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
          e.preventDefault()
          const next = e.key === 'Home' ? 0 : e.key === 'End' ? items.length - 1 : (index + (e.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length
          setTab(items[next]); document.getElementById(`preview-tab-${items[next]}`)?.focus()
        }}>{item}</button>)}
      </div>
      <div id="preview-panel" className="preview-panel" role="tabpanel" aria-labelledby={`preview-tab-${tab}`} tabIndex={0} key={tab}>
        {tab === 'Overview' && <><div className="preview-metric"><div><span className="micro-label">SYNTHETIC LOAN-BOOK INDEX</span><strong>{period === 'FY26' ? '120.0' : '100.0'} <small>index points</small></strong></div><div className="period-switch" aria-label="Preview year">{['FY25', 'FY26'].map(year => <button key={year} aria-pressed={period === year} onClick={() => setPeriod(year)}>{year}</button>)}</div></div>
          <div className="preview-chart" role="figure" aria-label={`Illustrative ${period} loan-book index, synthetic values, line chart`}>
            <div className="chart-y-axis" aria-hidden="true">{[0, 40, 80, 120].map(tick => <span key={tick} style={{ bottom: `${tick / 140 * 100}%` }}>{tick}</span>)}</div>
            <div className="chart-plot"><div className="chart-grid" aria-hidden="true">{[0, 40, 80, 120].map(tick => <span key={tick} style={{ bottom: `${tick / 140 * 100}%` }} />)}</div>
              <svg className="chart-line-svg" viewBox="0 0 1200 140" preserveAspectRatio="none" aria-hidden="true" key={period}>
                <defs><linearGradient id={chartGradient} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#7d9f68" stopOpacity=".22" /><stop offset="100%" stopColor="#7d9f68" stopOpacity="0" /></linearGradient></defs>
                <polygon className="chart-line-area" points={`50,140 ${linePoints} 1150,140`} fill={`url(#${chartGradient})`} />
                <polyline className="chart-line-path" points={linePoints} pathLength="1" fill="none" stroke="#315b3e" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
              </svg>
              {values.map((value, i) => <button type="button" className="chart-point" key={months[i]} aria-label={`${months[i]} ${period}: ${value} index points, synthetic`} style={{ '--point-height': `${value / 140 * 100}%` } as CSSProperties}><span className={`chart-point-dot ${i === 11 ? 'chart-point-latest' : ''}`} /><span className="chart-tooltip" aria-hidden="true"><strong>{months[i]} · {period}</strong>{value.toFixed(1)} index points</span></button>)}
            </div>
            <div className="chart-axis" aria-hidden="true">{months.map((month, i) => <span key={month} className={i % 3 === 0 || i === 11 ? 'quarter-label' : ''}>{month}</span>)}</div>
          </div><div className="preview-bottom"><span><i className="tiny-dot" /> Traceable financial inputs</span><span>Filing → fact → calculation</span></div></>}
        {tab === 'Evidence' && <div className="preview-detail"><span className="micro-label">FOLLOW THE EVIDENCE</span><h4>A figure is only the beginning.</h4><p>Inspect the source, reporting period and scope behind every verified input.</p><button className="preview-source" onClick={() => setSource(!source)} aria-expanded={source} aria-controls="source-example"><span>↳ &nbsp; Example source passage</span><span>{source ? '−' : '+'}</span></button><div className="source-excerpt" id="source-example" data-open={source} aria-hidden={!source} inert={!source}><div><blockquote>Synthetic example: the loan-book index increased from 100 to 120 across comparable annual periods. This is illustrative data, not a company filing.</blockquote></div></div></div>}
        {tab === 'Challenge' && <div className="preview-detail"><span className="micro-label">THE OTHER SIDE OF THE STORY</span><h4>What if the explanation is wrong?</h4><p>Loan growth alone does not establish asset quality. Check non-performing assets, provisions and scope changes before drawing a conclusion.</p><div className="challenge-note"><span>↗</span><div><strong>A question, not a conclusion.</strong><small>More evidence is needed before publication.</small></div></div></div>}
      </div>
    </div>
  </div>
}

export function Landing({ onLaunch, motionPaused }: { onLaunch: () => void; motionPaused: boolean }) {
  const root = useRef<HTMLDivElement>(null)
  const [angle, setAngle] = useState(0)
  useEffect(() => {
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('is-revealed'); observer.unobserve(entry.target) }
    }), { threshold: 0.12 })
    root.current?.querySelectorAll('.reveal').forEach(el => observer.observe(el))
    const scenes = new IntersectionObserver(entries => entries.forEach(entry => {
      entry.target.classList.toggle('is-in-view', entry.isIntersecting)
    }), { threshold: 0 })
    root.current?.querySelectorAll('.motion-scene').forEach(el => scenes.observe(el))
    return () => { observer.disconnect(); scenes.disconnect() }
  }, [])
  return <div className="landing" ref={root}>
    <section className="landing-hero motion-scene" id="platform" aria-labelledby="hero-heading">
      <FinanceBackdrop />
      <div className="hero-copy"><h1 id="hero-heading"><span className="hero-line hero-line-muted"><span>Find the next signal.</span></span>{' '}<span className="hero-line"><span>Beyond the numbers.</span></span></h1><p>Investigate banks, NBFCs and financial services.<br />Connect public filings. Test the story behind the numbers.</p><div className="hero-actions"><button className="button-dark" onClick={onLaunch}>Start your research <Arrow /></button><a className="text-link" href="#how-it-works">Explore the process <span>↓</span></a></div><span className="hero-footnote">Independent evidence. Reproducible calculations. Challenged conclusions.</span></div>
      <div className="hero-product" onPointerMove={e => {
        if (motionPaused || e.pointerType !== 'mouse' || matchMedia('(prefers-reduced-motion: reduce)').matches) return
        const interactive = (e.target as HTMLElement).closest('button, a, [role="tabpanel"]')
        const box = e.currentTarget.getBoundingClientRect()
        e.currentTarget.style.setProperty('--tilt-x', interactive ? '0deg' : `${(e.clientY - box.top - box.height / 2) / -240}deg`)
        e.currentTarget.style.setProperty('--tilt-y', interactive ? '0deg' : `${(e.clientX - box.left - box.width / 2) / 300}deg`)
      }} onPointerLeave={e => { e.currentTarget.style.setProperty('--tilt-x', '0deg'); e.currentTarget.style.setProperty('--tilt-y', '0deg') }}><div className="floating-label label-source"><span className="label-check">✓</span><div><strong>Evidence, connected.</strong><small>From original source to insight</small></div></div><ProductPreview /><div className="floating-label label-review"><span className="review-orbit">✳</span><div><strong>Built to question.</strong><small>Counterevidence comes first.</small></div></div></div>
      <div className="hero-caption"><span>BEYOND / THE FINANCIAL RESEARCH WORKBENCH</span><a href="#how-it-works">Scroll to discover <span>↓</span></a><span>FINDING THE NEXT SIGNAL</span></div>
    </section>
    <section className="principle-strip" aria-label="Research principles"><span>Research with a paper trail.</span><div><span>Original disclosures</span><span className="strip-star">✳</span><span>Independent context</span><span className="strip-star">✳</span><span>Verifiable calculations</span></div></section>
    <section className="finance-angles section-width" aria-labelledby="angles-heading"><div className="angles-intro reveal"><span className="section-kicker">BANKING, NBFCS & FINANCIAL SERVICES</span><h2 id="angles-heading"><HeadingLine>Look where the</HeadingLine>{" "}<HeadingLine>financial story changes.</HeadingLine></h2><p>Starting points for investigation, not prewritten findings.</p></div><div className="angle-explorer reveal"><div className="angle-select" aria-label="Financial research angles" style={{ '--selected-index': angle } as CSSProperties}>{researchAngles.map((item, i) => <button key={item.title} aria-pressed={angle === i} aria-controls="angle-panel" onClick={() => setAngle(i)}><span>0{i + 1}</span>{item.title}<Arrow diagonal /></button>)}</div><div className="angle-panel" id="angle-panel" aria-live="polite" key={angle}><span className="micro-label">THE RESEARCH QUESTION</span><h3>{researchAngles[angle].question}</h3><p>{researchAngles[angle].detail}</p><div className="angle-sources"><span>FOLLOW THE EVIDENCE</span><p>{researchAngles[angle].sources}</p></div></div></div></section>
    <section className="method-section section-width" id="how-it-works"><div className="section-heading reveal"><span className="section-kicker">01 / THE PROCESS</span><h2><HeadingLine>From scattered sources</HeadingLine>{" "}<HeadingLine>to a sharper perspective.</HeadingLine></h2><p>One investigation. A complete evidence trail.<br />Explore how Beyond connects the dots.</p></div><ResearchJourney motionPaused={motionPaused} /></section>
    <section className="why-section" id="why-beyond"><div className="section-width"><div className="why-heading reveal"><span className="section-kicker">02 / A HIGHER STANDARD</span><h2><HeadingLine>Good research shows its work.</HeadingLine>{" "}<HeadingLine muted>Great research questions it.</HeadingLine></h2></div><div className="belief-grid"><article className="belief reveal"><span className="belief-icon">↳</span><h3>Follow the fact.</h3><p>Open the original passage behind a figure. See its reporting period, unit and financial scope.</p><span className="belief-tag">SOURCE PROVENANCE</span></article><article className="belief reveal"><span className="belief-icon">±</span><h3>Check the arithmetic.</h3><p>Inspect registered formulas and the verified inputs behind each reproducible calculation.</p><span className="belief-tag">REPRODUCIBLE REASONING</span></article><article className="belief reveal"><span className="belief-icon">⇄</span><h3>Consider the alternative.</h3><p>Read the strongest counterargument. When evidence falls short, see exactly what is missing.</p><span className="belief-tag">HONEST UNCERTAINTY</span></article></div></div></section>
    <section className="landing-end section-width reveal"><span className="section-kicker">YOUR NEXT QUESTION STARTS HERE</span><h2><HeadingLine>There’s more to</HeadingLine>{" "}<HeadingLine><em>the story.</em></HeadingLine></h2><p>Choose a financial business.<br />Let the evidence lead the way.</p><button className="button-dark" onClick={onLaunch}>Open the workbench <Arrow /></button><span className="end-watermark" aria-hidden="true">beyond.</span></section>
  </div>
}
