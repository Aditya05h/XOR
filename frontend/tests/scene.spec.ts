import { test, expect } from '@playwright/test'

test('facility supports keyboard pan and center without changing rack selection', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/')
  const scene = page.getByRole('group', { name: /Isometric facility/ })
  await expect(scene).toBeVisible()
  await scene.focus()
  await scene.press('ArrowLeft')
  await expect(page.locator('.scene-pan')).toHaveAttribute('data-pan-x', '24')
  await scene.press('ArrowUp')
  await expect(page.locator('.scene-pan')).toHaveAttribute('data-pan-y', '24')
  await scene.press('Home')
  await expect(page.locator('.scene-pan')).toHaveAttribute('data-pan-x', '0')
  await expect(page.locator('.scene-pan')).toHaveAttribute('data-pan-y', '0')
  await expect(page.getByRole('button', { name: /^Inspect R-/ })).toHaveCount(12)
  expect(errors).toEqual([])
})
