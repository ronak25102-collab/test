import { expect, type Page, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/**', route => route.fulfill({ json: route.request().url().includes('configuration')
    ? { ready: true, issues: [], demo_time_warning: false } : route.request().url().endsWith('/runs/queue') ? { queued_count: 0 } : { items: [] } }))
})

async function scrollJourney(page: Page, progress: number) {
  await page.evaluate(progress => {
    const track = document.querySelector<HTMLElement>('.scroll-journey-track')!
    const stage = document.querySelector<HTMLElement>('.scroll-journey-stage')!
    const top = Number.parseFloat(getComputedStyle(stage).top)
    window.scrollTo({ top: scrollY + track.getBoundingClientRect().top - top + (track.offsetHeight - stage.offsetHeight) * progress, behavior: 'instant' })
  }, progress)
}

test('native scrolling pins the scene, advances all chapters and reverses without research requests', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  const mutations: string[] = []
  page.on('request', request => { if (request.method() === 'POST') mutations.push(request.url()) })
  await page.goto('/')
  await page.getByRole('button', { name: 'Skip intro' }).click()
  const stage = page.locator('.scroll-journey-stage')
  for (const [progress, chapter] of [[.12, 0], [.5, 1], [.88, 2], [.12, 0]]) {
    await scrollJourney(page, progress)
    await expect(stage).toHaveAttribute('data-chapter', String(chapter))
    await expect.poll(() => stage.evaluate(el => Math.round(el.getBoundingClientRect().top))).toBe(106)
    await expect(page.locator('.scroll-journey-art-layer.is-active')).toHaveCount(1)
    await expect(page.locator(`#step-detail-${chapter}`)).toHaveAttribute('aria-hidden', 'false')
  }
  await page.getByRole('button', { name: '03 Challenge the explanation.', exact: true }).click()
  await expect.poll(() => stage.evaluate(el => Number((el as HTMLElement).style.getPropertyValue('--scroll-journey-progress')))).toBeGreaterThan(.66)
  await expect(stage).toHaveAttribute('data-chapter', '2')
  expect(mutations).toEqual([])
})

test('short mobile screens fit the pinned chapter and keep touch navigation usable', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 })
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await page.goto('/')
  await page.getByRole('button', { name: 'Skip intro' }).click()
  await scrollJourney(page, .5)
  const stage = page.locator('.scroll-journey-stage')
  await expect(stage).toHaveAttribute('data-chapter', '1')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  expect(await stage.evaluate(el => el.getBoundingClientRect().bottom <= innerHeight)).toBe(true)
  await page.getByRole('button', { name: '03 Challenge the explanation.', exact: true }).click()
  await expect(stage).toHaveAttribute('data-chapter', '2')
})

test('reduced motion removes pinning and keyboard controls still open every chapter', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/')
  const stage = page.locator('.scroll-journey-stage')
  await expect(stage).toHaveCSS('position', 'relative')
  for (const [index, name] of ['01 Find the original evidence.', '02 Connect the numbers.', '03 Challenge the explanation.'].entries()) {
    const button = page.getByRole('button', { name, exact: true })
    await button.focus()
    await button.press('Enter')
    await expect(button).toHaveAttribute('aria-expanded', 'true')
    await expect(page.locator(`#step-detail-${index} p`)).toBeVisible()
  }
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await expect(stage).toHaveCSS('position', 'sticky')
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(stage).toHaveCSS('position', 'relative')
})
