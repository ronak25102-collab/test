import { expect, test } from '@playwright/test'
import report from './fixtures/replay.json' with { type: 'json' }

const standaloneFact = { ...report.facts[0], id: 'standalone-figure', metric_key: 'nim', value_decimal: '3.26', unit_normalized: 'percent', unit_raw: '%', scope: 'standalone', passage_id: 'standalone-passage' }
const result = { ...report, discoveries: [], claims: [], outcome: 'insufficient_evidence', publication_status: 'abstained', facts: [...report.facts, standaloneFact],
  passages: [...report.passages, { ...report.passages[0], id: 'standalone-passage', text: 'Synthetic issuer reported standalone NIM of 3.26 percent for this reporting date.' }],
  abstention: { missing_requirements: ['Independent corroboration'], next_evidence_needed: ['A dated independent disclosure'], attempted_angles: [] } }

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [], demo_time_warning: false } })
    if (path.endsWith('/companies') || path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/report')) return route.fulfill({ json: result })
    return route.fulfill({ json: { id: result.run_id, company: result.company, as_of: result.cutoff, mode: 'replay', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
})

test('completed output prioritizes the report and filters source-bound figures without changing research', async ({ page }) => {
  const mutations: string[] = []
  page.on('request', request => { if (request.method() === 'POST') mutations.push(request.url()) })
  await page.goto(`/?run=${report.run_id}`)
  const output = page.getByRole('region', { name: 'SYNTHBANK research report', exact: true })
  await expect(output.getByText('Finding withheld', { exact: true })).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Company search', exact: true })).not.toBeVisible()
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: 'Verified figures', exact: false }).click()
  await expect(page).toHaveURL(/section=figures/)
  await expect(page.getByRole('textbox', { name: 'Company search', exact: true })).toHaveCount(0)
  const filter = page.getByRole('textbox', { name: 'Filter verified figures', exact: true })
  await filter.fill('deposits')
  await expect(output.getByText('2 of 5 verified figures shown', { exact: true })).toBeVisible()
  await page.getByRole('combobox', { name: 'Financial scope', exact: true }).selectOption('standalone')
  await expect(output.getByText('No figures match these filters.', { exact: true })).toBeVisible()
  await output.getByRole('button', { name: 'Reset filters', exact: true }).click()
  await page.getByRole('combobox', { name: 'Financial scope', exact: true }).selectOption('standalone')
  const inspect = output.getByRole('button', { name: /Inspect NIM/ })
  await inspect.click()
  const dialog = page.getByRole('dialog', { name: 'Verified figure evidence', exact: true })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByRole('heading', { name: 'NIM', exact: true })).toBeVisible()
  await expect(dialog.locator('blockquote')).toHaveText('Synthetic issuer reported standalone NIM of 3.26 percent for this reporting date.')
  await expect(dialog.getByRole('button', { name: 'Close source evidence', exact: true })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  await expect(inspect).toBeFocused()
  expect(mutations).toEqual([])
})

test('interrupted research with zero verified figures never implies a completed investigation', async ({ page }) => {
  const interrupted = { ...result, outcome: 'partial', facts: [], calculations: [],
    limitations: ['The final review allowance ended before verified facts were available.'] }
  await page.route('**/api/v1/runs/*/report', route => route.fulfill({ json: interrupted }))
  await page.goto(`/?run=${report.run_id}`)
  const output = page.getByRole('region', { name: 'SYNTHBANK research report', exact: true })
  await expect(output.getByRole('heading', { name: 'Investigation incomplete', exact: true })).toBeVisible()
  await expect(output).toContainText('this incomplete investigation does not support a conclusion about the company')
  await expect(output.getByText('No verified figures were established', { exact: true })).toBeVisible()
  await expect(output.getByText(/The run completed/)).toHaveCount(0)
  await expect(output.getByText(interrupted.limitations[0], { exact: true })).not.toBeVisible()
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Review/ }).click()
  await output.getByText('Source access and coverage details', { exact: true }).click()
  await expect(output.getByText(interrupted.limitations[0], { exact: true })).toBeVisible()
  await output.evaluate(element => element.scrollIntoView({ block: 'start', behavior: 'instant' }))
  const topbarBottom = await page.locator('.topbar').evaluate(element => element.getBoundingClientRect().bottom)
  expect(await output.evaluate(element => element.getBoundingClientRect().top)).toBeGreaterThanOrEqual(topbarBottom)
})

