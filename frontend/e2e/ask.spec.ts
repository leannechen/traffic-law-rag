import { expect, test } from '@playwright/test'

// 假後端（backend/tests/e2e_server.py）固定的題目與條文
const RED = '紅燈右轉會被罰多少錢？'
const DRUNK = '酒駕被抓到會有什麼處罰？'
const WEATHER = '今天天氣怎麼樣？'

test.describe('問答', () => {
  test('點範例問題 → 看到答案、引用與依據，並能查看條文全文', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: new RegExp(RED) }).click()

    // 串流完成後才會出現「重新提問」
    await expect(page.getByRole('button', { name: '重新提問' })).toBeVisible()
    const answer = page.getByRole('region', { name: '答案' })
    await expect(answer).toContainText('測試回答第一段')
    await expect(answer).not.toContainText('[[') // 引用標記不會露出原始格式

    // 引用標記是按鈕；預設第一個引用是 active
    const first = answer.getByRole('button', { name: '測試條例 §53', exact: true })
    const second = answer.getByRole('button', { name: '測試條例 §53-1' })
    await expect(first).toHaveAttribute('aria-pressed', 'true')
    await second.click()
    await expect(second).toHaveAttribute('aria-pressed', 'true')
    await expect(first).toHaveAttribute('aria-pressed', 'false')

    // 依據：已引用在上，並可開啟下方的全文面板
    const evidence = page.getByRole('complementary', { name: '依據' })
    await expect(evidence).toContainText('已引用 2 · 檢索到 3')
    await evidence.getByRole('button', { name: '查看測試條例 第 53 條全文' }).click()
    const panel = page.getByRole('region', { name: '條文全文', exact: true })
    await expect(panel).toContainText('前項測試條文乙。')

    // Esc 關閉，焦點回到原本的按鈕
    await page.keyboard.press('Escape')
    await expect(panel).toBeHidden()
    await expect(evidence.getByRole('button', { name: '查看測試條例 第 53 條全文' })).toBeFocused()
  })

  test('依項切分的條文：全文面板顯示整條', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: new RegExp(DRUNK) }).click()
    await expect(page.getByRole('button', { name: '重新提問' })).toBeVisible()
    await page.getByRole('button', { name: '查看測試條例 第 35 條全文' }).click()
    const panel = page.getByRole('region', { name: '條文全文', exact: true })
    await expect(panel).toContainText('第一項的測試內容')
    await expect(panel).toContainText('被切成兩塊的長條文')
  })

  test('範圍外問題 → 拒答，並說明為什麼不回答', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('textbox', { name: '你的問題' }).fill(WEATHER)
    await page.getByRole('button', { name: /提問/ }).click()

    await expect(page.getByText('資料範圍內找不到相關規定')).toBeVisible()
    await expect(page.getByText('0.20 ＜ 門檻 0.40')).toBeVisible()
    const steps = page.getByRole('list', { name: '處理步驟' })
    await expect(steps.getByRole('listitem').nth(2)).toContainText('相關度不足')
    await expect(steps.getByRole('listitem').nth(3)).toContainText('略過')
    await expect(page.getByRole('complementary', { name: '收錄範圍' })).toContainText(
      '測試用處罰條例',
    )
  })

  test('串流中可以按「停止」，答案標示為不完整', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: new RegExp(DRUNK) }).click()
    await page.getByRole('button', { name: '停止' }).click()
    await expect(page.getByText('你已停止產生，答案不完整')).toBeVisible()
    await expect(page.getByRole('button', { name: '重新產生' })).toBeVisible()
  })

  test('檢索過程：完成後維持展開，可以收合再展開', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: new RegExp(RED) }).click()
    await expect(page.getByRole('button', { name: '重新提問' })).toBeVisible()
    const toggle = page.getByRole('button', { name: /檢索過程/ })
    const steps = page.getByRole('list', { name: '處理步驟' })
    await expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await expect(toggle).toContainText('5 個步驟完成')
    await expect(steps.getByRole('listitem')).toHaveCount(5)
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await expect(steps).toHaveCount(0)
    await toggle.click()
    await expect(steps.getByRole('listitem')).toHaveCount(5)
  })
})

test.describe('網址', () => {
  test('問題在網址裡：重新整理會重新提問，上一頁回到首頁', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: new RegExp(RED) }).click()
    await expect(page.getByRole('button', { name: '重新提問' })).toBeVisible()
    await expect(page).toHaveURL(/\/\?q=/)
    expect(decodeURIComponent(new URL(page.url()).searchParams.get('q') ?? '')).toBe(RED)

    await page.reload()
    await expect(page.getByRole('region', { name: '答案' })).toContainText('測試回答第一段')

    await page.goBack()
    await expect(page.getByRole('textbox', { name: '你的問題' })).toBeVisible()
  })

  test('直接開分享連結就會提問', async ({ page }) => {
    await page.goto(`/?q=${encodeURIComponent(WEATHER)}`)
    await expect(page.getByText('資料範圍內找不到相關規定')).toBeVisible()
    await expect(page).toHaveTitle(new RegExp(WEATHER))
  })
})
