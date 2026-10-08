import { test, expect } from '@playwright/test'

test('dashboard shell loads', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Signal Research' })).toBeVisible()
  await expect(page.getByText('Investigate a listed financial business')).toBeVisible()
})
