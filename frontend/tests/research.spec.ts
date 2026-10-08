import { test, expect } from '@playwright/test'
import report from './fixtures/replay.json' with { type: 'json' }

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

test('directory resolution selects the returned listed company', async ({ page }) => {
  await page.route('**/api/v1/companies?*', route => route.fulfill({ json: { items: [] } }))
  await page.route('**/api/v1/companies/resolve', route => route.fulfill({ json: { resolved: { ...report.company, legal_name: 'New Bank Limited', symbols: ['NEWBANK'] } } }))
  await page.goto('/')
  await page.getByLabel('Company search').fill('NEWBANK')
  await page.getByRole('button', { name: 'Resolve from exchange directory' }).click()
  await expect(page.getByRole('button', { name: /Start autonomous research/ })).toBeEnabled()
  await expect(page.getByRole('button', { name: /New Bank Limited/ })).toBeVisible()
})
