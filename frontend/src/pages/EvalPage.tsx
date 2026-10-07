import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { PageShell } from '../components/PageShell'
import { EvalTable } from '../features/eval/EvalTable'
import { formatEvalDate, percent } from '../features/eval/labels'
import { MetricCard } from '../features/eval/MetricCard'
import { fetchEval } from '../lib/api'
import { useMeta } from '../lib/useMeta'
import styles from './EvalPage.module.css'

/** `/eval`：這個系統答得有多準？數字來自 /api/eval/latest（run_generation_eval --publish 的結果）。 */
export function EvalPage() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['eval'],
    queryFn: fetchEval,
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  })
  const { data: meta } = useMeta()
  const shortNames = useMemo(
    () => Object.fromEntries((meta?.laws ?? []).map((law) => [law.pcode, law.law_short_name])),
    [meta],
  )

  return (
    <PageShell>
      <div className={styles.root}>
        <section className={styles.intro}>
          <p className={styles.kicker}>品質報告</p>
          <h1 className={styles.title}>這個系統答得有多準？</h1>
          <p className={styles.lede}>
            我們準備了一組人工確認過標準答案的題目，逐題檢查系統有沒有找到正確條文、引用對不對、數字有沒有照抄條文，以及該拒答時有沒有拒答。
          </p>
          {data && (
            <div className={styles.facts}>
              <span>評估日期 {formatEvalDate(data.evaluated_at)}</span>
              <span>資料版本 {data.data_version}</span>
              <span>
                題數 {data.counts.verified} 題（範圍外 {data.counts.out_of_scope} 題）
              </span>
            </div>
          )}
        </section>

        {isPending && <p role="status">評估結果載入中…</p>}
        {isError && (
          <p role="alert" className={styles.error}>
            目前沒有可顯示的評估結果。
          </p>
        )}

        {data && (
          <>
            <section aria-label="指標" className={styles.metrics}>
              <MetricCard
                name="檢索命中率"
                code="Recall@5"
                value={percent(data.metrics.recall_at_5)}
                description="正確條文出現在前 5 筆檢索結果的比例。"
              />
              <MetricCard
                name="排序品質"
                code="MRR"
                value={data.metrics.mrr.toFixed(2)}
                description="正確條文排得越前面，分數越接近 1。"
              />
              <MetricCard
                name="引用正確率"
                code="Citation"
                value={percent(data.metrics.citation_accuracy)}
                description="答案引用的條文，包含標準答案條文的比例。"
              />
              <MetricCard
                name="數字正確率"
                code="Numbers"
                value={
                  data.metrics.number_accuracy === null
                    ? '—'
                    : percent(data.metrics.number_accuracy)
                }
                description="答案中的金額、點數、期限與條文原文一致的比例。"
              />
              <MetricCard
                name="拒答正確率"
                code="Refusal"
                value={percent(data.metrics.refusal_accuracy)}
                description="範圍外問題確實拒答、範圍內問題沒有誤拒的比例。"
              />
            </section>
            <EvalTable rows={data.questions} shortNames={shortNames} />
          </>
        )}
      </div>
    </PageShell>
  )
}
