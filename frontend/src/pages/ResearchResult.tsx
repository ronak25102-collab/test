import { type CSSProperties, useEffect, useId, useRef, useState } from 'react'
import type { Fact, Passage, Report } from '../api/generated'
import { type ReportSection, routeHref } from '../appRoute'
import { TimelineStory } from './TimelineStory'
import { PeerComparison } from './PeerComparison'
import { API_BASE } from '../api/client'
import { Arrow } from './Landing'
import { ResearchAudit } from './ResearchAudit'
import { ChallengeTrail, SubmissionBrief } from './SubmissionBrief'
import { calculationFormulas, displayMetric, displayNumber, displayResearchGap, displayUnit } from './format'

// Slide PDFs extract rotated side labels as stray letters ("s", "t if", "c n t e Total Assets").
// The quote stays verbatim in the DOM; fragments are only hidden from view until requested.
const FRAGMENT_LINE = /^[A-Za-z]{1,2}(?: [A-Za-z]{1,2})*$/
const FRAGMENT_PREFIX = /^((?:[A-Za-z]{1,2} )+)(?=[A-Z][A-Za-z])/

function SourcePassage({ passage, figure }: { passage: Passage; figure?: string }) {
  const [showFragments, setShowFragments] = useState(false)
  const lines = passage.text.split('\n')
  // Only slide pages with several stray-letter lines are treated as having rotated labels.
  const slideLayout = lines.filter(line => FRAGMENT_LINE.test(line.trim())).length >= 3
  let fragments = 0
  const mark = (text: string) => {
    if (!figure || !text.includes(figure)) return text
    const [before, ...rest] = text.split(figure)
    return <>{before}<mark>{figure}</mark>{rest.join(figure)}</>
  }
  const rendered = lines.map((line, index) => {
    const newline = index < lines.length - 1 ? '\n' : ''
    if (slideLayout && FRAGMENT_LINE.test(line.trim())) {
      fragments++
      return <span key={index} className="passage-fragment">{line}{newline}</span>
    }
    const prefix = slideLayout ? FRAGMENT_PREFIX.exec(line)?.[1] : undefined
    if (prefix) fragments++
    return <span key={index} className={figure && line.includes(figure) ? 'passage-match' : undefined}>{prefix && <span className="passage-fragment">{prefix}</span>}{mark(prefix ? line.slice(prefix.length) : line)}{newline}</span>
  })
  const hashName = /^[0-9a-f]{64}\.pdf$/i.test(passage.section || '')
  const meta = [hashName ? undefined : passage.section, passage.page_index != null ? `Page ${passage.page_index + 1}` : undefined, passage.row_label, passage.column_label].filter(Boolean).join(' · ')
  return <section className="inspector-passage">
    <h3>Exact source passage</h3>
    {meta && <p>{meta}</p>}
    <blockquote className={showFragments ? 'show-fragments' : undefined}>{rendered}</blockquote>
    {fragments > 0 && <div className="passage-note"><span>Extracted verbatim from the PDF page. Rotated slide labels leave stray letters, hidden here.</span><button type="button" aria-pressed={showFragments} onClick={() => setShowFragments(value => !value)}>{showFragments ? 'Hide layout fragments' : `Show layout fragments (${fragments})`}</button></div>}
  </section>
}

