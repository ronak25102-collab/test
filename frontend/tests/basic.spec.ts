import { test, expect } from '@playwright/test'

test('dashboard shell loads', async ({ page }) => {
  await page.route('**/api/v1/companies?*', route => route.fulfill({ json: { items: [] } }))
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Beyond', exact: true })).toBeVisible()
  await expect(page.getByText('Investigate a listed financial business')).toBeVisible()
})
