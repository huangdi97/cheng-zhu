import { lazy, Suspense, useEffect, useState } from 'react'
import { BookOpenCheck, Sparkles } from 'lucide-react'
import { api, type PrepSpaceLite } from '@/lib/api'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'
import CoachPanel from '@/components/coach/CoachPanel'
import PinnedMoments from '@/components/v13/PinnedMoments'

// v1.3 compatibility hubs: Goal-centered primary IA lives in App. These hubs keep
// existing Practice/History components reusable without duplicating domain state.

const PrepSpace = lazy(() => import('@/components/PrepSpace'))
const JobTracker = lazy(() => import('@/components/JobTracker'))
const PracticePanel = lazy(() => import('@/components/PracticePanel'))
const ReviewMode = lazy(() => import('@/components/ReviewMode'))
const KnowledgeMap = lazy(() => import('@/components/KnowledgeMap'))

function Loading({ label }: { label: string }) {
  return <div className="flex-1 flex items-center justify-center text-sm text-text-muted">{label}</div>
}

function SubTabs<T extends string>({ label, tabs, value, onChange }: { label: string; tabs: Array<[T, string]>; value: T; onChange: (v: T) => void }) {
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 px-3 md:px-5 py-2 border-b border-bg-tertiary/70 bg-bg-secondary/40 flex-shrink-0">
      {tabs.map(([key, text]) => (
        <button key={key} type="button" role="tab" aria-selected={value === key} onClick={() => onChange(key)}
          className={`rounded-full px-3 py-1.5 text-xs font-medium ${value === key ? 'bg-container-primary text-container-on-primary' : 'text-text-muted hover:text-text-primary'}`}>
          {text}
        </button>
      ))}
    </div>
  )
}

/** 求职：Job Goal（概览 / JD·Alignment / 准备 / Interview Pack）+ 投递看板（Interviews / Offer）。 */
export function JobHub() {
  const jobHubTab = useUiPrefsStore((s) => s.jobHubTab)
  const setJobHubTab = useUiPrefsStore((s) => s.setJobHubTab)
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <SubTabs label="求职" value={jobHubTab} onChange={setJobHubTab} tabs={[['goals', '岗位目标'], ['board', '投递看板']]} />
      <Suspense fallback={<Loading label="加载中…" />}>
        {jobHubTab === 'goals' ? <PrepSpace /> : <JobTracker />}
      </Suspense>
    </div>
  )
}

/** 演练：选择一个岗位目标，进入基于 Gap / Attack Surface 的模拟面试。 */
export function RehearseHub() {
  const [spaces, setSpaces] = useState<PrepSpaceLite[] | null>(null)
  const activeGoalId = useUiPrefsStore((s) => s.activeGoalId)
  const [active, setActive] = useState<number | null>(activeGoalId)
  const setActiveGoalId = useUiPrefsStore((s) => s.setActiveGoalId)
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)
  const setJobHubTab = useUiPrefsStore((s) => s.setJobHubTab)
  useEffect(() => {
    api.prepListSpaces().then((res) => {
      const items = res.items ?? []
      setSpaces(items)
      if (activeGoalId && items.some((space) => space.id === activeGoalId)) setActive(activeGoalId)
    }).catch(() => setSpaces([]))
  }, [activeGoalId])

  if (active != null) {
    return (
      <div className="flex-1 min-h-0 overflow-y-auto p-4">
        <Suspense fallback={<Loading label="加载模拟面试中…" />}>
          <PracticePanel spaceId={active} onClose={() => setActive(null)} />
        </Suspense>
      </div>
    )
  }
  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6" data-testid="rehearse-hub">
      <div className="flex items-center gap-2">
        <BookOpenCheck className="h-5 w-5 text-accent-blue" aria-hidden />
        <h2 className="text-lg font-semibold text-text-primary">练习</h2>
      </div>
      <p className="mt-1 text-xs text-text-muted">按岗位目标出题，并根据你的薄弱点追问。回答前不显示标准答案；结束后自动生成复盘。</p>
      {spaces === null && <p className="mt-4 text-sm text-text-muted">加载中…</p>}
      {spaces !== null && spaces.length === 0 && (
        <div className="mt-6 rounded-2xl border border-dashed border-bg-hover p-6 text-sm text-text-muted">
          还没有岗位目标。
          <button type="button" className="ml-2 text-accent-blue underline" onClick={() => { setJobHubTab('goals'); setAppMode('goals') }}>去「求职目标」新建</button>
        </div>
      )}
      <div className="mt-4 max-w-2xl"><CoachPanel sessionKind="practice" /></div>
      <ul className="mt-4 grid gap-3 md:grid-cols-2">
        {(spaces ?? []).map((space) => (
          <li key={space.id} className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-4">
            <div className="text-sm font-semibold text-text-primary">{space.title}</div>
            <div className="text-[11px] text-text-muted">{[space.company, space.role].filter(Boolean).join(' · ')}</div>
            <button type="button" onClick={() => { setActiveGoalId(space.id); setActive(space.id) }}
              className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-accent-green/15 border border-accent-green/30 px-3 py-1.5 text-xs font-medium text-status-direct">
              <Sparkles className="h-3.5 w-3.5" aria-hidden /> 开始 Practice
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** 复盘：场次复盘 + 能力分析。 */
export function ReviewHub() {
  const reviewHubTab = useUiPrefsStore((s) => s.reviewHubTab)
  const setReviewHubTab = useUiPrefsStore((s) => s.setReviewHubTab)
  return (
    <div className="flex-1 flex flex-col min-h-0">
      <SubTabs label="历史" value={reviewHubTab} onChange={setReviewHubTab} tabs={[['sessions', 'Sessions / Reflection'], ['ability', '能力趋势']]} />
      {reviewHubTab === 'sessions' && <PinnedMoments />}
      <Suspense fallback={<Loading label="加载中…" />}>
        {reviewHubTab === 'sessions' ? <ReviewMode /> : <KnowledgeMap />}
      </Suspense>
    </div>
  )
}
