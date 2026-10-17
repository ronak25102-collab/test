import { expect, test } from '@playwright/test'
import report from './fixtures/replay.json' with { type: 'json' }

test('setup opens a dedicated progress page and completion opens report pages without creating another run', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  let status = 'queued'
  const posts: string[] = []
  const run = () => ({ id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'replay', status, stage: status, progress: {}, limitations: [] })
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() === 'POST') posts.push(path)
    if (path.endsWith('/configuration')) return route.fulfill({ json: { ready: true, issues: [] } })
    if (path.endsWith('/queue')) return route.fulfill({ json: { queued_count: status === 'queued' ? 1 : 0 } })
    if (path.endsWith('/history')) return route.fulfill({ json: { items: [run()] } })
    if (path.endsWith('/companies')) return route.fulfill({ json: { items: [report.company] } })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    if (path.endsWith('/runs') && route.request().method() === 'POST') return route.fulfill({ json: { run_id: report.run_id } })
    return route.fulfill({ json: run() })
  })
  await page.goto('/?view=workspace')
  await page.getByRole('button', { name: /SYNTHBANK/ }).click()
  await page.getByRole('combobox', { name: 'Mode', exact: true }).selectOption('replay')
  await page.getByRole('button', { name: /Start autonomous research/ }).click()
  await expect(page).toHaveURL(/view=progress&run=/)
  await expect(page.getByRole('heading', { name: 'Following the evidence.' })).toBeVisible()
  await expect(page.getByRole('progressbar', { name: 'Research stage progress' })).toBeVisible()
  await expect(page.getByLabel('Company search')).toHaveCount(0)
  await expect(page.getByLabel('Saved investigations')).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole('progressbar', { name: 'Research stage progress' })).toBeVisible()
  status = 'completed'
  await expect(page).toHaveURL(/view=report&run=.*section=overview/)
  await expect(page.getByRole('heading', { name: report.discoveries[0].discovery_sentence })).toBeVisible()
  await expect(page.getByRole('progressbar', { name: 'Research stage progress' })).toHaveCount(0)
  const navigation = page.getByRole('navigation', { name: 'Report sections' })
  for (const [section, label, heading] of [
    ['figures', 'Verified figures', 'Verified source figures'],
    ['calculations', 'Calculations', 'Reproducible calculations'],
    ['sources', 'Sources', 'Source library'],
    ['review', 'Review', 'The other side of the story.'],
  ]) {
    await navigation.getByRole('link', { name: new RegExp(label) }).click()
    await expect(page).toHaveURL(new RegExp(`section=${section}`))
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
    await expect(navigation.getByRole('link', { name: new RegExp(label) })).toHaveAttribute('aria-current', 'page')
    await expect(page.getByLabel('Company search')).toHaveCount(0)
  }
  await page.reload()
  await expect(page.getByRole('heading', { name: 'The other side of the story.' })).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(/section=sources/)
  await expect(page.getByRole('heading', { name: 'Source library' })).toBeVisible()
  await page.goForward()
  await expect(page).toHaveURL(/section=review/)
  expect(posts).toEqual(['/api/v1/runs'])
})

test('a direct report section link restores its page and stays usable on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.route('**/api/v1/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/report')) return route.fulfill({ json: report })
    if (path.endsWith('/events')) return route.fulfill({ json: { items: [] } })
    if (path.endsWith('/configuration')) return route.fulfill({ json: { ready: true, issues: [] } })
    return route.fulfill({ json: { id: report.run_id, company: report.company, as_of: report.cutoff, mode: 'replay', status: 'completed', stage: 'completed', progress: {}, limitations: [] } })
  })
  await page.goto(`/?view=report&run=${report.run_id}&section=calculations`)
  await expect(page.getByRole('heading', { name: 'Reproducible calculations' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Source library' })).toHaveCount(0)
  await expect(page.getByLabel('Filter verified figures')).toHaveCount(0)
  await page.locator('.calculation-card').first().getByText('Calculation inputs', { exact: true }).click()
  await page.getByRole('button', { name: /Inspect input/ }).first().click()
  await expect(page.getByRole('dialog', { name: 'Verified figure evidence' })).toBeVisible()
  await page.keyboard.press('Escape')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'New research', exact: true }).click()
  await expect(page).toHaveURL(/view=workspace/)
  await expect(page.getByLabel('Company search')).toBeVisible()
})
