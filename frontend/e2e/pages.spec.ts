import { expect, test } from '@playwright/test'

test('評估頁顯示發布的評估結果', async ({ page }) => {
  await page.goto('/eval')
  await expect(page.getByRole('heading', { name: '這個系統答得有多準？' })).toBeVisible()
  await expect(page.getByText('題數 3 題（範圍外 1 題）')).toBeVisible()
  await expect(page.getByRole('region', { name: '指標' })).toContainText('0.75')
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(4) // 表頭 + 3 題

  await page.getByRole('button', { name: '範圍外' }).click()
  await expect(page.getByRole('table').getByRole('row')).toHaveCount(2)
  await page.getByRole('button', { name: '展開 q03' }).click()
  await expect(page.getByText('範圍外：應該拒答')).toBeVisible()
})

test('關於頁與頁首導覽', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: '關於' }).click()
  await expect(page).toHaveURL(/\/about$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('只根據條文回答')
  await page.getByRole('link', { name: '評估結果' }).click()
  await expect(page).toHaveURL(/\/eval$/)
})

test('外觀切換：選擇會被記住（重新整理後仍然是暗色）', async ({ page }) => {
  await page.goto('/')
  const toggle = page.getByRole('button', { name: /外觀：/ })
  await expect(toggle).toHaveAccessibleName(/跟隨系統/)
  await toggle.click() // → 亮色
  await toggle.click() // → 暗色
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')

  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.getByRole('button', { name: /外觀：暗色/ })).toBeVisible()
})
