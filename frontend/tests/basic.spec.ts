import { test, expect } from '@playwright/test'

test('dashboard shell loads', async ({ page }) => {
  await page.route('**/api/v1/companies?*', route => route.fulfill({ json: { items: [] } }))
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Beyond home', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Find the next signal. Beyond the numbers.' })).toBeVisible()
  await expect(page.getByLabel('Company search')).toHaveCount(0)
  await page.getByRole('button', { name: 'Launch workspace', exact: true }).click()
  await expect(page.getByText('Investigate a listed financial business')).toBeVisible()
})
