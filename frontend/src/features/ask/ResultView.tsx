import { useEffect, useMemo, useRef, useState } from 'react'
import { SpinnerIcon, StopIcon } from '../../components/icons'
import { PageShell } from '../../components/PageShell'
import { MOBILE_QUERY, useMediaQuery } from '../../lib/useMediaQuery'
import { useMeta } from '../../lib/useMeta'
import { ProcessSection } from '../pipeline/ProcessSection'
import { WhyRefused } from '../pipeline/WhyRefused'
import { ArticleDrawer } from '../sources/ArticleDrawer'
import { ArticlePanel } from '../sources/ArticlePanel'
import { AnswerSection } from './AnswerSection'
import { articleIdOf, groupArticles, sortForDone } from './articles'
import type { AskState } from './askReducer'
import { EvidenceList } from './EvidenceList'
import { RefusalNotice } from './RefusalNotice'
import styles from './ResultView.module.css'
import { ScopeAside } from './ScopeAside'

type Props = {
  state: AskState
  onAsk: (question: string) => void
  onStop: () => void
  onReset: () => void
}

const STATUS_TEXT: Record<AskState['phase'], string> = {
  idle: '',
  streaming: '正在產生答案',
  done: '答案已完成',
  refused: '查無依據，因此不作答',
  stopped: '已停止產生，答案不完整',
  error: '發生錯誤',
}

type Tab = 'answer' | 'process'

/**
 * 問答結果頁。左欄固定順序：你的問題 → 檢索過程 → 答案；右欄是依據（5.5-A）。
 * 手機（< 768px）改成兩個分頁：答案｜過程與依據（5.5-E）。
 * `activeArticleId` 全頁唯一，答案的引用標記、依據卡片、全文面板（抽屜）都讀它（5.5-C）。
 */
