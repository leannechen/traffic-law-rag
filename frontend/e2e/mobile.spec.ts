import { expect, test } from '@playwright/test'

test('手機：兩個分頁，點引用標記開條文抽屜，上一則／下一則切換', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /紅燈右轉會被罰多少錢/ }).click()
  await expect(page.getByRole('button', { name: '重新提問' })).toBeVisible()

  // 沒有水平捲動
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)

  await page.getByRole('button', { name: '測試條例 §53', exact: true }).click()
  const drawer = page.getByRole('dialog')
  await expect(drawer).toContainText('前項測試條文乙。')
  await expect(drawer.getByRole('button', { name: '← 上一則' })).toBeDisabled()
  await drawer.getByRole('button', { name: '下一則 →' }).click()
  await expect(drawer).toContainText('測試條文丙')

  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()

  // 過程與依據分頁：預設展開、直式列表
  await page.getByRole('tab', { name: '過程與依據' }).click()
  await expect(page.getByRole('list', { name: '處理步驟' }).getByRole('listitem')).toHaveCount(5)
  await expect(page.getByRole('complementary', { name: '依據' })).toContainText('已引用 2')
})

test('手機首頁：輸入框與提問按鈕是分開的兩塊', async ({ page }) => {
  await page.goto('/')
  const box = await page.getByRole('textbox', { name: '你的問題' }).boundingBox()
  const button = await page.getByRole('button', { name: /提問/ }).boundingBox()
  expect(box && button && button.y >= box.y + box.height).toBe(true)
  expect(button?.width).toBeGreaterThan(300) // 整行寬
})
