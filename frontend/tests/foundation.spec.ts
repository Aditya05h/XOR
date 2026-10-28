import { test, expect } from '@playwright/test'

test('real API renders reference geometry, selection, zoom and reset', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (['error', 'warning'].includes(message.type())) errors.push(message.text()) })
  await page.goto('/')
  await expect(page.getByText('API connected', { exact: false })).toBeVisible()
  await expect(page.getByRole('button', { name: /^Inspect R-/ })).toHaveCount(12)
  await page.getByRole('button', { name: 'R-04', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'R-04' })).toBeVisible()
  await expect(page.getByText('Not connected', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click()
  await expect(page.getByLabel('Zoom level')).toHaveText('110%')
  await page.getByRole('button', { name: 'Reset view' }).click()
  await expect(page.getByLabel('Zoom level')).toHaveText('100%')
  await expect(page.getByRole('heading', { name: 'The facility' })).toBeVisible()
  await expect(page.locator('.selected')).toHaveCount(0)
  await page.screenshot({ path: '../tmp/foundation-desktop.png', fullPage: true })
  expect(errors).toEqual([])
})

test('keyboard selection and reduced motion work at mobile width', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  const rack = page.getByRole('button', { name: 'Inspect R-09', exact: true })
  await rack.focus()
  await rack.press('Enter')
  await expect(page.getByRole('heading', { name: 'R-09' })).toBeVisible()
  await expect(page.locator('.rack-body').first()).toHaveCSS('opacity', '1')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy()
  await page.screenshot({ path: '../tmp/foundation-mobile.png', fullPage: true })
})

test('API failure is recoverable without fabricated facility data', async ({ page }) => {
  await page.route('**/api/bootstrap', route => route.fulfill({ status: 503, body: 'Unavailable' }))
  await page.goto('/')
  await expect(page.getByRole('alert')).toContainText('Could not load the facility')
  await expect(page.getByRole('button', { name: /^Inspect R-/ })).toHaveCount(0)
  await page.unroute('**/api/bootstrap')
  await page.getByRole('button', { name: 'Retry connection' }).click()
  await expect(page.getByRole('button', { name: /^Inspect R-/ })).toHaveCount(12)
})
