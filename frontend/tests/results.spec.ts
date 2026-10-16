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
  await page.getByText('Investigation settings', { exact: true }).click()
  await expect(page.getByRole('textbox', { name: 'Company search', exact: true })).toBeVisible()
  await page.getByText('Investigation settings', { exact: true }).click()
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
  const calculation = page.locator('.calculation-card').first()
  await calculation.getByText('Calculation inputs', { exact: true }).click()
  await expect(calculation.locator('code')).toContainText('current / prior')
  await calculation.getByRole('button', { name: /Inspect input/ }).first().click()
  dialog = page.getByRole('dialog', { name: 'Verified figure evidence', exact: true })
  await expect(dialog.getByRole('link', { name: /Open original source/ })).toHaveAttribute('href', report.documents[0].canonical_url)
})

test('source filters, empty states and export links keep their provenance', async ({ page }) => {
  await page.goto(`/?run=${report.run_id}`)
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
  const brief = page.getByRole('region', { name: 'Required discovery output', exact: true })
  await page.getByText('Submission completeness checklist', { exact: true }).click()
  await expect(brief.locator('li')).toHaveCount(8)
  await expect(brief.getByText('Discovery requirements not met', { exact: true })).toBeVisible()
  const trail = page.getByRole('region', { name: 'Adversarial research trail', exact: true })
  await expect(trail).toContainText('1 adversarial reviews recorded · 1 opposing searches recorded')
  await expect(trail.getByText('A reporting-boundary change could explain the comparison.', { exact: true })).toBeVisible()
  await expect(trail.getByRole('heading', { name: 'Proposed falsification condition · unverified', exact: true })).toBeVisible()
  await expect(trail.getByRole('link').first()).toHaveAttribute('href', result.documents[0].canonical_url)
  await expect(page.getByText('Finding withheld', { exact: true })).toBeVisible()
})

test('published reports expose the eight-part brief and preserve an explicit temporal caveat', async ({ page }) => {
  const published = { ...report, generation_metadata: { temporal_reasoning: {
    text: 'Two observed reporting dates do not establish when the relationship began.',
    claim_id: report.claims[0].id, onset_status: 'unknown' } } }
  await page.route('**/api/v1/runs/*/report', route => route.fulfill({ json: published }))
  await page.goto(`/?run=${report.run_id}`)
  const brief = page.getByRole('region', { name: 'Required discovery output', exact: true })
  await page.getByText('Submission completeness checklist', { exact: true }).click()
  await expect(brief.locator('li')).toHaveCount(8)
  await expect(page.getByRole('heading', { name: 'Why it matters', exact: true })).toBeVisible()
  await expect(page.getByText(published.generation_metadata.temporal_reasoning.text, { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: /Inspect timeline evidence/ })).toBeVisible()
  await expect(page.getByText('Synthetic replay', { exact: true })).toBeVisible()
})
