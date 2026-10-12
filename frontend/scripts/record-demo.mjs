// 錄 README 的 demo GIF：用 Playwright 在真實網站上走一遍，錄成 webm，
// 用 ffmpeg 去掉開頭的載入畫面並縮小，最後用 gifski 合成 GIF。
// 兩個情境各一支，檔案小、載入快：成功回答（happy path）與拒答（bad path）。
//
//   pnpm demo:record                       錄線上版（會呼叫真實模型，兩題約 US$0.02）
//   pnpm demo:record -- --url http://localhost:5173
//
// 需要：brew install ffmpeg gifski；首次要 pnpm exec playwright install chromium
// 輸出：docs/media/demo-answer.gif、docs/media/demo-refusal.gif（中間檔放在系統暫存資料夾）

import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, readdirSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const args = process.argv.slice(2)
const urlFlag = args.indexOf('--url')
const BASE_URL = urlFlag >= 0 ? args[urlFlag + 1] : 'https://traffic-law-rag.fly.dev/'

const VIEWPORT = { width: 1280, height: 720 }
const GIF_WIDTH = 880
const GIF_FPS = 12
const GIF_QUALITY = 70
const OUT_DIR = resolve(fileURLToPath(import.meta.url), '../../../docs/media')

const pause = (ms) => new Promise((r) => setTimeout(r, ms))

// 成功題：看完答案，再展開檢索過程
async function answer(page) {
  await ask(page, '紅燈右轉會被罰多少錢？')
  await page.getByRole('button', { name: '重新提問' }).waitFor({ timeout: 60_000 })
  await pause(1200)
  await page.getByRole('button', { name: /檢索過程/ }).click()
  await pause(2200)
}

// 拒答題：過了相似度門檻，但模型判斷條文不足；等拒答說明出現，再往下捲看「為什麼不回答」
async function refusal(page) {
  await ask(page, '公車專用道可以走嗎？')
  await page.getByText('資料範圍內找不到相關規定').waitFor({ timeout: 60_000 })
  await page.getByText('為什麼不回答').waitFor()
  await pause(1500)
  await page.mouse.wheel(0, 260)
  await pause(2200)
}

const SCENARIOS = [
  { name: 'demo-answer', run: answer },
  { name: 'demo-refusal', run: refusal },
]

// 記下字型載入完成的秒數（page.startAt）；之前的空白畫面與字型跳動不放進 GIF
// （Google Fonts 用 display=swap，第一次載入標題會先用備用字型再換字，是正常現象）
async function ask(page, question) {
  await page.goto(BASE_URL)
  const input = page.getByRole('textbox', { name: '你的問題' })
  await input.waitFor()
  await page.evaluate(() => document.fonts.ready)
  page.startAt = (Date.now() - page.t0) / 1000
  await pause(300)
  await input.click()
  await input.pressSequentially(question, { delay: 90 })
  await pause(500)
  await input.press('Enter')
}

async function record(browser, { name, run }) {
  const work = mkdtempSync(join(tmpdir(), `${name}-`))
  const context = await browser.newContext({
    viewport: VIEWPORT,
    locale: 'zh-TW',
    recordVideo: { dir: work, size: VIEWPORT },
  })
  const page = await context.newPage()
  page.t0 = Date.now()
  await run(page)
  await pause(500)

  const video = page.video()
  await context.close()
  const webm = await video.path()

  const frames = join(work, 'frames')
  mkdirSync(frames)
  execFileSync(
    'ffmpeg',
    [
      ...['-v', 'error', '-ss', String(page.startAt), '-i', webm],
      ...['-vf', `fps=${GIF_FPS},scale=${GIF_WIDTH}:-2:flags=lanczos`],
      join(frames, '%04d.png'),
    ],
    { stdio: 'inherit' },
  )

  mkdirSync(OUT_DIR, { recursive: true })
  const out = join(OUT_DIR, `${name}.gif`)
  const pngs = readdirSync(frames)
    .sort()
    .map((f) => join(frames, f))
  execFileSync(
    'gifski',
    ['--fps', String(GIF_FPS), '--quality', String(GIF_QUALITY), '-o', out, ...pngs],
    { stdio: 'inherit' },
  )
  rmSync(work, { recursive: true, force: true })

  const kb = Math.round(statSync(out).size / 1024)
  console.log(
    `完成：${out}（${pngs.length} 幀，約 ${(pngs.length / GIF_FPS).toFixed(1)} 秒，${kb} KB）`,
  )
}

const browser = await chromium.launch()
for (const scenario of SCENARIOS) await record(browser, scenario)
await browser.close()