test('chart points and calculation inputs open their exact evidence', async ({ page }) => {
  await page.goto(`/?run=${report.run_id}`)
  const audit = page.getByRole('region', { name: 'Research coverage and decisions', exact: true })
  const older = audit.getByRole('button', { name: /Gross advances on 2025-03-31/ })
  await older.click()
  await expect(older).toHaveAttribute('aria-pressed', 'true')
  await audit.getByRole('button', { name: /Inspect selected source/ }).click()
  let dialog = page.getByRole('dialog', { name: 'Verified figure evidence', exact: true })
  await expect(dialog.locator('blockquote')).toHaveText(report.passages[0].text)
  await dialog.getByRole('button', { name: 'Close source evidence', exact: true }).click()
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Calculations/ }).click()
  const calculation = page.locator('.calculation-card').first()
  await calculation.getByText('Calculation inputs', { exact: true }).click()
  await expect(calculation.locator('code')).toContainText('current / prior')
  await calculation.getByRole('button', { name: /Inspect input/ }).first().click()
  dialog = page.getByRole('dialog', { name: 'Verified figure evidence', exact: true })
  await expect(dialog.getByRole('link', { name: /Open original source/ })).toHaveAttribute('href', report.documents[0].canonical_url)
})

test('source filters, empty states and export links keep their provenance', async ({ page }) => {
  await page.goto(`/?run=${report.run_id}`)
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Sources/ }).click()
  const sources = page.getByRole('region', { name: 'Source library', exact: true })
  await sources.getByRole('button', { name: 'Supporting figures', exact: true }).click()
  await expect(sources.locator('.source-record')).toHaveCount(1)
  await sources.getByRole('textbox', { name: 'Search sources', exact: true }).fill('no matching document')
  await expect(sources.getByText('No sources match these filters.', { exact: true })).toBeVisible()
  await sources.getByRole('button', { name: 'Reset source filters', exact: true }).click()
  await expect(sources.locator('.source-record')).toHaveCount(report.documents.length)
  await page.locator('.report-export > summary').click()
  await expect(page.getByRole('link', { name: 'CSV', exact: true })).toHaveAttribute('href', new RegExp(`/runs/${report.run_id}/exports/facts.csv$`))
  await expect(page.getByRole('link', { name: 'Print / Save as PDF', exact: true })).toHaveAttribute('href', `?run=${report.run_id}&print=1`)
  await expect(page.getByRole('link', { name: 'Self-contained HTML', exact: true })).toHaveAttribute('href', new RegExp(`/runs/${report.run_id}/exports/report.html$`))
})

test('mobile results and evidence dialogs fit the viewport with reduced motion', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto(`/?run=${report.run_id}`)
  await expect(page.locator('.report-stat').first()).toHaveCSS('animation-name', 'none')
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Verified figures/ }).click()
  const inspect = page.getByRole('button', { name: /Inspect NIM/ })
  await inspect.click()
  const dialog = page.getByRole('dialog', { name: 'Verified figure evidence', exact: true })
  await expect(dialog).toHaveCSS('animation-name', 'none')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.keyboard.press('Escape')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('withheld reports expose all eight requirements and retain the actual adversarial trail', async ({ page }) => {
  const challenged = { ...result, generation_metadata: { ...result.generation_metadata,
    opposing_queries: ['issuer acquisition reclassification alternative'],
    challenge_reviews: [{ candidate: 'Unconfirmed funding relationship', strongest_alternative: 'A reporting-boundary change could explain the comparison.',
      reason: 'The boundary change remains unresolved.', refuted: false, unresolved: true,
      relevant_passage_ids: [result.passages[0].id], proposed_falsification: 'A reversal in two future comparable quarters.',
      opposing_query: 'issuer acquisition reclassification alternative', novelty_status: 'novelty_unknown', novelty_rationale: 'Further independent evidence is required.' }] } }
  await page.route('**/api/v1/runs/*/report', route => route.fulfill({ json: challenged }))
  await page.goto(`/?run=${report.run_id}`)
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Review/ }).click()
  const brief = page.getByRole('region', { name: 'Required discovery output', exact: true })
  await page.getByText('Submission completeness checklist', { exact: true }).click()
  await expect(brief.locator('li')).toHaveCount(8)
  await expect(brief.getByText('Discovery requirements not met', { exact: true })).toBeVisible()
  const trail = page.getByRole('region', { name: 'Adversarial research trail', exact: true })
  await expect(trail).toContainText('1 adversarial reviews recorded · 1 opposing searches recorded')
  await expect(trail.getByText('A reporting-boundary change could explain the comparison.', { exact: true })).toBeVisible()
  await expect(trail.getByRole('heading', { name: 'Proposed falsification condition · unverified', exact: true })).toBeVisible()
  await expect(trail.getByRole('link').first()).toHaveAttribute('href', result.documents[0].canonical_url)
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Overview/ }).click()
  await expect(page.getByText('Finding withheld', { exact: true })).toBeVisible()
})

