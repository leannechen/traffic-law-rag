import type { AskState } from '../ask/askReducer'

export type StepId = 'rewrite' | 'retrieve' | 'gate' | 'generate' | 'validate'

/** 等待／進行中／完成／略過／相關度不足（拒答時停在這一步），外加「已停止」。 */
export type StepStatus = 'waiting' | 'running' | 'done' | 'skipped' | 'insufficient' | 'stopped'

export type PipelineStep = {
  id: StepId
  label: string
  status: StepStatus
  /** 一行摘要（直接用後端 step.completed 的 summary） */
  detail: string
  durationMs: number | null
}

export const STEP_ORDER: readonly StepId[] = ['rewrite', 'retrieve', 'gate', 'generate', 'validate']

export const STEP_LABELS: Record<StepId, string> = {
  rewrite: '改寫問題',
  retrieve: '檢索條文',
  gate: '相關度檢查',
  generate: '產生答案',
  validate: '驗證引用',
}

/**
 * 事件序列 → 五個步驟的狀態（PipelineSteps 與「為什麼不回答」共用）。
 * 拒答時：門檻拒答停在「相關度檢查」（後兩步略過）；模型拒答停在「產生答案」（驗證略過）。
 */
export function pipelineSteps(state: AskState): PipelineStep[] {
  const { phase, steps, refusal, cited } = state
  const stoppedAt =
    refusal === null
      ? -1
      : STEP_ORDER.indexOf(refusal.reason === 'low_relevance' ? 'gate' : 'generate')

  return STEP_ORDER.map((id, index): PipelineStep => {
    const reported = steps[id]
    let status: StepStatus = 'waiting'
    if (reported?.status === 'done') status = 'done'
    else if (reported?.status === 'running') {
      status = phase === 'stopped' || phase === 'error' ? 'stopped' : 'running'
    }
    if (stoppedAt >= 0) {
      if (index === stoppedAt) status = 'insufficient'
      else if (index > stoppedAt) status = 'skipped'
    }

    let label = STEP_LABELS[id]
    if (status === 'insufficient') label = id === 'gate' ? '相關度不足' : '條文不足'

    const detail = {
      waiting: '等待中',
      skipped: '略過',
      stopped: '已停止',
      running: id === 'generate' ? `進行中 · 已引用 ${cited.length} 條` : '進行中',
      done: reported?.summary ?? '',
      insufficient: reported?.summary ?? '',
    }[status]

    const finished = status === 'done' || status === 'insufficient'
    return {
      id,
      label,
      status,
      detail,
      durationMs: finished ? (reported?.durationMs ?? null) : null,
    }
  })
}

export function formatDuration(ms: number | null): string {
  return ms === null ? '—' : `${(ms / 1000).toFixed(1)}s`
}
