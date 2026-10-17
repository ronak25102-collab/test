import { test, expect } from '@playwright/test'
import report from './fixtures/replay.json' with { type: 'json' }

test('retrieved context is not displayed as verified issuer evidence', async ({ page }) => {
  const empty = { ...report, outcome: 'insufficient_evidence', publication_status: 'abstained', discoveries: [],
    facts: [], calculations: [], documents: report.documents.map(d => ({ ...d, document_type: 'public_context' })) }
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/report')) return route.fulfill({ json: empty })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff,
      mode: 'live', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  const audit = page.getByLabel('Research coverage and decisions')
  await expect(audit.getByText(/0 official issuer filings/)).toBeVisible()
  await expect(audit.getByText(/0 documents supporting verified facts/)).toBeVisible()
  await expect(audit.getByText(/Availability alone does not establish issuer identity/)).toBeVisible()
})

test('comparable charts retain source links and withheld candidates stay labelled', async ({ page }) => {
  const partial = { ...report, outcome: 'partial', publication_status: 'abstained', discoveries: [],
    generation_metadata: { research_decisions: [{ candidate: 'Unconfirmed funding mechanism', disposition: 'withheld',
      reason: 'Independent corroboration was insufficient.', published: false }] } }
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/report')) return route.fulfill({ json: partial })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff,
      mode: 'live', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  const audit = page.getByLabel('Research coverage and decisions')
  await expect(audit.getByRole('img')).toBeVisible()
  await expect(audit.getByRole('combobox', { name: 'Comparable metric' })).toBeVisible()
  await expect(audit.getByRole('link', { name: 'Source', exact: true }).first()).toHaveAttribute('href', report.documents[0].canonical_url)
  await expect(audit.getByText(/Two snapshots establish a comparison/)).toBeVisible()
  await audit.getByText('Candidate decisions (1)', { exact: true }).click()
  await expect(audit.getByText('These investigation candidates were not published as findings.')).toBeVisible()
  await expect(audit.getByText(/Independent corroboration was insufficient/)).toBeVisible()
})

test('missing account configuration blocks live research while preserving replay', async ({ page }) => {
  let created = false
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: {
      ready: false, issues: ['Create config/model-rates.json with your verified account prices.'], demo_time_warning: true,
    } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/runs')) created = true
    return route.fulfill({ json: {} })
  })
  await page.goto('/?view=workspace')
  await page.getByRole('button', { name: /SYNTHBANK/ }).click()
  await expect(page.getByRole('status')).toContainText('Live research needs configuration')
  await expect(page.getByRole('button', { name: /Start autonomous research/ })).toBeDisabled()
  expect(created).toBe(false)
  await page.getByRole('combobox', { name: 'Mode', exact: true }).selectOption('replay')
  await expect(page.getByRole('button', { name: /Start autonomous research/ })).toBeEnabled()
})

test('saved bank run restores its own company, cutoff and mode without defaulting to HDFC', async ({ page }) => {
  const company = { ...report.company, legal_name: 'Axis Bank', symbols: ['AXISBANK'] }
  let polls = 0
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [company] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    polls++
    return route.fulfill({ json: { id: report.run_id, company, as_of: '2026-07-17', mode: 'deep',
      status: 'extracting', stage: 'extracting', progress: { sources_found: polls }, limitations: [] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  await expect(page).toHaveURL(/view=progress/)
  await expect(page.getByRole('heading', { name: 'Following the evidence.' })).toBeVisible()
  await expect(page.locator('.workspace-heading')).toContainText('Axis Bank')
  await expect(page.locator('.workspace-heading')).toContainText('2026-07-17')
  await expect(page.locator('.workspace-heading')).toContainText('Extended research')
  await expect(page.getByRole('textbox', { name: 'Company search' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Start autonomous research/ })).toHaveCount(0)
  await expect.poll(() => polls).toBeGreaterThan(1)
  await expect(page.locator('.workspace-heading')).toContainText('Axis Bank')
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
  await page.goto('/?view=workspace')
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
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/report')) return route.fulfill({ json: partial })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'live', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  await expect(page.getByRole('heading', { name: 'Verified evidence collected' })).toBeVisible()
  if (outcome === 'partial') {
    await expect(page.getByText('PARTIAL RESEARCH')).toBeVisible()
    await expect(page.getByRole('status')).toContainText('Research stopped before discovery verification finished')
  }
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Verified figures/ }).click()
  await expect(page.getByRole('link', { name: /Original source/ }).first()).toHaveAttribute('href', report.documents[0].canonical_url)
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Verified figures/ }).click()
  await page.getByText('Source passage', { exact: true }).first().click()
  await expect(page.locator('blockquote').first()).toHaveText(report.passages[0].text)
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Calculations/ }).click()
  await expect(page.getByRole('heading', { name: 'Reproducible calculations' })).toBeVisible()
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Review/ }).click()
  await expect(page.getByText('Independent funding corroboration')).toBeVisible()
  await expect(page.getByText('Source unavailable: blocked publisher returned 403')).not.toBeVisible()
  await page.getByText('Source access and coverage details', { exact: true }).click()
  await expect(page.getByText('Source unavailable: blocked publisher returned 403')).toBeVisible()
})
}