test('published reports expose the eight-part brief and preserve an explicit temporal caveat', async ({ page }) => {
  const published = { ...report, generation_metadata: { temporal_reasoning: {
    text: 'Two observed reporting dates do not establish when the relationship began.',
    claim_id: report.claims[0].id, onset_status: 'unknown' } } }
  await page.route('**/api/v1/runs/*/report', route => route.fulfill({ json: published }))
  await page.goto(`/?run=${report.run_id}`)
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Review/ }).click()
  const brief = page.getByRole('region', { name: 'Required discovery output', exact: true })
  await page.getByText('Submission completeness checklist', { exact: true }).click()
  await expect(brief.locator('li')).toHaveCount(8)
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Overview/ }).click()
  await expect(page.getByRole('heading', { name: 'Why it matters', exact: true })).toBeVisible()
  await expect(page.getByText(published.generation_metadata.temporal_reasoning.text, { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /Inspect timeline evidence/ })).toBeVisible()
  await expect(page.getByText('Synthetic replay', { exact: true })).toBeVisible()
})

test('demo output exposes strength caps, break evidence, peer gaps and current falsification checks', async ({ page }) => {
  const fact = report.facts[0], passage = report.passages.find(p => p.id === fact.passage_id)!
  const enhanced = { ...report, generation_metadata: {
    headline: { technical_detail: 'Reviewed technical relationship.', technical_claim_id: report.claims[0].id, claim_id: report.claims[0].id, method: 'verified_arithmetic_template' },
    strength_trace: { rating: 'Weak', rules: { peer_comparison_verified: false }, caps: ['Peer verification is incomplete: maximum Weak.'], origin_families: [], note: 'Corroboration rules.' },
    cache_usage: { cold_start: true, reused: 0, fresh: report.facts.length },
    structural_breaks: [{ id: 'break-fixture', metric: fact.metric_key, scope: fact.scope, start: '2025-03-31', end: fact.period_end, growth: '80', passage_ids: [passage.id], source_url: report.documents[0].canonical_url, reason: 'A verified event requires reconciliation.' }],
    timeline_story: { events: [{ date: fact.period_end, metric: fact.metric_key, scope: fact.scope, fact_id: fact.id, passage_id: passage.id, source_url: report.documents[0].canonical_url, value: fact.value_decimal, unit: fact.unit_normalized, what_changed: 'A source-bound balance was disclosed.', why_it_matters: 'Tests the observed relationship.' }], onsets: [], missing: ['More consecutive quarterly dates are required.'] },
    peer_benchmark: { status: 'inconclusive', comparisons: [], missing: ['Two matching peer disclosures.'] },
    falsification_tests: { cadence: { confidence: 'Unknown', note: 'Estimate, not a promise.', missing: ['Two filing dates.'] }, conditions: [{ kind: 'current_reconciliation', metric: 'reconciliation disclosed', operator: '=', threshold: '1', unit: 'event', checkable_now: true, status: 'not_found', source_type: 'Issuer notes', passage_ids: [passage.id], reason: 'No relevant reconciliation was found in checked passages.' }] }
  } }
  await page.route('**/api/v1/runs/*/report', route => route.fulfill({ json: enhanced }))
  await page.goto(`/?run=${report.run_id}`)
  await page.getByText('Weak · evidence strength rule trace', { exact: true }).click()
  await expect(page.getByText('Peer verification is incomplete: maximum Weak.', { exact: true })).toBeVisible()
  await expect(page.getByText(/0 facts reused, 4 fetched fresh/)).toBeVisible()
  const timeline = page.getByRole('region', { name: 'Timeline story', exact: true })
  await expect(timeline).toContainText('Structural break flagged')
  await timeline.getByRole('button', { name: 'Inspect exact passage ↗', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Verified figure evidence', exact: true })).toContainText(passage.text)
  await page.keyboard.press('Escape')
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Review/ }).click()
  await expect(page.getByRole('heading', { name: 'Observable tests and current checks' })).toBeVisible()
  await expect(page.getByText('No relevant reconciliation was found in checked passages.', { exact: true })).toBeVisible()
})


test('withheld candidate stays readable on its beige panel', async ({ page }) => {
  const candidate = { ...result, generation_metadata: { ...result.generation_metadata, best_candidate: {
    label: 'Not established', text: 'Synthetic candidate needs independent verification.',
    reason: 'Scope and peer evidence remain incomplete.', missing: ['Matching peer facts'], fact_ids: [], calculation_ids: []
  } } }
  await page.route('**/api/v1/runs/*/report', route => route.fulfill({ json: candidate }))
  await page.goto(`/?run=${report.run_id}`)
  const panel = page.locator('.best-candidate')
  await expect(panel).toContainText('not a published finding')
  const contrast = await panel.evaluate(element => {
    const luminance = (value: string) => {
      const rgb = value.match(/\d+/g)!.slice(0, 3).map(Number).map(c => {
        const v = c / 255
        return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4
      })
      return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722
    }
    const background = luminance(getComputedStyle(element).backgroundColor)
    return Math.min(...Array.from(element.querySelectorAll('strong, p, small')).map(text => {
      const foreground = luminance(getComputedStyle(text).color)
      return (Math.max(background, foreground) + .05) / (Math.min(background, foreground) + .05)
    }))
  })
  expect(contrast).toBeGreaterThanOrEqual(4.5)
})
