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

test('首頁輸入框換行時會長高，不出現多餘的捲軸', async ({ page }) => {
  await page.goto('/')
  const input = page.getByRole('textbox', { name: '你的問題' })
  const overflows = () => input.evaluate((el) => el.scrollHeight > el.clientHeight)
  const height = () => input.evaluate((el) => el.clientHeight)

  // 桌面版平常只有一行高（畫板 Main），不是兩行
  const empty = await height()
  expect(empty).toBeLessThan(80)

  await input.fill('騎機車沒戴安全帽')
  expect(await overflows()).toBe(false)
  const oneLine = await height()
  expect(oneLine).toBe(empty)

  await input.press('Shift+Enter')
  await input.pressSequentially('會被罰多少')
  await input.press('Shift+Enter')
  await input.pressSequentially('還會被記點嗎')
  expect(await overflows()).toBe(false)
  expect(await height()).toBeGreaterThan(oneLine)
})

test('首頁：頁首沒有產品名稱那一列，收錄範圍是五欄表格', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('交通法規白話文搜尋')
  const table = page.getByRole('table', { name: '收錄法規' })
  await expect(table.getByRole('row')).toHaveCount(2) // 表頭 + 假後端的 1 部法規
  await expect(table.getByRole('columnheader')).toHaveCount(5)
  await expect(page.getByRole('link', { name: '交通法規資料庫' })).toBeHidden()
  await expect(page.getByRole('link', { name: /GitHub/ })).toHaveCount(0) // repo 公開前不顯示
})