test('complete report exposes sources, calculation inputs and printable timeline', async ({ page }) => {
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/runs') && route.request().method() === 'POST') return route.fulfill({ status: 202, json: { run_id: report.run_id } })
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [], next_cursor: 0 } })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'replay', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
  await page.goto('/?view=workspace')
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
  await page.locator('.report-export > summary').click()
  await page.getByRole('link', { name: 'Print / Save as PDF' }).click()
  await expect(page.getByRole('heading', { name: 'Timeline' })).toBeVisible()
  await expect(page.getByRole('link', { name: report.documents[0].title })).toHaveAttribute('href', report.documents[0].canonical_url)
  await page.screenshot({ path: 'test-results/print-report.png', fullPage: true })
})

test('failed run shows its reason and can resume', async ({ page }) => {
  let status = 'failed'
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
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
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
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
  await expect.poll(() => created).toEqual({ company_id: report.company.id, as_of: report.cutoff, mode: 'live', cold_start: false })
})

test('directory resolution selects the returned listed company', async ({ page }) => {
  await page.route('**/api/v1/companies?*', route => route.fulfill({ json: { items: [] } }))
  await page.route('**/api/v1/companies/resolve', route => route.fulfill({ json: { resolved: { ...report.company, legal_name: 'New Bank Limited', symbols: ['NEWBANK'] } } }))
  await page.goto('/?view=workspace')
  await page.getByLabel('Company search').fill('NEWBANK')
  await page.getByRole('button', { name: 'Resolve from exchange directory' }).click()
  await expect(page.getByRole('button', { name: /Start autonomous research/ })).toBeEnabled()
  await expect(page.getByRole('button', { name: /New Bank Limited/ })).toBeVisible()
})


test('long source passage opens without widening the dashboard', async ({ page }) => {
  const text = 'SourceHeader'.repeat(300)
  const partial = { ...report, outcome: 'insufficient_evidence', publication_status: 'abstained', discoveries: [], claims: [],
    passages: report.passages.map((p, index) => index === 0 ? { ...p, text } : p),
    abstention: { missing_requirements: ['Independent corroboration'], next_evidence_needed: [], attempted_angles: [] } }
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies') || path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/report')) return route.fulfill({ json: partial })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'live', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.goto(`/?run=${report.run_id}`)
  await page.getByRole('navigation', { name: 'Report sections' }).getByRole('link', { name: /Verified figures/ }).click()
  await page.getByText('Source passage', { exact: true }).first().click()
  await expect(page.locator('blockquote').first()).toHaveText(text)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
})


test('queued research cannot be duplicated by repeated start clicks', async ({ page }) => {
  let starts = 0
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [], demo_time_warning: false } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/runs') && route.request().method() === 'POST') {
      starts++
      return route.fulfill({ json: { run_id: report.run_id } })
    }
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'replay', status: 'queued', stage: 'queued', progress: {}, limitations: [] } })
  })
  await page.goto('/?view=workspace')
  await page.getByRole('button', { name: /SYNTHBANK/ }).click()
  await page.getByRole('combobox', { name: 'Mode', exact: true }).selectOption('replay')
  const start = page.getByRole('button', { name: /Start autonomous research/ })
  await start.evaluate(el => { (el as HTMLButtonElement).click(); (el as HTMLButtonElement).click() })
  await expect(page.getByRole('status')).toContainText('Research is queued')
  await expect(start).toHaveCount(0)
  await expect(page).toHaveURL(/view=progress/)
  expect(starts).toBe(1)
})


test('lost creation response reuses the same idempotency key on retry', async ({ page }) => {
  const keys: (string | undefined)[] = []
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [], demo_time_warning: false } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/runs') && route.request().method() === 'POST') {
      keys.push(route.request().headers()['idempotency-key'])
      if (keys.length === 1) return route.abort('connectionfailed')
      return route.fulfill({ json: { run_id: report.run_id } })
    }
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'replay', status: 'queued', stage: 'queued', progress: {}, limitations: [] } })
  })
  await page.goto('/?view=workspace')
  await page.getByRole('button', { name: /SYNTHBANK/ }).click()
  await page.getByRole('combobox', { name: 'Mode', exact: true }).selectOption('replay')
  const start = page.getByRole('button', { name: /Start autonomous research/ })
  await start.click()
  await expect(page.getByRole('alert')).toBeVisible()
  await start.click()
  await expect(page.getByRole('status')).toContainText('Research is queued')
  expect(keys).toHaveLength(2)
  expect(keys[0]).toBeTruthy()
  expect(keys[0]).toBe(keys[1])
})

test('saved run polling reconnects after a temporary local API failure', async ({ page }) => {
  let polls = 0
  let apiRecovered = false
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.route('**/api/v1/**', route => {
    if (new URL(route.request().url()).pathname.endsWith('/history')) return route.fulfill({ json: { items: [] } })
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies') || path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [], demo_time_warning: false } })
    polls++
    if (!apiRecovered) return route.fulfill({ status: 503, json: { message: 'Controlled temporary API outage' } })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'live', status: 'queued', stage: 'queued', progress: {}, limitations: [] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  await page.getByRole('button', { name: 'Skip intro' }).click()
  await expect(page.getByRole('alert')).toContainText('Controlled temporary API outage')
  // Restore the mock service after the error is observed, independently of intro timing.
  apiRecovered = true
  await expect(page.getByRole('status')).toContainText('Research is queued', { timeout: 10000 })
  await expect(page.getByRole('alert')).not.toBeVisible()
  expect(polls).toBeGreaterThanOrEqual(2)
})
