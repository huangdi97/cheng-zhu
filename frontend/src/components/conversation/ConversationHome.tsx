import { ArrowRight, MessageSquareText, Plus, Clock3, CircleHelp, CheckCircle2, Play, Bell, BellOff } from 'lucide-react'
import { conversationApi } from '@/lib/conversationApi'
import { navigate, paths } from '@/lib/router'
import { EmptyState, ErrorState, Loading, Page, PageHeader, PrimaryButton, Section, SecondaryButton, StatusBadge, formatWhen, useAsync } from '@/components/os/ui'
import { useState } from 'react'

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
    } catch (e) { setStartError(e instanceof Error ? e.message : String(e)) }
    finally { setStarting(false) }
  }
  if (loading) return <Page testId="conversation-home"><Loading label="正在整理你的对话连续性…" /></Page>
  if (error || !data) return <Page testId="conversation-home"><ErrorState message={error ?? '无法加载对话首页'} onRetry={reload} /></Page>

  return (
    <Page testId="conversation-home">
      <PageHeader
        eyebrow="Personal Conversation Intelligence · Beta"
        title="对话"
        subtitle="不是会议纪要。把过去真正发生过的事带进下一场对话，并在值得开口时提醒你。"
        actions={<div className="flex flex-wrap gap-2">
          <SecondaryButton disabled={!reminderSupported} onClick={toggleReminders} icon={remindersEnabled ? <Bell className="h-3.5 w-3.5" /> : <BellOff className="h-3.5 w-3.5" />}>
            {reminderSupported ? (remindersEnabled ? '桌面提醒已开' : '开启桌面提醒') : '桌面提醒仅桌面端'}
          </SecondaryButton>
          <SecondaryButton disabled={starting} onClick={startAdhoc} icon={<Play className="h-3.5 w-3.5" />}>{starting ? '启动中…' : '开始临时会话'}</SecondaryButton>
          <PrimaryButton onClick={() => navigate(paths.conversationSpaces(undefined, { new: '1' }))} icon={<Plus className="h-3.5 w-3.5" />}>新建对话空间</PrimaryButton>
        </div>}
      />

      {startError ? <div className="mb-4"><ErrorState message={startError} /></div> : null}
      {data.state === 'EMPTY' ? (
        <EmptyState
          title="还没有对话空间"
          body="先从项目周会或设计评审开始。它会跨多场会话保留 Decision、Commitment 与 Open Question。"
          action={<PrimaryButton onClick={() => navigate(paths.conversationSpaces(undefined, { new: '1' }))}>创建第一个空间</PrimaryButton>}
        />
      ) : (
        <>
          <Section title="下一场">
            {reminderSupported ? <p className="mb-2 text-[11px] text-text-muted">{remindersEnabled ? '本地桌面提醒已开启：默认提前 10 分钟；系统通知不显示会话标题。' : '桌面提醒默认关闭；开启后只使用成竹内已排期 Session，不读取外部 Calendar。'}</p> : null}
            {data.next_session ? (
              <button type="button" onClick={() => navigate(paths.conversationSpace(data.next_session!.space_id, 'prepare'))}
                className="w-full text-left rounded-2xl border border-bg-tertiary bg-bg-secondary/40 p-4 hover:bg-bg-hover/40 transition-colors">
                <div className="flex items-center gap-2">
                  <Clock3 className="h-4 w-4 text-accent-blue" />
                  <span className="font-medium text-text-primary">{data.next_session.title}</span>
                  <StatusBadge tone="info">{data.next_session.assistance_mode}</StatusBadge>
                </div>
                <div className="mt-1 text-xs text-text-muted">{formatWhen(data.next_session.scheduled_at)} · 点击准备下一场</div>
              </button>
            ) : <p className="text-xs text-text-muted">没有已安排的下一场；可以从任一 Space 开始临时会话。</p>}
          </Section>

          <Section title="Next Focus">
            {data.next_focus ? (
              <button type="button" onClick={() => navigate(paths.conversationSpace(data.next_focus!.space_id, 'overview'))}
                className="group flex w-full items-center justify-between rounded-xl px-2 py-2 text-left hover:bg-bg-hover/50">
                <div>
                  <div className="text-sm font-medium text-text-primary">{data.next_focus.title}</div>
                  <div className="mt-0.5 text-[11px] text-text-muted">{data.next_focus.kind}</div>
                </div>
                <ArrowRight className="h-4 w-4 text-text-muted group-hover:text-text-primary" />
              </button>
            ) : <p className="text-xs text-text-muted">当前没有需要优先处理的开放事项。</p>}
          </Section>

          <div className="grid gap-4 md:grid-cols-2">
            <Section title="我欠的">
              {data.owed_by_me.length ? data.owed_by_me.map((item) => (
                <div key={item.id} className="flex items-start gap-2 py-1.5">
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-status-inferred" />
                  <div className="min-w-0">
                    <p className="text-xs text-text-primary">{item.title}</p>
                    <p className="text-[11px] text-text-muted">{item.due_at || '未设截止时间'} · {item.state}</p>
                  </div>
                </div>
              )) : <p className="text-xs text-text-muted">目前没有由你确认的未完成承诺。</p>}
            </Section>
            <Section title="等待 / 未解决">
              {data.open_questions.length ? data.open_questions.map((item) => (
                <div key={item.id} className="flex items-start gap-2 py-1.5">
                  <CircleHelp className="mt-0.5 h-3.5 w-3.5 text-accent-blue" />
                  <div>
                    <p className="text-xs text-text-primary">{item.title}</p>
                    <p className="text-[11px] text-text-muted">{item.review_status === 'AI_EXTRACTED' ? '待确认' : item.state}</p>
                  </div>
                </div>
              )) : <p className="text-xs text-text-muted">没有开放问题。</p>}
            </Section>
          </div>

          <Section title="最近变化" action={<SecondaryButton onClick={() => navigate(paths.conversationSpaces())}>查看全部空间</SecondaryButton>}>
            {data.recent_change ? (
              <div className="rounded-xl border border-bg-tertiary/70 px-3 py-2">
                <div className="flex items-center gap-2"><MessageSquareText className="h-4 w-4 text-accent-blue" /><span className="text-sm text-text-primary">{data.recent_change.title}</span></div>
                <p className="mt-1 text-[11px] text-text-muted">{data.recent_change.type} · {data.recent_change.state} · {data.recent_change.review_status}</p>
              </div>
            ) : <p className="text-xs text-text-muted">还没有确认过的 Decision / Commitment 变化。</p>}
          </Section>
        </>
      )}
    </Page>
  )
}
