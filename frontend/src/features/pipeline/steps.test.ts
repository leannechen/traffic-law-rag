import { ev, item, normalRun } from '../../test-utils'
import type { AskEvent } from '../../types/events'
import { type AskState, askReducer, initialAskState } from '../ask/askReducer'
import { formatDuration, pipelineSteps } from './steps'

function run(events: AskEvent[], extra: Parameters<typeof askReducer>[1][] = []): AskState {
  let state = askReducer(initialAskState, { type: 'submit', question: 'Q' })
  for (const event of events) state = askReducer(state, { type: 'event', event })
  for (const action of extra) state = askReducer(state, action)
  return state
}

const statuses = (state: AskState) => pipelineSteps(state).map((s) => s.status)

describe('pipelineSteps', () => {
  it('starts with every step waiting', () => {
    const state = askReducer(initialAskState, { type: 'submit', question: 'Q' })
    expect(statuses(state)).toEqual(['waiting', 'waiting', 'waiting', 'waiting', 'waiting'])
  })

  it('marks finished steps done and the current one running, the rest waiting', () => {
    const state = run(normalRun().slice(0, 9)) // …到 generate 開始、已有第一段文字之前
    expect(statuses(state)).toEqual(['done', 'done', 'done', 'running', 'waiting'])
    const generate = pipelineSteps(state)[3]
    expect(generate.detail).toBe('進行中 · 已引用 0 條')
  })

  it('shows the live citation count while generating', () => {
    const state = run([
      ev('step.started', { step: 'generate' }),
      ev('answer.delta', { text: '罰[[K1:1]]' }),
    ])
    expect(pipelineSteps(state)[3].detail).toBe('進行中 · 已引用 1 條')
  })

  it('is all done for a normal run, with the backend summaries and durations', () => {
    const steps = pipelineSteps(run(normalRun()))
    expect(steps.map((s) => s.status)).toEqual(['done', 'done', 'done', 'done', 'done'])
    expect(steps.map((s) => s.detail)).toEqual([
      '未啟用',
      'top 3',
      '通過',
      '1 個引用',
      '1 / 1 通過',
    ])
    expect(steps[1].durationMs).toBe(200)
  })

  it('gate refusal: stops at the relevance check and skips the last two', () => {
    const state = run([
      ev('step.started', { step: 'rewrite' }),
      ev('step.completed', { step: 'rewrite', duration_ms: 0, summary: '未啟用' }),
      ev('step.started', { step: 'retrieve' }),
      ev('retrieval.results', { items: [item('K0040012:53', 1, 0.2)] }),
      ev('step.completed', { step: 'retrieve', duration_ms: 200, summary: 'top 1' }),
      ev('step.started', { step: 'gate' }),
      ev('step.completed', { step: 'gate', duration_ms: 0, summary: '最高 0.26 < 門檻 0.40' }),
      ev('answer.refused', { reason: 'low_relevance', top_score: 0.26, threshold: 0.4 }),
      ev('run.completed', { total_ms: 264 }),
    ])
    const steps = pipelineSteps(state)
    expect(steps.map((s) => s.status)).toEqual([
      'done',
      'done',
      'insufficient',
      'skipped',
      'skipped',
    ])
    expect(steps[2].label).toBe('相關度不足')
    expect(steps[3].detail).toBe('略過')
  })

  it('model refusal: gate passes, stops at generating, skips the validation', () => {
    const state = run([
      ev('step.completed', { step: 'rewrite', duration_ms: 0, summary: '未啟用' }),
      ev('step.completed', { step: 'retrieve', duration_ms: 1, summary: 'top 5' }),
      ev('step.completed', { step: 'gate', duration_ms: 0, summary: '最高 0.55 ≥ 門檻 0.40' }),
      ev('step.started', { step: 'generate' }),
      ev('step.completed', { step: 'generate', duration_ms: 1700, summary: '條文不足，模型拒答' }),
      ev('answer.refused', { reason: 'out_of_scope', top_score: 0.55, threshold: 0.4 }),
    ])
    const steps = pipelineSteps(state)
    expect(steps.map((s) => s.status)).toEqual(['done', 'done', 'done', 'insufficient', 'skipped'])
    expect(steps[3].label).toBe('條文不足')
  })

  it('stopped: the running step shows as stopped, later steps keep waiting', () => {
    const state = run(normalRun().slice(0, 9), [{ type: 'stop' }])
    expect(statuses(state)).toEqual(['done', 'done', 'done', 'stopped', 'waiting'])
  })
})

describe('formatDuration', () => {
  it('formats milliseconds as seconds and shows a dash when unknown', () => {
    expect(formatDuration(3200)).toBe('3.2s')
    expect(formatDuration(0)).toBe('0.0s')
    expect(formatDuration(null)).toBe('—')
  })
})
