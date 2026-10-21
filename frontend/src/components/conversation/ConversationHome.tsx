import { Bell, BellOff, Clock3, Play, Plus } from 'lucide-react'
import { useState } from 'react'
import { conversationApi } from '@/lib/conversationApi'
import { navigate, paths } from '@/lib/router'
import { EmptyState, ErrorState, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, formatWhen, useAsync } from '@/components/os/ui'

const MODE_LABEL: Record<string, string> = {
  QUIET: '安静',
  BALANCED: '平衡',
  ACTIVE: '主动',
  PRESENTATION: '演示',
  ONE_ON_ONE: '1:1',
}

export default function ConversationHome() {
  const { data, error, loading, reload } = useAsync(() => conversationApi.home(), [])
  const [starting, setStarting] = useState(false)
  const [startError, setStartError] = useState('')
  const reminderSupported = Boolean(window.electronAPI?.syncConversationReminders)
  const [remindersEnabled, setRemindersEnabled] = useState(() => {
    try { return window.localStorage.getItem('chengzhu-conversation-reminders') === '1' }
    catch { return false }
  })

  const toggleReminders = () => {
    if (!reminderSupported) return
    const next = !remindersEnabled
    setRemindersEnabled(next)
    try { window.localStorage.setItem('chengzhu-conversation-reminders', next ? '1' : '0') } catch { /* storage unavailable */ }
    window.dispatchEvent(new Event('chengzhu-conversation-reminders-changed'))
  }

  const startAdhoc = async () => {
    setStarting(true); setStartError('')
    try {
      const result = await conversationApi.adhoc({ title: '临时对话', profile: 'PROJECT_SYNC', assistance_mode: 'BALANCED' })
      navigate(paths.conversationLive(result.session.id))
    } catch (e) {
      setStartError(e instanceof Error ? e.message : String(e))
    } finally {
      setStarting(false)
    }
  }

  if (loading) return <Page testId="conversation-home"><Loading label="正在整理你的对话连续性…" /></Page>
  if (error || !data) return <Page testId="conversation-home"><ErrorState message={error ?? '无法加载对话首页'} onRetry={reload} /></Page>

  const needsAttention = [
    ...data.owed_by_me.map((item) => ({
      key: `owed:${item.id}`,
      label: '我的承诺',
      title: item.title,
      meta: item.due_at || '未设截止时间',
    })),
    ...data.open_questions.map((item) => ({
      key: `question:${item.id}`,
      label: item.review_status === 'AI_EXTRACTED' ? '待确认问题' : '开放问题',
      title: item.title,
      meta: item.review_status === 'AI_EXTRACTED' ? '需要你确认后才进入长期事实' : item.state,
    })),
  ]

  return (
    <Page testId="conversation-home">
      <PageHeader
        eyebrow="Personal Conversation Intelligence"
        title="对话"
        subtitle="把上一场留下的事实、承诺和决策带进下一场；不是把每次谈话都做成一份会议纪要。"
        actions={<div className="flex flex-wrap gap-2">
          <SecondaryButton disabled={!reminderSupported} onClick={toggleReminders} icon={remindersEnabled ? <Bell className="h-3.5 w-3.5" /> : <BellOff className="h-3.5 w-3.5" />}>
            {reminderSupported ? (remindersEnabled ? '提醒已开' : '开启提醒') : '提醒仅桌面端'}
          </SecondaryButton>
          <SecondaryButton disabled={starting} onClick={startAdhoc} icon={<Play className="h-3.5 w-3.5" />}>
            {starting ? '启动中…' : '开始临时会话'}
          </SecondaryButton>
          <PrimaryButton onClick={() => navigate(paths.conversationSpaces(undefined, { new: '1' }))} icon={<Plus className="h-3.5 w-3.5" />}>
            新建对话空间
          </PrimaryButton>
        </div>}
      />

      {startError ? <div className="mb-4"><ErrorState message={startError} /></div> : null}

      {data.state === 'EMPTY' ? (
        <EmptyState
          title="还没有持续对话"
          body="先从一个会反复发生的项目同步、1:1 或设计评审开始；成竹只保留跨场真正需要延续的事实。"
          action={<PrimaryButton onClick={() => navigate(paths.conversationSpaces(undefined, { new: '1' }))}>创建第一个空间</PrimaryButton>}
        />
      ) : (
        <div className="space-y-6">
          <section aria-labelledby="conversation-next-heading" className="border-y border-bg-tertiary/70 py-4">
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
              <div>
                <p className="text-[10px] font-semibold tracking-[0.14em] text-text-muted">NEXT CONVERSATION</p>
                <h2 id="conversation-next-heading" className="mt-1 text-base font-semibold text-text-primary">下一场</h2>
                {data.next_session ? (
                  <button type="button" onClick={() => navigate(paths.conversationSpace(data.next_session!.space_id, 'prepare'))}
                    className="mt-3 flex w-full items-start gap-3 text-left group">
                    <Clock3 className="mt-0.5 h-4 w-4 flex-shrink-0 text-accent-blue" aria-hidden />
                    <span className="min-w-0">
                      <span className="block text-lg font-semibold text-text-primary group-hover:underline group-hover:underline-offset-4">{data.next_session.title}</span>
                      <span className="mt-1 block text-xs text-text-secondary">{formatWhen(data.next_session.scheduled_at)} · 进入准备</span>
                      <span className="mt-1 block text-[11px] text-text-muted">帮助方式：{MODE_LABEL[data.next_session.assistance_mode] ?? data.next_session.assistance_mode}</span>
                    </span>
                  </button>
                ) : (
                  <p className="mt-3 text-sm text-text-secondary">还没有已安排的下一场。可以从任一空间开始临时会话。</p>
                )}
              </div>

              <div className="lg:border-l lg:border-bg-tertiary/70 lg:pl-6">
                <p className="text-[10px] font-semibold tracking-[0.14em] text-text-muted">NEXT FOCUS</p>
                {data.next_focus ? (
                  <button type="button" onClick={() => navigate(paths.conversationSpace(data.next_focus!.space_id, 'overview'))} className="mt-2 text-left">
                    <span className="block text-sm font-semibold text-text-primary">{data.next_focus.title}</span>
                    <span className="mt-1 block text-[11px] text-text-muted">{data.next_focus.kind}</span>
                  </button>
                ) : (
                  <p className="mt-2 text-xs text-text-muted">当前没有需要优先处理的开放事项。</p>
                )}
              </div>
            </div>
            {reminderSupported ? (
              <p className="mt-3 text-[10px] text-text-muted">
                {remindersEnabled ? '本地提醒默认提前 10 分钟；系统通知不显示会话标题。' : '提醒默认关闭；开启后只使用成竹内已排期的 Session。'}
              </p>
            ) : null}
          </section>

          <section aria-labelledby="conversation-attention-heading">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h2 id="conversation-attention-heading" className="text-sm font-semibold text-text-primary">需要你处理</h2>
                <p className="mt-0.5 text-[11px] text-text-muted">这里只放会影响后续对话的承诺和未解决问题。</p>
              </div>
              <span className="text-[11px] tabular-nums text-text-muted">{needsAttention.length} 项</span>
            </div>

            {needsAttention.length ? (
              <ul className="mt-3 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
                {needsAttention.slice(0, 6).map((item) => (
                  <li key={item.key} className="grid gap-1 py-2.5 sm:grid-cols-[92px_minmax(0,1fr)_auto] sm:items-center sm:gap-3">
                    <span className="text-[10px] text-text-muted">{item.label}</span>
                    <span className="text-xs font-medium text-text-primary">{item.title}</span>
                    <span className="text-[10px] text-text-muted">{item.meta}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 border-y border-bg-tertiary/70 py-4 text-xs text-text-muted">现在没有待处理承诺或开放问题。</p>
            )}
          </section>

          <section aria-labelledby="conversation-change-heading" className="grid gap-5 border-t border-bg-tertiary/70 pt-4 md:grid-cols-[1fr_auto] md:items-start">
            <div>
              <h2 id="conversation-change-heading" className="text-sm font-semibold text-text-primary">最近真正改变了什么</h2>
              {data.recent_change ? (
                <div className="mt-2">
                  <p className="text-sm text-text-primary">{data.recent_change.title}</p>
                  <p className="mt-0.5 text-[11px] text-text-muted">
                    {data.recent_change.type} · {data.recent_change.state} · {data.recent_change.review_status === 'AI_EXTRACTED' ? '待确认' : '已进入长期记录'}
                  </p>
                </div>
              ) : (
                <p className="mt-2 text-xs text-text-muted">还没有确认过的 Decision / Commitment 变化。</p>
              )}
            </div>
            <SecondaryButton onClick={() => navigate(paths.conversationSpaces())}>查看全部空间</SecondaryButton>
          </section>
        </div>
      )}
    </Page>
  )
}
