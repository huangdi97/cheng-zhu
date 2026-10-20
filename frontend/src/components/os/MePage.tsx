/** 我的成竹 (canonical §6): 概览 · 简历 · 项目 · 待确认 · Stories · Skills · 我的表达. */
import { lazy, Suspense, useState } from 'react'
import { navigate, paths } from '@/lib/router'
import { productApi } from '@/lib/productApi'
import { Overview, Projects, Skills, Stories, Voice, type TabKey } from '@/components/my/MyChengzhu'
import FactsSources from '@/components/my/FactsSources'
import FactInboxView from './FactInboxView'
import { Loading, Page, PageHeader, StatusBadge, Tabs, useAsync } from './ui'

const ResumeOptimizer = lazy(() => import('@/components/ResumeOptimizer'))

type MeTab = 'overview' | 'resume' | 'projects' | 'inbox' | 'stories' | 'skills' | 'voice'
const ME_TABS: MeTab[] = ['overview', 'resume', 'projects', 'inbox', 'stories', 'skills', 'voice']

function StoriesCoverage() {
  const { data } = useAsync(() => productApi.storyCoverage(), [])
  if (!data) return null
  const covered = data.categories.filter((c) => c.story_ids.length).length
  const total = data.categories.length
  const nextGap = data.missing[0] ?? null
  return (
    <section aria-label="Story 覆盖" className="mx-4 mt-4 grid gap-3 border-y border-bg-tertiary/70 py-3 sm:grid-cols-[auto_1fr] sm:items-center">
      <div className="min-w-[110px]">
        <p className="text-lg font-semibold tabular-nums text-text-primary">{covered} / {total}</p>
        <p className="text-[10px] text-text-muted">已覆盖能力情境</p>
      </div>
      <div>
        {nextGap ? (
          <>
            <p className="text-xs font-medium text-text-primary">下一块最值得补：{nextGap.label}</p>
            <p className="mt-0.5 text-[11px] leading-4 text-text-muted">不用为了“凑分类”编故事；只从真实经历里补一个能经得住追问的例子。</p>
          </>
        ) : (
          <>
            <p className="text-xs font-medium text-text-primary">常见能力情境已有覆盖</p>
            <p className="mt-0.5 text-[11px] text-text-muted">继续优先补证据、结果和失败后的反思，而不是继续堆数量。</p>
          </>
        )}
      </div>
    </section>
  )
}

export default function MePage({ tab }: { tab: string }) {
  const current = (ME_TABS as string[]).includes(tab) ? (tab as MeTab) : 'overview'
  const [showAllFacts, setShowAllFacts] = useState(false)
  const inbox = useAsync(() => productApi.factInbox(), [])
  const go = (t: MeTab) => navigate(paths.me(t), { replace: true })
  const jump = (t: TabKey) => go(t === 'facts' ? 'inbox' : (t as MeTab))
  return (
    <Page testId="me-page" wide>
      <PageHeader title="我的成竹" subtitle="你的简历、项目、事实、故事和表达习惯。个人经历受事实与来源约束；通用知识、设计和假设问题不会被误当成你的经历。" />
      <Tabs<MeTab> label="我的成竹" value={current} onChange={go}
        tabs={[['overview', '概览'], ['resume', '简历'], ['projects', '项目'], ['inbox', '待确认', inbox.data?.count ?? 0], ['stories', 'Stories'], ['skills', 'Skills'], ['voice', '我的表达']]} />
      <div className="pt-2">
        {current === 'overview' ? <Overview onJump={jump} /> : null}
        {current === 'resume' ? <Suspense fallback={<Loading />}><div className="flex flex-col min-h-[480px]"><ResumeOptimizer /></div></Suspense> : null}
        {current === 'projects' ? <Projects /> : null}
        {current === 'inbox' ? (
          <div className="p-1">
            {showAllFacts ? <><button type="button" className="mb-2 text-xs text-accent-blue underline" onClick={() => setShowAllFacts(false)}>返回待确认</button><FactsSources /></>
              : <FactInboxView onShowAll={() => setShowAllFacts(true)} />}
          </div>
        ) : null}
        {current === 'stories' ? <><StoriesCoverage /><Stories /></> : null}
        {current === 'skills' ? <Skills /> : null}
        {current === 'voice' ? <Voice /> : null}
      </div>
    </Page>
  )
}
