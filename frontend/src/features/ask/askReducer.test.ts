import { ev, item, normalRun, RUN } from '../../test-utils'
import type { AskEvent } from '../../types/events'
import {
  type AskAction,
  type AskState,
  askReducer,
  initialAskState,
  splitMarkers,
} from './askReducer'

function run(
  events: AskEvent[],
  start: AskState = askReducer(initialAskState, { type: 'submit', question: 'Q' }),
) {
  return events.reduce<AskState>(
    (state, event) => askReducer(state, { type: 'event', event } satisfies AskAction),
    start,
  )
}

describe('splitMarkers', () => {
  it('splits text around citation markers', () => {
    expect(splitMarkers('罰六百元[[K0040012:53]]。')).toEqual([
      { kind: 'text', text: '罰六百元' },
      { kind: 'citation', articleId: 'K0040012:53' },
      { kind: 'text', text: '。' },
    ])
  })

  it('maps a chunk id to its article id and never shows [[REFUSE]]', () => {
    expect(splitMarkers('[[K0040012:35-p2]][[REFUSE]]')).toEqual([
      { kind: 'citation', articleId: 'K0040012:35' },
    ])
  })
})

describe('askReducer', () => {
  it('starts in idle and goes to streaming on submit', () => {
    expect(initialAskState.phase).toBe('idle')
    const s = askReducer(initialAskState, { type: 'submit', question: '問題' })
    expect(s).toMatchObject({ phase: 'streaming', question: '問題' })
  })

  it('walks a normal run to done with answer, citation, validation and timing', () => {
    const s = run(normalRun())
    expect(s.phase).toBe('done')
    expect(s.runId).toBe(RUN)
    expect(s.segments).toEqual([
      { kind: 'text', text: '**重點**依規定罰六百元' },
      { kind: 'citation', articleId: 'K0040012:53' },
      { kind: 'text', text: '。' },
    ])
    expect(s.cited).toEqual(['K0040012:53'])
    expect(s.validation).toEqual({ valid: ['K0040012:53'], invalid: [] })
    expect(s.totalMs).toBe(1300)
    expect(s.steps.retrieve).toMatchObject({ status: 'done', summary: 'top 3' })
  })

  it('tracks the step in progress while streaming', () => {
    const s = run(normalRun().slice(0, 4))
    expect(s.phase).toBe('streaming')
    expect(s.currentStep).toBe('retrieve')
    expect(s.steps.rewrite?.status).toBe('done')
  })

  it('does not count the same citation twice', () => {
    const s = run([
      ev('answer.delta', { text: '甲[[K1:1]]乙[[K1:1]]' }),
      ev('answer.citation', { marker: '[[K1:1]]', chunk_id: 'K1:1' }),
    ])
    expect(s.cited).toEqual(['K1:1'])
  })

  it('moves to refused on answer.refused and keeps the later run.completed timing', () => {
    let s = run([
      ev('retrieval.results', { items: [item('K0040012:53', 1, 0.2)] }),
      ev('answer.refused', { reason: 'low_relevance', top_score: 0.26, threshold: 0.4 }),
    ])
    expect(s.phase).toBe('refused')
    expect(s.refusal).toEqual({ reason: 'low_relevance', topScore: 0.26, threshold: 0.4 })
    s = run([ev('run.completed', { total_ms: 264 })], s)
    expect(s.phase).toBe('refused')
    expect(s.totalMs).toBe(264)
  })

  it('moves to error on an error event and keeps the partial answer', () => {
    const s = run([
      ev('answer.delta', { text: '一半' }),
      ev('error', { code: 'llm_error', message: '回答服務暫時無法使用' }),
    ])
    expect(s.phase).toBe('error')
    expect(s.error).toEqual({ code: 'llm_error', message: '回答服務暫時無法使用' })
    expect(s.segments).toEqual([{ kind: 'text', text: '一半' }])
  })

  it('stop moves streaming to stopped and ignores events that arrive afterwards', () => {
    let s = run([ev('answer.delta', { text: '一半' })])
    s = askReducer(s, { type: 'stop' })
    expect(s.phase).toBe('stopped')
    s = run([ev('answer.delta', { text: '遲到' }), ev('run.completed', { total_ms: 1 })], s)
    expect(s.phase).toBe('stopped')
    expect(s.segments).toEqual([{ kind: 'text', text: '一半' }])
  })

  it('treats a stream that ends without run.completed as an interruption', () => {
    const s = askReducer(run([ev('answer.delta', { text: '一半' })]), { type: 'stream.ended' })
    expect(s.phase).toBe('error')
    expect(s.error?.code).toBe('stream_interrupted')
  })

  it('does not turn a finished run into an error when the stream ends', () => {
    const s = askReducer(run(normalRun()), { type: 'stream.ended' })
    expect(s.phase).toBe('done')
  })

  it('records request failures such as rate limiting', () => {
    const s = askReducer(askReducer(initialAskState, { type: 'submit', question: 'Q' }), {
      type: 'failed',
      error: { code: 'rate_limited', retryAfter: 42 },
    })
    expect(s).toMatchObject({ phase: 'error', error: { code: 'rate_limited', retryAfter: 42 } })
  })

  it('reset goes back to the initial state', () => {
    expect(askReducer(run(normalRun()), { type: 'reset' })).toEqual(initialAskState)
  })
})
