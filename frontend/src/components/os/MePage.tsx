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
  return (
    <div className="px-4 pt-4">
      <div className="flex flex-wrap gap-1.5" aria-label="Story 能力分类">
        {data.categories.map((c) => <StatusBadge key={c.key} tone={c.story_ids.length ? 'ok' : 'muted'}>{c.label}{c.story_ids.length ? ` · ${c.story_ids.length}` : ''}</StatusBadge>)}
      </div>
      {data.missing.length ? (
        <p className="mt-2 text-xs text-text-secondary">你还没有「{data.missing[0].label}」故事。在下面的 Story Builder 里用 5 分钟写下一个真实经历，标题里带上分类即可。</p>
      ) : null}
    </div>
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
