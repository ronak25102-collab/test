import type { Fact, Report } from '../api/generated'
import { displayMetric, displayNumber, displayUnit } from './format'

export function TimelineStory({ report, onFact }: { report: Report; onFact: (fact: Fact) => void }) {
  const story = report.generation_metadata?.timeline_story
  if (!story) return null
  const groups = [...new Set(story.events.map(e => `${e.metric}|${e.scope}`))]
  return <section className="report-section story-timeline" id="report-timeline" aria-label="Timeline story">
    <h3>How the relationship developed</h3>
    <div className="story-sparklines">{groups.map(key => {
      const points = story.events.filter(e => `${e.metric}|${e.scope}` === key)
      const values = points.map(p => Number(p.value)), min = Math.min(...values), range = Math.max(...values) - min || 1
      return <figure key={key}><figcaption>{displayMetric(points[0].metric)} · {points[0].scope}</figcaption><svg viewBox="0 0 240 60" role="img" aria-label={`${displayMetric(points[0].metric)} observed history`}><polyline fill="none" stroke="#315b3e" strokeWidth="2" points={values.map((v, i) => `${5 + i * 230 / Math.max(1, values.length - 1)},${55 - (v - min) * 45 / range}`).join(' ')} /></svg></figure>
    })}</div>
    {story.onsets.map(item => <p key={`${item.metric}|${item.scope}`}><strong>{displayMetric(item.metric)} onset · </strong>{item.estimate ? `${item.estimate.date} · ${item.estimate.confidence} confidence. ${item.estimate.reason}` : `Not established. Needed: ${item.missing.join(' ')}`}</p>)}
    {story.missing.map(text => <p className="muted" key={text}>Onset not established: {text}</p>)}
    <ol>{[...story.events.map(e => ({ date: e.date, key: e.fact_id, node: <><strong>{e.what_changed}</strong><p>{displayNumber(e.value)} {displayUnit(e.unit)} · {e.scope}{e.change != null && ` · Change ${displayNumber(e.change)} ${displayUnit(e.change_unit)}`}</p><p>{e.why_it_matters}</p><button onClick={() => { const f = report.facts.find(f => f.id === e.fact_id); if (f) onFact(f) }}>Inspect exact passage ↗</button></> })),
      ...(report.generation_metadata?.structural_breaks || []).map(b => ({ date: b.end, key: b.id, node: <><strong>Structural break flagged · {displayMetric(b.metric)}</strong><p>{b.reason}</p>{b.passage_ids.map(id => <details key={id}><summary>Event source passage</summary><blockquote>{report.passages.find(p => p.id === id)?.text || 'Passage unavailable'}</blockquote><a href={b.source_url} target="_blank" rel="noreferrer">Original filing ↗</a></details>)}</> }))].sort((a, b) => a.date.localeCompare(b.date)).map(e => <li key={e.key}><time>{e.date}</time><div>{e.node}</div></li>)}</ol>
  </section>
}
