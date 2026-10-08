// 錄 README 的 demo GIF：用 Playwright 在真實網站上走一遍，錄成 webm，
// 再用 ffmpeg 把「送出到答完」那幾秒放慢，最後用 gifski 合成 GIF。
//
//   pnpm demo:record                       錄線上版（會呼叫真實模型，三題約 US$0.03）
//   pnpm demo:record -- --url http://localhost:5173
//
// 需要：brew install ffmpeg gifski；首次要 pnpm exec playwright install chromium
// 輸出：docs/media/demo.gif（中間檔放在系統暫存資料夾）

import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const args = process.argv.slice(2)
const urlFlag = args.indexOf('--url')
const BASE_URL = urlFlag >= 0 ? args[urlFlag + 1] : 'https://traffic-law-rag.fly.dev/'

const VIEWPORT = { width: 1280, height: 720 }
const SLOW = 1 // 送出到答完這段放慢幾倍（1 = 正常速度）
const GIF_WIDTH = 1000
const GIF_FPS = 15
const OUT = resolve(fileURLToPath(import.meta.url), '../../../docs/media/demo.gif')

const work = mkdtempSync(join(tmpdir(), 'demo-'))
const pause = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await chromium.launch()
const context = await browser.newContext({
  viewport: VIEWPORT,
  locale: 'zh-TW',
  recordVideo: { dir: work, size: VIEWPORT },
})
const page = await context.newPage()
const t0 = Date.now()
const now = () => (Date.now() - t0) / 1000
const slowSegments = [] // [開始秒, 結束秒]
let startAt = null // 字型載入完成的時間點；之前的空白畫面與字型跳動不放進 GIF

async function ask(question) {
  await page.goto(BASE_URL)
  const input = page.getByRole('textbox', { name: '你的問題' })
  await input.waitFor()
  // Google Fonts 用 display=swap，第一次載入標題會先用備用字型再換字（正常現象，快取後不會再跳）
  await page.evaluate(() => document.fonts.ready)
  startAt ??= now()
  await pause(300)
  await input.click()
  await input.pressSequentially(question, { delay: 90 })
  await pause(500)
  const start = now()
  await input.press('Enter')
  return start
}

async function finishAnswer(start) {
  await page.getByRole('button', { name: '重新提問' }).waitFor({ timeout: 60_000 })
  slowSegments.push([start, now() + 0.4])
  await pause(400)
}

// 成功題：看完答案，展開檢索過程，再開第一個引用條文的全文
async function success(question, { openArticle }) {
  const start = await ask(question)
  await finishAnswer(start)
  await pause(1200)
  await page.getByRole('button', { name: /檢索過程/ }).click()
  await pause(2200)
  if (openArticle) {
    await page
      .getByRole('button', { name: /^查看.*全文$/ })
      .first()
      .click()
    await pause(2600)
    await page.keyboard.press('Escape')
    await pause(600)
  }
}

// 拒答題：等到拒答說明出現，再往下捲看「為什麼不回答」
async function refusal(question) {
  const start = await ask(question)
  await page.getByText('資料範圍內找不到相關規定').waitFor({ timeout: 60_000 })
  // 「為什麼不回答」的步驟列要等到串流結束才完整
  await page.getByText('為什麼不回答').waitFor()
  slowSegments.push([start, now() + 0.4])
  await pause(1500)
  await page.mouse.wheel(0, 260)
  await pause(2600)
}

await success('紅燈右轉會被罰多少錢？', { openArticle: true })
await success('發生車禍時該怎麼辦？', { openArticle: false })
await refusal('公車專用道可以走嗎？')
await pause(500)

const video = page.video()
await context.close()
await browser.close()
const webm = await video.path()
const total = now()

// 依慢放區段切成「一般／慢放」交錯的片段，再串起來
const parts = []
let cursor = startAt
for (const [s, e] of slowSegments) {
  if (s > cursor) parts.push({ from: cursor, to: s, speed: 1 })
  parts.push({ from: s, to: e, speed: SLOW })
  cursor = e
}
parts.push({ from: cursor, to: total, speed: 1 })

const filters = parts.map(
  (p, i) => `[0:v]trim=start=${p.from}:end=${p.to},setpts=(PTS-STARTPTS)*${p.speed}[v${i}]`,
)
const chain = parts.map((_, i) => `[v${i}]`).join('')
const filter = `${filters.join(';')};${chain}concat=n=${parts.length}:v=1:a=0,fps=${GIF_FPS},scale=${GIF_WIDTH}:-2:flags=lanczos[out]`

const frames = join(work, 'frames')
mkdirSync(frames)
execFileSync(
  'ffmpeg',
  ['-v', 'error', '-i', webm, '-filter_complex', filter, '-map', '[out]', join(frames, '%04d.png')],
  { stdio: 'inherit' },
)

mkdirSync(resolve(OUT, '..'), { recursive: true })
const pngs = readdirSync(frames)
  .sort()
  .map((f) => join(frames, f))
execFileSync('gifski', ['--fps', String(GIF_FPS), '--quality', '80', '-o', OUT, ...pngs], {
  stdio: 'inherit',
})

rmSync(work, { recursive: true, force: true })
console.log(`完成：${OUT}（${pngs.length} 幀，約 ${(pngs.length / GIF_FPS).toFixed(1)} 秒）`)