export function ResultView({ state, onAsk, onStop, onReset }: Props) {
  const { phase, question, results, cited, refusal, validation } = state
  const { data: meta } = useMeta()
  const isMobile = useMediaQuery(MOBILE_QUERY)
  const titleRef = useRef<HTMLHeadingElement>(null)
  const openerRef = useRef<HTMLElement | null>(null)

  const [activeId, setActiveId] = useState<string | null>(null)
  const [hoverId, setHoverId] = useState<string | null>(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const [tab, setTab] = useState<Tab>('answer')

  // 從首頁切到結果頁：被卸載的輸入框／範例按鈕原本有焦點，把焦點與捲動位置帶到「你的問題」
  useEffect(() => {
    window.scrollTo(0, 0)
    titleRef.current?.focus()
  }, [])

  const done = phase === 'done'
  const streaming = phase === 'streaming'
  const refused = phase === 'refused' && refusal !== null
  const interactive = done

  // 檢索結果以條為單位、依檢索名次排列（檢索過程用）；完成時依據欄把已引用的排到前面
  const ranked = useMemo(() => groupArticles(results), [results])
  const evidence = useMemo(
    () => (done ? sortForDone(ranked, cited) : ranked),
    [ranked, cited, done],
  )

  const invalidIds = useMemo(
    () => new Set((validation?.invalid ?? []).map(articleIdOf)),
    [validation],
  )

  // 重新產生或重新提問後，互動狀態一律重來
  useEffect(() => {
    if (!done) {
      setActiveId(null)
      setHoverId(null)
      setPanelOpen(false)
    }
  }, [done])

  // 回答完成時，預設 active 為答案中的第一個（有對應條文的）引用；全文面板預設關閉（5.5-G1）
  const firstCited = cited.find((id) => evidence.some((e) => e.articleId === id)) ?? null
  const effectiveActive = done ? (activeId ?? firstCited) : null
  const activeArticle = evidence.find((e) => e.articleId === effectiveActive) ?? null

  function openPanel() {
    if (!panelOpen) openerRef.current = document.activeElement as HTMLElement | null
    setPanelOpen(true)
  }

  function closePanel() {
    setPanelOpen(false)
    openerRef.current?.focus()
    openerRef.current = null
  }

  /** 點引用標記：設為 active，不開啟面板（手機沒有常駐面板，所以直接開抽屜）。 */
  function selectCitation(articleId: string) {
    setActiveId(articleId)
    if (isMobile) {
      openPanel()
    } else {
      document.getElementById(`card-${articleId}`)?.scrollIntoView({ block: 'nearest' })
    }
  }

  /** 點卡片標題或「查看全文」：設為 active 並開啟全文。 */
  function openArticle(articleId: string) {
    setActiveId(articleId)
    openPanel()
  }

  // Esc 關閉全文面板與抽屜（5.5-G5）
  useEffect(() => {
    if (!panelOpen) return
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') closePanel()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  })

  // 桌面面板開啟時，頁面底部留出面板高度，答案與依據才能捲到最底
  useEffect(() => {
    if (!panelOpen || isMobile) return
    document.body.style.paddingBottom = 'var(--panel-height)'
    return () => {
      document.body.style.paddingBottom = ''
    }
  }, [panelOpen, isMobile])

  const citationSelection = {
    interactive,
    activeId: effectiveActive,
    hoverId,
    invalidIds,
    onSelect: selectCitation,
    onHover: setHoverId,
  }
  const evidenceSelection = {
    interactive,
    activeId: effectiveActive,
    hoverId,
    onOpen: openArticle,
    onHover: setHoverId,
  }

  const questionBlock = (
    <section aria-label="你的問題" className={styles.question}>
      <p className={styles.kicker}>你的問題</p>
      <h1 ref={titleRef} tabIndex={-1} className={styles.title}>
        {question}
      </h1>
      {streaming && (
        <div className={styles.status}>
          <span className={styles.working} role="status">
            <SpinnerIcon size={16} className={styles.spinner} />
            正在產生答案…
          </span>
          <button type="button" className={styles.stop} onClick={onStop}>
            <StopIcon />
            停止
          </button>
        </div>
      )}
    </section>
  )

  const statusLine = !streaming && (
    // 只播報階段變化一次；逐字出現的答案本身不設 aria-live，避免每個 delta 都被念出來
    <p className="visually-hidden" role="status">
      {STATUS_TEXT[phase]}
    </p>
  )

  const answer = (
    <AnswerSection
      state={state}
      evidence={evidence}
      selection={citationSelection}
      dataVersion={meta?.data_version}
      onAsk={onAsk}
      onReset={onReset}
    />
  )
  const process = phase !== 'error' && <ProcessSection state={state} articles={ranked} />
  const evidenceList = phase !== 'error' && (
    <EvidenceList
      evidence={evidence}
      cited={cited}
      loading={streaming}
      selection={evidenceSelection}
      compact={isMobile}
      panelOpen={panelOpen}
    />
  )

  const drawerIndex = evidence.findIndex((e) => e.articleId === effectiveActive)

  const dialogs =
    panelOpen && activeArticle ? (
      isMobile ? (
        <ArticleDrawer
          articles={evidence}
          index={drawerIndex}
          cited={cited.includes(activeArticle.articleId)}
          onClose={closePanel}
          onNavigate={setActiveId}
        />
      ) : (
        <ArticlePanel
          article={activeArticle}
          cited={cited.includes(activeArticle.articleId)}
          onClose={closePanel}
        />
      )
    ) : null

  if (refused) {
    return (
      <PageShell>
        <div className={styles.grid}>
          <div className={styles.main}>
            {questionBlock}
            {statusLine}
            <RefusalNotice onAsk={onAsk} onNewQuestion={onReset} />
            <WhyRefused state={state} />
          </div>
          <ScopeAside />
        </div>
      </PageShell>
    )
  }

  // 手機：串流中停在「答案」分頁，檢索過程在「過程與依據」分頁更新（5.5-G3）
  if (isMobile && phase !== 'error') {
    return (
      <PageShell>
        <div className={styles.mobile}>
          <div role="tablist" aria-label="結果內容" className={styles.tabs}>
            {(['answer', 'process'] as const).map((id) => (
              <button
                key={id}
                id={`tab-${id}`}
                type="button"
                role="tab"
                aria-selected={tab === id}
                aria-controls={`tabpanel-${id}`}
                className={`${styles.tab} ${tab === id ? styles.tabActive : ''}`}
                onClick={() => setTab(id)}
              >
                {id === 'answer' ? '答案' : '過程與依據'}
              </button>
            ))}
          </div>
          {statusLine}
          <div
            id={`tabpanel-${tab}`}
            role="tabpanel"
            aria-labelledby={`tab-${tab}`}
            className={styles.main}
          >
            {tab === 'answer' ? (
              <>
                {questionBlock}
                {answer}
              </>
            ) : (
              <>
                {process}
                {evidenceList}
              </>
            )}
          </div>
        </div>
        {dialogs}
      </PageShell>
    )
  }

  return (
    <PageShell>
      <div className={styles.grid}>
        <div className={styles.main}>
          {questionBlock}
          {statusLine}
          {process}
          {answer}
        </div>
        {evidenceList}
      </div>
      {dialogs}
    </PageShell>
  )
}
