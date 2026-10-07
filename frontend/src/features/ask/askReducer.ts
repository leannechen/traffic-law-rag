import type {
  AskEvent,
  RefusalReason,
  RetrievalItem,
  ServerErrorCode,
  StepName,
} from '../../types/events'
import { articleIdOf } from './articles'

export type AskPhase = 'idle' | 'streaming' | 'done' | 'refused' | 'stopped' | 'error'

export type Segment = { kind: 'text'; text: string } | { kind: 'citation'; articleId: string }

export type StepState = { status: 'running' | 'done'; durationMs?: number; summary?: string }

export type AskErrorCode =
  | ServerErrorCode
  | 'rate_limited'
  | 'invalid_question'
  | 'http_error'
  | 'network_error'
  | 'stream_interrupted'

export type AskError = {
  code: AskErrorCode
  message?: string
  retryAfter?: number
  /** code 為 http_error 時的 HTTP 狀態碼 */
  status?: number
}

export type AskState = {
  phase: AskPhase
  question: string
  runId: string | null
  steps: Partial<Record<StepName, StepState>>
  currentStep: StepName | null
  queries: string[]
  results: RetrievalItem[]
  segments: Segment[]
  cited: string[]
  refusal: { reason: RefusalReason; topScore: number | null; threshold: number } | null
  validation: { valid: string[]; invalid: string[] } | null
  totalMs: number | null
  error: AskError | null
}

export type AskAction =
  | { type: 'submit'; question: string }
  | { type: 'event'; event: AskEvent }
  | { type: 'stop' }
  | { type: 'stream.ended' }
  | { type: 'failed'; error: AskError }
  | { type: 'reset' }

export const initialAskState: AskState = {
  phase: 'idle',
  question: '',
  runId: null,
  steps: {},
  currentStep: null,
  queries: [],
  results: [],
  segments: [],
  cited: [],
  refusal: null,
  validation: null,
  totalMs: null,
  error: null,
}

const MARKER = /\[\[([^[\]]+)\]\]/g

/** 一段 delta 切成文字與引用標記。後端保證標記不會被切在兩個 delta 之間。 */
export function splitMarkers(text: string): Segment[] {
  const segments: Segment[] = []
  let last = 0
  for (const match of text.matchAll(MARKER)) {
    if (match.index > last) segments.push({ kind: 'text', text: text.slice(last, match.index) })
    if (match[1] !== 'REFUSE') segments.push({ kind: 'citation', articleId: articleIdOf(match[1]) })
    last = match.index + match[0].length
  }
  if (last < text.length) segments.push({ kind: 'text', text: text.slice(last) })
  return segments
}

function appendSegments(current: Segment[], added: Segment[]): Segment[] {
  const next = [...current]
  for (const segment of added) {
    const tail = next[next.length - 1]
    if (segment.kind === 'text' && tail?.kind === 'text') {
      next[next.length - 1] = { kind: 'text', text: tail.text + segment.text }
    } else {
      next.push(segment)
    }
  }
  return next
}

function withCited(cited: string[], articleId: string): string[] {
  return cited.includes(articleId) ? cited : [...cited, articleId]
}

function applyEvent(state: AskState, event: AskEvent): AskState {
  switch (event.type) {
    case 'run.started':
      return { ...state, runId: event.run_id }
    case 'step.started':
      return {
        ...state,
        currentStep: event.data.step,
        steps: { ...state.steps, [event.data.step]: { status: 'running' } },
      }
    case 'step.completed':
      return {
        ...state,
        steps: {
          ...state.steps,
          [event.data.step]: {
            status: 'done',
            durationMs: event.data.duration_ms,
            summary: event.data.summary,
          },
        },
      }
    case 'rewrite.result':
      return { ...state, queries: event.data.queries }
    case 'retrieval.results':
      return { ...state, results: event.data.items }
    case 'answer.delta': {
      const added = splitMarkers(event.data.text)
      let cited = state.cited
      for (const segment of added) {
        if (segment.kind === 'citation') cited = withCited(cited, segment.articleId)
      }
      return { ...state, segments: appendSegments(state.segments, added), cited }
    }
    case 'answer.citation':
      return { ...state, cited: withCited(state.cited, articleIdOf(event.data.chunk_id)) }
    case 'answer.refused':
      return {
        ...state,
        phase: 'refused',
        currentStep: null,
        refusal: {
          reason: event.data.reason,
          topScore: event.data.top_score,
          threshold: event.data.threshold,
        },
      }
    case 'validate.result':
      return { ...state, validation: event.data }
    case 'run.completed':
      return {
        ...state,
        phase: state.refusal ? 'refused' : 'done',
        currentStep: null,
        totalMs: event.data.total_ms,
      }
    case 'error':
      return {
        ...state,
        phase: 'error',
        currentStep: null,
        error: { code: event.data.code, message: event.data.message },
      }
  }
}

export function askReducer(state: AskState, action: AskAction): AskState {
  switch (action.type) {
    case 'submit':
      return { ...initialAskState, phase: 'streaming', question: action.question }
    case 'reset':
      return initialAskState
    case 'stop':
      return state.phase === 'streaming' ? { ...state, phase: 'stopped', currentStep: null } : state
    case 'stream.ended':
      // 串流結束卻沒有 run.completed、error 或拒答：連線中途斷了
      return state.phase === 'streaming'
        ? { ...state, phase: 'error', currentStep: null, error: { code: 'stream_interrupted' } }
        : state
    case 'failed':
      return state.phase === 'streaming'
        ? { ...state, phase: 'error', currentStep: null, error: action.error }
        : state
    case 'event':
      // 已停止、已出錯、已完成後遲到的事件一律忽略；拒答後只收 run.completed（取耗時）
      if (state.phase === 'streaming') return applyEvent(state, action.event)
      if (state.phase === 'refused' && action.event.type === 'run.completed') {
        return applyEvent(state, action.event)
      }
      return state
  }
}