function SourceInspector({ fact, report, onClose }: { fact: Fact; report: Report; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const passage = report.passages.find(item => item.id === fact.passage_id)
  const source = report.documents.find(item => item.id === passage?.document_id)
  useEffect(() => { const dialog = ref.current; const previous = document.activeElement as HTMLElement | null; dialog?.showModal(); return () => { if (dialog?.open) dialog.close(); previous?.focus({ preventScroll: true }) } }, [])
  return <dialog ref={ref} className="source-inspector" aria-label="Verified figure evidence" onCancel={event => { event.preventDefault(); onClose() }} onClick={event => { if (event.target === event.currentTarget) { const rect = event.currentTarget.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose() } }}>
    <div className="inspector-top"><span className="section-kicker">THE FIGURE & ITS SOURCE</span><button className="close" onClick={onClose} aria-label="Close source evidence">×</button></div>
    <h2>{displayMetric(fact.metric_key)}</h2><div className="inspector-number">{displayNumber(fact.value_decimal)}<span>{displayUnit(fact.unit_normalized)}</span></div>
    <div className="inspector-metadata"><span>Reporting date<strong>{fact.period_end || 'Not specified'}</strong></span><span>Scope<strong>{fact.scope} · {fact.segment || 'all'}</strong></span><span>Definition<strong>{fact.definition_id || 'Issuer reported'}</strong></span><span>Original unit<strong>{fact.unit_raw || 'Not specified'}</strong></span></div>
    {source && <div className="inspector-source"><span className="section-kicker">ORIGINAL DOCUMENT</span><h3>{source.title}</h3><p>{source.publisher} · {source.published_at ? `Published ${source.published_at.slice(0, 10)}` : source.cutoff_eligibility_basis === 'verified_retrieval' ? `Public availability verified ${source.retrieved_at?.slice(0, 10) || 'by retrieval receipt'}` : 'Publication date unknown'}</p><a href={source.canonical_url} target="_blank" rel="noreferrer">Open original source{passage?.page_index != null ? ` · page ${passage.page_index + 1}` : ''}<Arrow diagonal /></a></div>}
    {passage ? <SourcePassage passage={passage} figure={fact.value_raw} /> : <p>No source passage is available for this figure.</p>}
  </dialog>
}

function SourceLibrary({ report }: { report: Report }) {
  const [search, setSearch] = useState('')
  const [type, setType] = useState('All sources')
  const supportingIds = new Set(report.passages.filter(p => report.facts.some(f => f.passage_id === p.id)).map(p => p.document_id))
  const documents = report.documents.filter(document => (type !== 'Issuer filings' || document.document_type.startsWith('issuer')) && (type !== 'Supporting figures' || supportingIds.has(document.id)) && `${document.title} ${document.publisher} ${document.canonical_url}`.toLowerCase().includes(search.toLowerCase()))
  return <section className="report-section" id="report-sources" aria-labelledby="sources-heading"><div className="report-section-title"><div><span className="section-kicker">04 / THE PAPER TRAIL</span><h3 id="sources-heading">Source library</h3></div><span>{report.documents.length} retrieved documents</span></div>
    <div className="source-toolbar"><div className="source-filters" aria-label="Filter source type">{['All sources', 'Issuer filings', 'Supporting figures'].map(item => <button key={item} aria-pressed={item === type} onClick={() => setType(item)}>{item}</button>)}</div><label className="report-search"><span>Search sources</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Title, publisher or domain" /></label></div>
    <div className="source-count" aria-live="polite">{documents.length} of {report.documents.length} documents shown · Retrieved context is distinct from evidence supporting a verified figure.</div>
    <div className="source-library">{documents.map((source, index) => <article className="source-record" key={source.id}><span className="source-record-number">{String(index + 1).padStart(2, '0')}</span><div><div className="source-record-tags"><span>{source.document_type === 'issuer_mirror' ? 'Third-party mirror · issuer origin' : source.document_type.startsWith('issuer') ? 'Issuer disclosure' : 'Public context'}</span><span className={supportingIds.has(source.id) ? 'source-supporting' : ''}>{supportingIds.has(source.id) ? 'Supports verified figures' : 'Retrieved context'}</span>{source.cutoff_eligibility !== 'eligible' && <span className="source-unavailable">{source.cutoff_eligibility.replaceAll('_', ' ')}</span>}</div><a href={source.canonical_url} target="_blank" rel="noreferrer">{source.title || source.publisher}<Arrow diagonal /></a><p>{source.publisher} · {source.published_at?.slice(0, 10) || (source.cutoff_eligibility_basis === 'verified_retrieval' ? `Availability verified ${source.retrieved_at?.slice(0, 10) || 'by receipt'}` : 'Publication date unknown')}</p></div></article>)}</div>
    {!documents.length && <div className="report-empty"><span>No sources match these filters.</span><button className="quiet" onClick={() => { setSearch(''); setType('All sources') }}>Reset source filters</button></div>}
  </section>
}

function ReportExport({ report }: { report: Report }) {
  return <details className="report-export"><summary>Export report <span>↗</span></summary><div><a href={`${API_BASE}/api/v1/runs/${report.run_id}/exports/report.html`}>Self-contained HTML</a><a href={`?run=${report.run_id}&print=1`}>Print / Save as PDF</a><a href={`${API_BASE}/api/v1/runs/${report.run_id}/exports/report.json`}>JSON</a><a href={`${API_BASE}/api/v1/runs/${report.run_id}/exports/facts.csv`}>CSV</a></div></details>
}

export function ResearchResult({ report, onClaim, section, onNavigate }: { report: Report; onClaim: (id: string) => void; section: ReportSection; onNavigate: (section: ReportSection) => void }) {
  const discovery = report.discoveries[0]
  const [search, setSearch] = useState('')
  const [scope, setScope] = useState('All scopes')
  const [selectedFact, setSelectedFact] = useState<Fact | null>(null)
  const [showAdditionalCalculations, setShowAdditionalCalculations] = useState(false)
  const root = useRef<HTMLElement>(null)
  const id = useId()
  const nav: [ReportSection, string][] = [['overview', 'Overview'], ['figures', 'Verified figures'], ['calculations', 'Calculations'], ['sources', 'Sources'], ['review', 'Review']]
  const filteredFacts = report.facts.filter(fact => (scope === 'All scopes' || fact.scope === scope) && `${fact.metric_key.replaceAll('_', ' ')} ${fact.period_end} ${fact.scope} ${fact.segment || ''}`.toLowerCase().includes(search.toLowerCase()))
  const scopes = [...new Set(report.facts.map(fact => fact.scope))]
  const findingCalculationIds = new Set(discovery?.calculation_ids || [])
  const displayedCalculations = discovery && !showAdditionalCalculations ? report.calculations.filter(c => findingCalculationIds.has(c.id)) : report.calculations
  const origins = new Set(report.documents.filter(document => document.cutoff_eligibility === 'eligible').map(document => document.origin_family_id)).size

  useEffect(() => { setSelectedFact(null) }, [section])

  useEffect(() => {
    const element = root.current
    if (!element) return
    const navigation = element.querySelector<HTMLElement>('.report-navigation')
    const currentLink = navigation?.querySelector<HTMLElement>('[aria-current="page"]')
    const centerCurrentPage = () => {
      if (navigation && currentLink) navigation.scrollLeft = Math.max(0, currentLink.offsetLeft - (navigation.clientWidth - currentLink.offsetWidth) / 2)
    }
    centerCurrentPage()
    const resize = new ResizeObserver(centerCurrentPage)
    if (navigation) resize.observe(navigation)
    const observer = new IntersectionObserver(entries => entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('report-in-view'); observer.unobserve(entry.target) } }), { threshold: .04 })
    element.querySelectorAll('.report-reveal').forEach(section => observer.observe(section))
    return () => { observer.disconnect(); resize.disconnect() }
  }, [report.run_id, section])

  // Strength trace and arithmetic sit inside the finding card so every run shares one hero layout.
  const heroDetails = <>
    {report.generation_metadata?.strength_trace && <details className="strength-trace"><summary>{report.generation_metadata.strength_trace.rating} · evidence strength rule trace</summary><ul>{Object.entries(report.generation_metadata.strength_trace.rules).map(([rule, passed]) => <li key={rule}>{passed ? '✓' : '○'} {rule.replaceAll('_', ' ')}</li>)}</ul>{report.generation_metadata.strength_trace.caps.map(cap => <p key={cap}>{cap}</p>)}<small>{report.generation_metadata.strength_trace.note}</small></details>}
    {report.generation_metadata?.headline && <details className="technical-detail"><summary>Technical detail and arithmetic</summary><p>{report.generation_metadata.headline.technical_detail}</p><button onClick={() => onClaim(report.generation_metadata!.headline!.technical_claim_id)}>Inspect technical evidence ↗</button></details>}
  </>
  return <section className={`result-card report-dashboard ${discovery ? 'report-published' : 'report-withheld'}`} ref={root} data-report-page={section} aria-label={`${report.company.legal_name} research report`} tabIndex={-1}>
    <div className="report-export-slot"><ReportExport report={report} /></div>
    <nav className="report-navigation" aria-label="Report sections">{nav.map(([key, label], index) => <a key={key} href={routeHref({ view: 'report', runId: report.run_id, section: key })} aria-current={section === key ? 'page' : undefined} onClick={event => { if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(key) } }}><span>0{index + 1}</span>{label}</a>)}</nav>
    {section === 'overview' && <>
    <header className="report-hero"><div className="report-hero-top"><span className="report-eyebrow">{discovery ? 'PRIMARY DISCOVERY' : report.outcome === 'partial' ? 'PARTIAL RESEARCH' : 'RESEARCH COMPLETE'}<span> / {String(report.source_coverage.mode || 'mode unrecorded').toUpperCase()}</span></span></div>
      <div className="report-company"><span>{report.company.symbols.join(' · ')}</span><span>Cutoff {report.cutoff}</span>{report.source_coverage.synthetic === true && <span>Synthetic replay</span>}</div>
      <h2>{discovery ? 'Discovery published' : report.facts.length ? 'Verified evidence collected' : report.outcome === 'partial' ? 'Investigation incomplete' : 'More evidence needed'}</h2>
      {discovery
        ? <section className="best-candidate hero-finding"><strong>Published discovery · {discovery.evidence_strength} evidence</strong><h3>{discovery.discovery_sentence}</h3>{heroDetails}</section>
        : report.generation_metadata?.best_candidate
          ? <section className="best-candidate"><strong>Not established · best research candidate</strong><p>{report.generation_metadata.best_candidate.text}</p><p>{report.generation_metadata.best_candidate.reason}</p><ul>{report.generation_metadata.best_candidate.missing.map(item => <li key={item}>{displayResearchGap(item)}</li>)}</ul><small>This is an unverified candidate, not a published finding.</small>{heroDetails}</section>
          : heroDetails}
      <p className="report-hero-description">{discovery?.strength_rationale || (report.facts.length ? `${report.facts.length} verified facts from ${report.documents.length} documents. A primary discovery remains withheld until independent evidence supports it.` : report.outcome === 'partial' ? 'Research ended before verification finished. No verified financial figures were established; this incomplete investigation does not support a conclusion about the company.' : 'The available sources did not establish a supported finding.')}</p>
      <div className="report-verdict"><span className={`report-verdict-mark ${discovery ? '' : 'verdict-withheld'}`}>{discovery ? '↗' : '◌'}</span><span><span>{discovery ? `${discovery.evidence_strength} evidence` : 'Finding withheld'}</span><small>{discovery ? 'Open the evidence behind the finding' : report.facts.length ? 'Verified figures remain available for inspection' : 'No verified figures were established'}</small></span><span className="report-run-id">{report.company.legal_name}<small>Cutoff {report.cutoff}</small></span></div>
    </header>
    {report.outcome === 'partial' && <p role="status" className="report-partial">Research stopped before discovery verification finished. See source access and coverage details for the reason. Further investigation needs a new run.</p>}
    <div className="report-stat-grid">{[[report.facts.length, 'Verified facts', 'Source-bound figures'], [report.calculations.length, 'Calculations', 'Reproducible arithmetic'], [report.documents.length, 'Documents', 'Retrieved sources'], [origins, 'Source families', 'Available by cutoff']].map(([value, label, caption], index) => <div className="report-stat" key={label} style={{ '--stat-delay': `${index * 70}ms` } as CSSProperties}><span>0{index + 1} / {label}</span><strong>{value}</strong><small>{caption}</small></div>)}</div>
    </>}

    <div className="report-body">
      {section === 'overview' && <>
      <section className="report-section report-reveal" id="report-overview" aria-labelledby={`${id}-overview`}><div className="report-section-title"><div><span className="section-kicker">01 / A CLEARER VIEW</span><h3 id={`${id}-overview`}>The evidence at a glance.</h3></div><span>{report.company.legal_name}</span></div>
        {discovery && <div className="report-why"><h3>Why it matters</h3><ul className="linked-list">{discovery.why_it_matters.map(item => <li key={item.claim_id}><button onClick={() => onClaim(item.claim_id)}>{item.text}<Arrow diagonal /></button></li>)}</ul></div>}
        <ResearchAudit report={report} onFact={setSelectedFact} />
        <PeerComparison report={report} />
        <TimelineStory report={report} onFact={setSelectedFact} />
        {report.generation_metadata?.temporal_reasoning && <section className="report-why report-temporal"><h3>When the relationship emerged</h3><p>{report.generation_metadata.temporal_reasoning.text}</p><p className="muted">Onset: {report.generation_metadata.temporal_reasoning.onset_status}</p><button onClick={() => onClaim(report.generation_metadata!.temporal_reasoning!.claim_id)}>Inspect timeline evidence <Arrow diagonal /></button></section>}
      </section>
      </>}
      {section === 'figures' && <>
      <section className="report-section report-reveal" id="report-figures" aria-labelledby={`${id}-figures`}><div className="report-section-title"><div><span className="section-kicker">02 / SOURCE-BOUND FIGURES</span><h3 id={`${id}-figures`}>Verified source figures</h3></div><span>{report.facts.length} figures to explore</span></div>
        <div className="figure-toolbar"><label className="report-search"><span>Filter verified figures</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Find a metric, period or segment" /></label><label className="scope-filter"><span>Financial scope</span><select value={scope} onChange={event => setScope(event.target.value)}><option>All scopes</option>{scopes.map(item => <option key={item}>{item}</option>)}</select></label>{(search || scope !== 'All scopes') && <button className="quiet" onClick={() => { setSearch(''); setScope('All scopes') }}>Reset filters</button>}</div>
        <p className="figure-count" aria-live="polite">{filteredFacts.length} of {report.facts.length} verified figures shown</p>
        <div className="facts-grid report-facts">{filteredFacts.map(fact => {
          const passage = report.passages.find(item => item.id === fact.passage_id)
          const source = report.documents.find(item => item.id === passage?.document_id)
          return <article className="fact report-fact" key={fact.id}><div className="report-fact-top"><span>{displayMetric(fact.metric_key)}</span><span className="fact-scope">{fact.scope}</span></div><strong>{displayNumber(fact.value_decimal)}<small>{displayUnit(fact.unit_normalized)}</small></strong><em>{fact.period_end || 'Period unspecified'}{fact.segment && fact.segment !== 'all' ? ` · ${fact.segment}` : ''}</em><div className="fact-actions">{source && <a href={source.canonical_url} target="_blank" rel="noreferrer">Original source{passage?.page_index != null ? ` · page ${passage.page_index + 1}` : ''}</a>}<button aria-label={`Inspect ${displayMetric(fact.metric_key)} · ${fact.period_end || 'source'}`} onClick={() => setSelectedFact(fact)} title="Inspect figure and source"><Arrow diagonal /></button></div>{passage && <details><summary>Source passage</summary><blockquote>{passage.text}</blockquote><small>Raw unit: {fact.unit_raw} · Published: {source?.published_at?.slice(0, 10) || 'unknown'}{source?.cutoff_eligibility_basis === 'verified_retrieval' && ` · Public availability verified: ${source.retrieved_at}`}</small></details>}</article>
        })}</div>
        {!filteredFacts.length && <div className="report-empty">{report.facts.length ? 'No figures match these filters.' : 'No verified financial figures were established for this run.'}</div>}
      </section>
      </>}
      {section === 'calculations' && <>
      <section className="report-section report-reveal" id="report-calculations" aria-labelledby={`${id}-calculations`}><div className="report-section-title"><div><span className="section-kicker">03 / CHECK THE ARITHMETIC</span><h3 id={`${id}-calculations`}>Reproducible calculations</h3></div><span>Expand any calculation to see its inputs</span></div>
        {discovery && report.calculations.length > displayedCalculations.length && <p className="muted">Showing the {displayedCalculations.length} calculations linked to this discovery.</p>}
        {discovery && report.calculations.some(c => !findingCalculationIds.has(c.id)) && <button className="quiet" aria-pressed={showAdditionalCalculations} onClick={() => setShowAdditionalCalculations(value => !value)}>{showAdditionalCalculations ? 'Show discovery calculations only' : 'Show additional research calculations'}</button>}
        <div className="calculation-grid">{displayedCalculations.map(calc => {
          const inputs = calc.input_fact_ids.map(input => report.facts.find(fact => fact.id === input))
          const metrics = [...new Set(inputs.filter((fact): fact is Fact => Boolean(fact)).map(fact => displayMetric(fact.metric_key)))]
          const claim = report.claims.find(item => item.calculation_ids.includes(calc.id))
          return <article className="calculation-card" key={calc.id}><span className="calculation-metric">{metrics.join(' / ') || 'Registered calculation'}</span><h4>{displayMetric(calc.formula_id)}</h4><div className={`calculation-value ${Number(calc.output_value) < 0 ? 'value-decrease' : ''}`}>{displayNumber(calc.output_value)}<span>{displayUnit(calc.unit)}</span></div><div className="calculation-context">{[...new Set(inputs.filter(Boolean).map(fact => fact!.scope))].join(' / ')} · Formula v{calc.formula_version}</div><details><summary>Calculation inputs</summary><code>{calculationFormulas[calc.formula_id] || calc.formula_id}</code><ol>{inputs.map((fact, index) => <li key={calc.input_fact_ids[index]}>{fact ? <><span>{displayMetric(fact.metric_key)}</span><strong>{displayNumber(fact.value_decimal)} {displayUnit(fact.unit_normalized)}</strong><small>{fact.period_end} · {fact.scope}</small><button onClick={() => setSelectedFact(fact)}>Inspect input <span>↗</span></button></> : 'Input unavailable'}</li>)}</ol>{calc.comparability_checks.length > 0 && <p>{calc.comparability_checks.join('; ')}</p>}{calc.limitations.length > 0 && <p>{calc.limitations.join('; ')}</p>}</details>{claim && <button className="calculation-claim" onClick={() => onClaim(claim.id)}>Open claim evidence <Arrow diagonal /></button>}</article>
        })}</div>{!report.calculations.length && <div className="report-empty">No reproducible calculations were available for this run.</div>}
      </section>
      </>}
      {section === 'sources' && <>
      <SourceLibrary report={report} />
      </>}
      {section === 'review' && <>
      <section className="report-section report-reveal" id="report-review" aria-labelledby={`${id}-review`}><div className="report-section-title"><div><span className="section-kicker">05 / QUESTION THE CONCLUSION</span><h3 id={`${id}-review`}>The other side of the story.</h3></div><span>{discovery ? 'Challenge & falsification' : 'Coverage gaps & next evidence'}</span></div>
        {discovery ? <><div className="report-review-grid"><section className="counter report-review-card"><span className="review-card-symbol">⇄</span><h3>Strongest counterargument</h3><p>{discovery.counterargument.statement}</p><small>{discovery.counterargument.search_summary}</small><span className="pill">Active challenge {discovery.counterargument.search_attempted ? 'completed' : 'not run'}</span></section><section className="falsification report-review-card"><span className="review-card-symbol">±</span><h3>What would change this conclusion</h3>{discovery.falsification_rules.map(rule => <div className="falsification-rule" key={rule.id}><strong>{rule.observable_metric_or_event}</strong><p>{rule.operator}{rule.threshold ? ` ${rule.threshold} ${displayUnit(rule.unit)}` : ''} · {rule.interpretation}</p><small>Expected evidence: {rule.expected_source_type}</small></div>)}</section></div><section className="report-timeline" hidden={!!report.generation_metadata?.timeline_story}><h3>Timeline</h3>{report.timeline_events.map(event => <details key={event.id}><summary><time>{event.event_date || 'Date unknown'}</time><span>{event.description}</span><span>+</span></summary><p>Publication {event.published_at?.slice(0, 10) || 'date unknown'} · {event.source_ids.length} source</p>{report.documents.filter(document => event.source_ids.includes(document.id)).map(document => <a key={document.id} href={document.canonical_url} target="_blank" rel="noreferrer">{document.title}</a>)}</details>)}</section></> : <div className="report-review-grid"><section className="report-review-card missing-evidence"><span className="review-card-symbol">◌</span><h3>What is still missing</h3><ul>{report.abstention?.missing_requirements.map(item => <li key={item}>{displayResearchGap(item)}</li>)}</ul>{!report.abstention?.missing_requirements.length && <p>No additional requirements were recorded.</p>}</section><section className="report-review-card next-evidence"><span className="review-card-symbol">↗</span><h3>Next evidence needed</h3><ul>{report.abstention?.next_evidence_needed.map(item => <li key={item}>{displayResearchGap(item)}</li>)}</ul>{!report.abstention?.next_evidence_needed.length && <p>Inspect the source coverage and limitations for the next investigation.</p>}</section></div>}
        <ChallengeTrail report={report} />
        <details><summary>Submission completeness checklist</summary><SubmissionBrief report={report} /></details>
        {report.generation_metadata?.falsification_tests && <section className="report-falsification-tests"><h3>Observable tests and current checks</h3><p>{report.generation_metadata.falsification_tests.cadence.note}</p>{report.generation_metadata.falsification_tests.cadence.missing.map(text => <p key={text}>Disclosure-date estimate unavailable: {text}</p>)}{report.generation_metadata.falsification_tests.conditions.map(test => <article key={test.kind}><h4>{test.checkable_now ? 'Checked in this run' : test.kind === 'next_quarter' ? 'Primary · next quarterly disclosure' : 'Secondary · next annual report'}</h4><p>{displayMetric(test.metric)} {test.operator} {displayNumber(test.threshold)} {test.unit}</p><p>Window: {test.window || 'Not established'} · Estimated disclosure: {test.expected_disclosure_date || 'Unknown'}</p><strong>{test.status.replaceAll('_', ' ')}</strong><p>{test.reason || test.interpretation}</p><small>Expected source: {test.source_type}</small>{test.passage_ids?.map(pid => <details key={pid}><summary>Exact checked passage</summary><blockquote>{report.passages.find(p => p.id === pid)?.text || 'Passage unavailable'}</blockquote></details>)}</article>)}</section>}
        {!discovery && report.timeline_events.length > 0 && <section className="report-timeline"><h3>Timeline of verified observations</h3><p>Reporting dates show observed snapshots; they do not establish trend onset or causality.</p>{report.timeline_events.map(event => <details key={event.id}><summary><time>{event.event_date || 'Date unknown'}</time><span>{event.description}</span><span>+</span></summary>{report.documents.filter(source => event.source_ids.includes(source.id)).map(source => <a key={source.id} href={source.canonical_url} target="_blank" rel="noreferrer">{source.title}</a>)}</details>)}</section>}
        <details className="limitations report-limitations"><summary><span>{discovery ? 'Coverage and limitations' : 'Source access and coverage details'}</span><span>{report.limitations.length} notes</span></summary><ul>{report.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
      </section>
      </>}
      <nav className="report-page-turner" aria-label="Continue reading report">{nav.map(([key, label], index) => {
        const current = nav.findIndex(([key]) => key === section)
        if (Math.abs(index - current) !== 1) return null
        const previous = index < current
        return <a key={key} className={previous ? 'turn-previous' : 'turn-next'} href={routeHref({ view: 'report', runId: report.run_id, section: key })} onClick={event => { if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) { event.preventDefault(); onNavigate(key) } }}><small>{previous ? 'PREVIOUS PAGE' : 'NEXT PAGE'}</small><strong>{previous ? `\u2190 ${label}` : `${label} \u2192`}</strong></a>
      })}</nav>
      <footer className="report-footnote"><span>Every figure has a paper trail.</span><span>Cutoff {report.cutoff} · Public evidence research</span></footer>
    </div>
    {selectedFact && <SourceInspector fact={selectedFact} report={report} onClose={() => setSelectedFact(null)} />}
  </section>
}
