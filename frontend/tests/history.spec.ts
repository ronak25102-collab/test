import { test, expect } from '@playwright/test'
import report from './fixtures/replay.json' with { type: 'json' }

test('saved investigations reopen original evidence without starting paid research', async ({ page }) => {
  let created = false
  const run = { id: report.run_id, company: report.company, as_of: report.cutoff,
    mode: 'replay', status: 'completed', stage: 'completed', outcome: 'discovery',
    progress: { facts_verified: 4 }, limitations: [], cold_start: false }
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() === 'POST') created = true
    if (path.endsWith('/history')) return route.fulfill({ json: { items: [run] } })
    if (path.endsWith('/configuration')) return route.fulfill({ json: { ready: true, issues: [] } })
    if (path.endsWith('/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    return route.fulfill({ json: run })
  })
  await page.goto('/?view=workspace')
  const history = page.getByLabel('Saved investigations')
  await history.locator('summary').click()
  await expect(history.getByText(/Synthetic replay/)).toBeVisible()
  await expect(history.getByText(/4 verified facts/)).toBeVisible()
  await history.getByRole('link').click()
  await expect(page).toHaveURL(new RegExp(`run=${report.run_id}`))
  await expect(page.getByRole('heading', { name: report.discoveries[0].discovery_sentence, exact: true })).toBeVisible()
  expect(created).toBe(false)
})
