import { Fragment, useState } from 'react'
import { MOBILE_QUERY, useMediaQuery } from '../../lib/useMediaQuery'
import type { EvalRow } from '../../types/eval'
import styles from './EvalTable.module.css'
import {
  articleLabel,
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  type Cell,
  citationCell,
  numbersCell,
  retrievalCell,
} from './labels'

type Props = {
  rows: EvalRow[]
  /** pcode → 法規簡稱（來自 /api/meta），用來把條 id 顯示成「道交處罰條例 §53」 */
  shortNames: Record<string, string>
}

function CellView({ cell, label }: { cell: Cell; label?: string }) {
  return (
    <span className={`${styles.cell} ${styles[cell.tone]}`}>
      {label && <span className={styles.cellLabel}>{label}</span>}
      <span aria-hidden="true">{cell.symbol}</span> {cell.text}
    </span>
  )
}

function Detail({ row, shortNames }: { row: EvalRow; shortNames: Props['shortNames'] }) {
  const expected = row.expected.map((id) => articleLabel(id, shortNames)).join('、')
  return (
    <div className={styles.detail}>
      <div>
        <p className={styles.detailTitle}>標準答案</p>
        <p className={styles.detailText}>
          {row.should_refuse ? '範圍外：應該拒答' : expected}
          {row.fact_amounts_expected
            ? ` · 重點金額 ${row.fact_amounts_found ?? 0} / ${row.fact_amounts_expected}`
            : ''}
        </p>
      </div>
      <div>
        <p className={styles.detailTitle}>系統檢索前 5 筆</p>
        <p className={`${styles.detailText} ${styles.mono}`}>
          {row.retrieved.length > 0
            ? row.retrieved
                .map(
                  (r) =>
                    `${articleLabel(r.article_id, shortNames)}${r.score === null ? '' : ` (${r.score.toFixed(2)})`}`,
                )
                .join(' · ')
            : '（這次評估沒有記錄檢索結果）'}
        </p>
      </div>
    </div>
  )
}

/** 逐題結果：可依類別篩選，每列可展開看標準答案與系統檢索前 5 筆。 */
export function EvalTable({ rows, shortNames }: Props) {
  const isMobile = useMediaQuery(MOBILE_QUERY)
  const [category, setCategory] = useState<string>('all')
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set())

  const categories = CATEGORY_ORDER.filter((c) => rows.some((r) => r.category === c))
  const shown = category === 'all' ? rows : rows.filter((r) => r.category === category)

  function toggle(id: string) {
    setOpen((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <section aria-labelledby="eval-table" className={styles.root}>
      <div className={styles.head}>
        <h2 id="eval-table" className={styles.title}>
          逐題結果
        </h2>
        <span className={styles.count}>
          {shown.length} / {rows.length} 題
        </span>
        <fieldset className={styles.filters}>
          <legend className="visually-hidden">依類別篩選</legend>
          {['all', ...categories].map((c) => (
            <button
              key={c}
              type="button"
              aria-pressed={category === c}
              className={`${styles.chip} ${category === c ? styles.chipOn : ''}`}
              onClick={() => setCategory(c)}
            >
              {c === 'all' ? '全部' : (CATEGORY_LABELS[c] ?? c)}
            </button>
          ))}
        </fieldset>
      </div>

      {isMobile ? (
        <ul className={styles.cards}>
          {shown.map((row) => (
            <li key={row.id} className={styles.card}>
              <button
                type="button"
                className={styles.cardButton}
                aria-expanded={open.has(row.id)}
                onClick={() => toggle(row.id)}
              >
                <span className={styles.id}>{row.id}</span>
                <span className={styles.question}>{row.question}</span>
                <span className={styles.category}>
                  {CATEGORY_LABELS[row.category] ?? row.category}
                </span>
              </button>
              <div className={styles.cardCells}>
                <CellView label="檢索" cell={retrievalCell(row.retrieval, row.first_hit_rank)} />
                <CellView label="引用" cell={citationCell(row.citation)} />
                <CellView label="數字" cell={numbersCell(row.numbers)} />
              </div>
              {open.has(row.id) && <Detail row={row} shortNames={shortNames} />}
            </li>
          ))}
        </ul>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col" className={styles.idCol}>
                #
              </th>
              <th scope="col">問題</th>
              <th scope="col" className={styles.col}>
                類別
              </th>
              <th scope="col" className={styles.col}>
                檢索
              </th>
              <th scope="col" className={styles.col}>
                引用
              </th>
              <th scope="col" className={styles.col}>
                數字
              </th>
              <th scope="col" className={styles.toggleCol}>
                <span className="visually-hidden">展開</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => {
              const expanded = open.has(row.id)
              return (
                <Fragment key={row.id}>
                  <tr className={expanded ? styles.expanded : ''}>
                    <td className={`${styles.id} ${styles.idCol}`}>{row.id}</td>
                    <td className={styles.question}>{row.question}</td>
                    <td className={styles.category}>
                      {CATEGORY_LABELS[row.category] ?? row.category}
                    </td>
                    <td>
                      <CellView cell={retrievalCell(row.retrieval, row.first_hit_rank)} />
                    </td>
                    <td>
                      <CellView cell={citationCell(row.citation)} />
                    </td>
                    <td>
                      <CellView cell={numbersCell(row.numbers)} />
                    </td>
                    <td>
                      <button
                        type="button"
                        className={styles.toggle}
                        aria-expanded={expanded}
                        aria-label={`${expanded ? '收合' : '展開'} ${row.id}`}
                        onClick={() => toggle(row.id)}
                      >
                        {expanded ? '−' : '+'}
                      </button>
                    </td>
                  </tr>
                  {expanded && (
                    <tr className={styles.expanded}>
                      <td />
                      <td colSpan={6}>
                        <Detail row={row} shortNames={shortNames} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      )}

      <p className={styles.legend}>
        符號說明：<span className={styles.ok}>✓</span> 正確／一致　
        <span className={styles.warn}>△</span> 部分命中　<span className={styles.err}>⨯</span>{' '}
        錯誤　<span className={styles.na}>—</span>{' '}
        不適用（例如範圍外問題沒有檢索標準答案、拒答時沒有數字可比對）
      </p>
    </section>
  )
}
