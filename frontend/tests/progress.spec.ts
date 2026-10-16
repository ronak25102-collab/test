import { expect, test } from '@playwright/test'
import report from './fixtures/replay.json' with { type: 'json' }

test('project research agents show actual worker events and unfinished work stays incomplete', async ({ page }) => {
  let status = 'normalizing'
  let posts = 0
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() === 'POST') posts++
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [] } })
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/history')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [
      { sequence: 1, stage: 'extracting', event_type: 'research_agent_started', public_summary: 'Page verifier 1: started' },
      { sequence: 2, stage: 'extracting', event_type: 'research_agent_started', public_summary: 'Page verifier 2: started' },
      { sequence: 3, stage: 'extracting', event_type: 'research_agent_completed', public_summary: 'Page verifier 1: completed after 1.2s' },
    ] } })
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff,
      mode: 'replay', status, stage: status, progress: { facts_verified: 6 }, limitations: [] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  const agents = page.getByRole('list', { name: 'Research agents' })
  await expect(agents.getByText('Complete', { exact: true })).toBeVisible()
  await expect(agents.getByText('Working', { exact: true })).toBeVisible()
  status = 'failed'
  await expect(agents.getByText('Incomplete', { exact: true })).toBeVisible({ timeout: 8000 })
  await expect(agents.getByText('Working', { exact: true })).toHaveCount(0)
  expect(posts).toBe(0)
})

test('starting research reveals a financial journey driven by actual stage updates', async ({ page }) => {
  let stage = 'queued'
  const visited = ['queued']
  const mutations: string[] = []
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() === 'POST') mutations.push(path)
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [], demo_time_warning: false } })
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: stage === 'queued' ? 1 : 0 } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/runs') && route.request().method() === 'POST') return route.fulfill({ json: { run_id: report.run_id } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: visited.map((item, i) => ({ sequence: i + 1, stage: item, public_summary: `Worker reported ${item}` })) } })
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'replay', status: stage, stage, progress: { sources_found: stage === 'queued' ? 0 : 8, documents_parsed: 4, calculations_completed: 2, counterevidence_checks: 0 }, limitations: [] } })
  })
  await page.goto('/?view=workspace')
  await page.getByRole('button', { name: /SYNTHBANK/ }).click()
  await page.getByRole('combobox', { name: 'Mode', exact: true }).selectOption('replay')
  await page.getByRole('button', { name: /Start autonomous research/ }).click()
  const panel = page.getByRole('region', { name: 'Investigation in progress', exact: true })
  await expect(panel).toBeFocused()
  await expect(panel.getByText('Waiting for a worker', { exact: true })).toBeVisible()
  const bar = panel.getByRole('progressbar', { name: 'Research stage progress', exact: true })
  await expect(bar).toHaveAttribute('aria-valuenow', '0')
  await expect(panel.locator('.finance-coin')).toHaveCount(0)

  stage = 'extracting'; visited.push(stage)
  await expect(bar).toHaveAttribute('aria-valuenow', '4')
  await expect(bar).toHaveAttribute('aria-valuetext', /Stage 5 of 11/)
  await expect(panel.getByRole('button', { name: /02 Examine Current stage/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(panel.getByText('Reading the financial filings', { exact: true })).toBeVisible()
  await expect(panel.locator('.journey-counters > div').first()).toContainText('8')

  const previewReport = panel.getByRole('button', { name: /04 Report Ahead/ })
  await previewReport.focus(); await page.keyboard.press('Space')
  await expect(previewReport).toHaveAttribute('aria-pressed', 'true')
  await expect(panel.getByRole('heading', { name: 'Build the report', exact: true })).toBeVisible()
  await expect(bar).toHaveAttribute('aria-valuenow', '4')
  stage = 'challenging'; visited.push(stage)
  await expect(bar).toHaveAttribute('aria-valuenow', '8')
  await expect(previewReport).toHaveAttribute('aria-pressed', 'true')
  await panel.getByRole('button', { name: /Follow live stage/ }).click()
  await expect(panel.getByRole('button', { name: /03 Challenge Current stage/ })).toHaveAttribute('aria-pressed', 'true')
  stage = 'composing'; visited.push(stage)
  await expect(bar).toHaveAttribute('aria-valuenow', '10')
  await expect(panel.getByRole('button', { name: /04 Report Current stage/ })).toHaveAttribute('aria-pressed', 'true')
  stage = 'completed'; visited.push(stage)
  await expect(page.locator('.money-journey')).not.toBeVisible()
  await expect(page.getByRole('heading', { name: report.discoveries[0].discovery_sentence })).toBeVisible()
  expect(mutations).toEqual(['/api/v1/runs'])
})

test('an interrupted financial journey retains the last known stage and stops its motion', async ({ page }) => {
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: 0 } })
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [], demo_time_warning: false } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [{ sequence: 1, stage: 'extracting', public_summary: 'Reading source passages' }, { sequence: 2, stage: 'failed', public_summary: 'Controlled interruption' }] } })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'live', status: 'failed', stage: 'failed', progress: { sources_found: 5 }, limitations: ['Controlled interruption'] } })
  })
  await page.goto(`/?run=${report.run_id}`)
  const panel = page.getByRole('region', { name: 'Investigation failed', exact: true })
  await expect(panel.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '4')
  await expect(panel.getByText('Research stopped', { exact: true })).toBeVisible()
  await expect(panel.locator('.finance-coin')).toHaveCSS('animation-play-state', 'paused')
  await expect(panel.getByRole('button', { name: 'Resume from saved work', exact: true })).toBeVisible()
  await expect(panel.getByText('Controlled interruption', { exact: true }).first()).toBeVisible()
})

test('financial motion respects pause, reduced motion, and the mobile viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/reviews/progress.html')
  await expect(page.locator('.finance-coin')).toHaveCSS('animation-name', 'none')
  await expect(page.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '4')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: /03 Challenge Ahead/ }).click()
  await expect(page.getByRole('heading', { name: 'Challenge the case', exact: true })).toBeVisible()
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.getByRole('button', { name: 'Enable animations', exact: true }).click()
  await page.getByRole('button', { name: 'Pause animations', exact: true }).click()
  await expect(page.locator('.finance-coin')).toHaveCSS('animation-name', 'none')
})
