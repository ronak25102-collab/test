import { test, expect } from '@playwright/test'
import report from './fixtures/replay.json' with { type: 'json' }

test('saved bank run restores its own company, cutoff and mode without defaulting to HDFC', async ({ page }) => {
  const company = { ...report.company, legal_name: 'Axis Bank', symbols: ['AXISBANK'] }
  let polls = 0
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [company] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    polls++
    return route.fulfill({ json: { id: report.run_id, company, as_of: '2026-07-17', mode: 'deep',
      status: 'extracting', stage: 'extracting', progress: { sources_found: polls }, limitations: [] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  await expect(page.getByRole('textbox', { name: 'Company search' })).toHaveValue('AXISBANK')
  await expect(page.getByLabel('Cutoff date')).toHaveValue('2026-07-17')
  await expect(page.getByRole('combobox', { name: 'Mode', exact: true })).toHaveValue('deep')
  await expect(page.getByRole('button', { name: /Axis Bank/ })).toHaveClass(/selected/)
  await expect(page.getByRole('button', { name: /Start autonomous research/ })).toBeEnabled()
  await page.getByRole('textbox', { name: 'Company search' }).fill('ICICIBANK')
  await expect.poll(() => polls).toBeGreaterThan(1)
  await expect(page.getByRole('textbox', { name: 'Company search' })).toHaveValue('ICICIBANK')
  await expect(page.getByRole('button', { name: /Start autonomous research/ })).toBeDisabled()
})

test('local startup removes a leftover root service worker', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'serviceWorker', { value: {
      controller: null,
      getRegistrations: async () => [{ scope: `${location.origin}/`, unregister: async () => {
        sessionStorage.setItem('legacy-worker-removed', 'yes'); return true
      } }],
    } })
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Investigate a listed financial business' })).toBeVisible()
  expect(await page.evaluate(() => sessionStorage.getItem('legacy-worker-removed'))).toBe('yes')
})

for (const outcome of ['insufficient_evidence', 'partial']) {
test(`${outcome} still exposes verified facts, inputs and original sources`, async ({ page }) => {
  const partial = { ...report, outcome, publication_status: 'abstained', discoveries: [],
    claims: [], abstention: { missing_requirements: ['Independent funding corroboration'], next_evidence_needed: ['A dated independent rating report'], attempted_angles: [] },
    limitations: ['Source unavailable: blocked publisher returned 403'] }
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/report')) return route.fulfill({ json: partial })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'live', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  await expect(page.getByRole('heading', { name: 'Verified evidence collected' })).toBeVisible()
  if (outcome === 'partial') {
    await expect(page.getByText('PARTIAL RESEARCH')).toBeVisible()
    await expect(page.getByRole('status')).toContainText('Research reached its configured limit')
  }
  await expect(page.getByRole('link', { name: /Original source/ }).first()).toHaveAttribute('href', report.documents[0].canonical_url)
  await expect(page.getByRole('heading', { name: 'Reproducible calculations' })).toBeVisible()
  await expect(page.getByText('Independent funding corroboration')).toBeVisible()
  await expect(page.getByText('Source unavailable: blocked publisher returned 403')).not.toBeVisible()
  await page.getByText('Source access and coverage details').click()
  await expect(page.getByText('Source unavailable: blocked publisher returned 403')).toBeVisible()
})
}

test('complete report exposes sources, calculation inputs and printable timeline', async ({ page }) => {
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/runs') && route.request().method() === 'POST') return route.fulfill({ status: 202, json: { run_id: report.run_id } })
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [], next_cursor: 0 } })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'replay', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
  await page.goto('/')
  await page.getByRole('button', { name: /SYNTHBANK/ }).click()
  await page.getByRole('combobox', { name: 'Mode', exact: true }).selectOption('replay')
  await page.getByRole('button', { name: /Start autonomous research/ }).click()
  await expect(page.getByRole('heading', { name: report.discoveries[0].discovery_sentence })).toBeVisible()
  await page.getByRole('button', { name: /Gross advances grew 20/ }).click()
  const drawer = page.getByLabel('Claim evidence')
  await expect(drawer.getByRole('link', { name: /Open original source/ }).first()).toHaveAttribute('href', report.documents[0].canonical_url)
  await expect(drawer.getByText(/current \/ prior/)).toBeVisible()
  await expect(drawer.getByText('Output: 20.00 percent')).toBeVisible()
  await page.screenshot({ path: 'test-results/evidence-drawer.png', fullPage: true })
  await page.getByRole('button', { name: 'Close evidence' }).click()
  await page.getByRole('link', { name: 'Print view' }).click()
  await expect(page.getByRole('heading', { name: 'Timeline' })).toBeVisible()
  await expect(page.getByRole('link', { name: report.documents[0].title })).toHaveAttribute('href', report.documents[0].canonical_url)
  await page.screenshot({ path: 'test-results/print-report.png', fullPage: true })
})

test('failed run shows its reason and can resume', async ({ page }) => {
  let status = 'failed'
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [], next_cursor: 0 } })
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    if (path.endsWith('/resume')) { status = 'completed'; return route.fulfill({ status: 202, json: { status: 'queued' } }) }
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'live', status, stage: status, progress: {}, limitations: ['Source request deadline exceeded'] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  await expect(page.getByRole('heading', { name: 'Investigation failed' })).toBeVisible()
  await expect(page.getByRole('alert')).toContainText('Source request deadline exceeded')
  await page.getByRole('button', { name: 'Resume from saved work' }).click()
  await expect(page.getByRole('heading', { name: report.discoveries[0].discovery_sentence })).toBeVisible()
})

test('expired run starts a fresh investigation with the original company and cutoff', async ({ page }) => {
  let restarted = false
  let created: unknown
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    if (path.endsWith('/runs') && route.request().method() === 'POST') {
      created = route.request().postDataJSON(); restarted = true
      return route.fulfill({ status: 202, json: { run_id: report.run_id } })
    }
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'live', status: restarted ? 'completed' : 'failed', stage: 'failed', progress: {}, limitations: ['run deadline exceeded'] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  await expect(page.getByRole('alert')).toContainText('This run reached its total time limit')
  await expect(page.getByRole('button', { name: 'Resume from saved work' })).not.toBeVisible()
  await page.getByRole('button', { name: 'Start a new run' }).click()
  await expect.poll(() => created).toEqual({ company_id: report.company.id, as_of: report.cutoff, mode: 'live' })
})

test('directory resolution selects the returned listed company', async ({ page }) => {
  await page.route('**/api/v1/companies?*', route => route.fulfill({ json: { items: [] } }))
  await page.route('**/api/v1/companies/resolve', route => route.fulfill({ json: { resolved: { ...report.company, legal_name: 'New Bank Limited', symbols: ['NEWBANK'] } } }))
  await page.goto('/')
  await page.getByLabel('Company search').fill('NEWBANK')
  await page.getByRole('button', { name: 'Resolve from exchange directory' }).click()
  await expect(page.getByRole('button', { name: /Start autonomous research/ })).toBeEnabled()
  await expect(page.getByRole('button', { name: /New Bank Limited/ })).toBeVisible()
})
