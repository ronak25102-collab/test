import type { Report } from '../api/generated'

const requirements = ['The Discovery', 'Why It Matters', 'Evidence', 'Timeline', 'Numbers', 'Counterargument', 'Falsification Condition', 'Evidence Strength']
const pendingReasons = [
  'No candidate passed the discovery publication checks.',
  'No discovery-level significance statements were verified.',
  'Source links remain available; independent support for a finding has not been established.',
  'Reporting snapshots alone do not establish when a change emerged.',
  'Reproducible calculations remain available; arithmetic alone is not a discovery.',
  'Review the recorded candidate challenges below; no discovery-level counterargument was approved.',
  'A proposed test must pass observable-condition review before publication.',
  'An unsupported candidate cannot receive a discovery strength rating.',
]

export function SubmissionBrief({ report }: { report: Report }) {
  const checklist = report.generation_metadata?.submission_checklist
  const discovery = report.discoveries[0]
  const items = checklist?.items || requirements.map((label, index) => ({
    key: label, label,
    status: discovery ? 'complete' : index === 4 && report.calculations.length ? 'complete' : 'missing',
    reason: discovery ? 'Open the verified discovery and linked evidence below.' : pendingReasons[index],
  }))
  return <section className="submission-brief" aria-label="Required discovery output">
    <div className="submission-heading"><div><span className="section-kicker">THE EIGHT REQUIRED ELEMENTS</span><h3>Discovery brief</h3></div><span className={`submission-status ${discovery ? 'is-ready' : ''}`}>{discovery ? 'Discovery published' : 'Discovery requirements not met'}</span></div>
    <p>{discovery ? 'Review each element against its original evidence. A completeness check does not replace the assessment of discovery quality.' : 'Verified observations and research candidates remain available. They do not constitute a completed discovery submission.'}</p>
    <ol className="submission-checklist">{items.map((item, index) => <li key={item.key} data-status={item.status}><span className="requirement-index">{String(index + 1).padStart(2, '0')}</span><div><strong>{item.label}</strong><p>{item.reason}</p></div><span className="requirement-status">{item.status === 'complete' ? 'Available' : item.status === 'limited' ? 'Limited' : 'Not established'}</span></li>)}</ol>
    {checklist?.historical_coverage && <p className="submission-history">Historical coverage: {checklist.historical_coverage.longest_comparable_series} dates in the longest comparable series. {checklist.historical_coverage.target}</p>}
  </section>
}

export function ChallengeTrail({ report }: { report: Report }) {
  const reviews = report.generation_metadata?.challenge_reviews || []
  const queries = report.generation_metadata?.opposing_queries || []
  const decisions = report.generation_metadata?.research_decisions || []
  if (report.discoveries.length) return null
  return <section className="challenge-trail" aria-label="Adversarial research trail">
    <h3>Counterargument & falsification research</h3>
    <p>{reviews.length} adversarial reviews recorded · {queries.length} opposing searches recorded. These are investigation records, not verified discovery claims.</p>
    {!reviews.length && <p>No completed adversarial review is recorded for this run. Rejected preliminary candidates do not count as counterevidence tests.</p>}
    {reviews.map((review, index) => <details key={index} open={index === 0}><summary><span>{review.refuted ? 'Refuted candidate' : review.unresolved ? 'Alternative unresolved' : 'Alternative reviewed'}</span><strong>{review.candidate}</strong></summary><div className="challenge-trail-body"><h4>Strongest alternative considered</h4><p>{review.strongest_alternative}</p><p>{review.reason}</p><h4>Proposed falsification condition · unverified</h4><p>{review.proposed_falsification}</p><p className="muted">This candidate test has not passed final observable-condition and semantic review.</p><h4>Opposing query</h4><p>{review.opposing_query}</p><h4>Novelty review</h4><p>{review.novelty_status.replaceAll('_', ' ')} · {review.novelty_rationale}</p><ul>{report.passages.filter(p => review.relevant_passage_ids.includes(p.id)).map(passage => {
      const source = report.documents.find(d => d.id === passage.document_id)
      return <li key={passage.id}>{source && <a href={source.canonical_url} target="_blank" rel="noreferrer">{source.title}{passage.page_index != null ? ` · page ${passage.page_index + 1}` : ''}</a>}<details><summary>Reviewed passage</summary><blockquote>{passage.text}</blockquote></details></li>
    })}</ul></div></details>)}
    {!!decisions.length && <div className="candidate-tests"><h4>Unverified candidate tests</h4>{decisions.filter(item => item.proposed_falsification).map((item, index) => <details key={index}><summary>{item.candidate}</summary><p>Publication withheld: {item.reason}</p><p>Proposed test: {item.proposed_falsification}</p><small>Proposed tests are retained for further research; they are not a verified finding or a strength rating.</small></details>)}</div>}
  </section>
}
