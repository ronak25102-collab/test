import { expect, test } from '@playwright/test'
import report from './fixtures/replay.json' with { type: 'json' }

for (const status of ['queued', 'extracting']) {
  test(`clearing waiting runs preserves ${status === 'queued' ? 'saved work for the displayed run' : 'the active investigation'}`, async ({ page }) => {
    let waiting = 2
    let currentStatus = status
    const mutations: string[] = []
    await page.route('**/api/v1/**', route => {
      const path = new URL(route.request().url()).pathname
      if (route.request().method() === 'POST') mutations.push(path)
      if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [], demo_time_warning: false } })
      if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
      if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
      if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: waiting } })
      if (path.endsWith('/runs/queue/clear')) {
        waiting = 0
        if (currentStatus === 'queued') currentStatus = 'cancelled'
        return route.fulfill({ json: { cancelled_count: 2, run_ids: status === 'queued' ? [report.run_id, 'other-run'] : ['other-run', 'another-run'] } })
      }
      return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'replay', status: currentStatus, stage: currentStatus, progress: {}, limitations: [] } })
    })
    await page.goto(`/?run=${report.run_id}`)
    const queue = page.getByRole('region', { name: 'Research queue', exact: true })
    await expect(queue.getByText('2 waiting runs', { exact: true })).toBeVisible()
    const clear = queue.getByRole('button', { name: 'Clear queue', exact: true })
    await clear.evaluate(el => { (el as HTMLButtonElement).click(); (el as HTMLButtonElement).click() })
    await expect(queue.getByText(/2 waiting runs cancelled. Saved work/)).toBeVisible()
    await expect(queue.getByText('0 waiting runs', { exact: true })).toBeVisible()
    await expect(clear).toBeDisabled()
    await expect(page.getByRole('heading', { name: status === 'queued' ? 'Investigation cancelled' : 'Investigation in progress', exact: true })).toBeVisible()
    if (status === 'queued') await expect(page.getByRole('button', { name: 'Resume from saved work', exact: true })).toBeVisible()
    expect(mutations).toEqual(['/api/v1/runs/queue/clear'])
  })
}

test('queue errors remain visible and can be retried without claiming success', async ({ page }) => {
  let clears = 0
  let waiting = 1
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/health/configuration')) return route.fulfill({ json: { ready: true, issues: [], demo_time_warning: false } })
    if (path.endsWith('/runs/queue')) return route.fulfill({ json: { queued_count: waiting } })
    if (path.endsWith('/runs/queue/clear')) {
      clears++
      if (clears === 1) return route.fulfill({ status: 503, json: { message: 'Queue clear temporarily unavailable.' } })
      waiting = 0
      return route.fulfill({ json: { cancelled_count: 1, run_ids: ['waiting-run'] } })
    }
    return route.fulfill({ json: { items: [] } })
  })
  await page.goto('/?view=workspace')
  const queue = page.getByRole('region', { name: 'Research queue', exact: true })
  await queue.getByRole('button', { name: 'Clear queue', exact: true }).click()
  await expect(queue.getByText('Queue clear temporarily unavailable.')).toBeVisible()
  await expect(queue.getByText(/cancelled. Saved work/)).not.toBeVisible()
  await queue.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(queue.getByText(/1 waiting run cancelled. Saved work/)).toBeVisible()
  expect(clears).toBe(2)
})
