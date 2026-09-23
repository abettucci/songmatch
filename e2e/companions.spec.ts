import { test, expect } from '@playwright/test'
test('companions route is protected until there is a local seeded session', async ({ page }) => {
  await page.goto('/companions')
  await expect(page).toHaveURL(/auth/)
})
