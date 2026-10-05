/**
 * Fact Inbox (canonical §6): "需要你确认 · N". Each card shows what the
 * material actually supports and resolves through the v1.2 provenance axes.
 * Burden guard: when the server switches to HIGH_ONLY, lower-risk items are
 * grouped into one batch card instead of more notifications.
 */
import { useEffect, useState } from 'react'
import { productApi, type FactInboxCard } from '@/lib/productApi'
import { navigate, paths } from '@/lib/router'
import { useOsStore } from '@/stores/osStore'
import { ActionMenu, EmptyState, ErrorState, inputCls, Loading, PrimaryButton, SecondaryButton, StatusBadge, useAsync } from './ui'

const RISK: Record<string, ['risk' | 'warn' | 'muted', string]> = {
  HIGH: ['risk', '高风险'],
  MEDIUM: ['warn', '需确认'],
  LOW: ['muted', '低风险'],
}

export default function FactInboxView({ onShowAll }: { onShowAll?: () => void }) {
  const { data, error, loading, reload } = useAsync(() => productApi.factInbox(true), [])
  const contextGoal = useOsStore((s) => s.contextGoalId)
  const goals = useAsync(() => productApi.goals('ACTIVE'), [])
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null)
  const [sourceFor, setSourceFor] = useState<{ id: string; text: string } | null>(null)
  const [practiceFor, setPracticeFor] = useState<string | null>(null)
  const [practiceGoalId, setPracticeGoalId] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  useEffect(() => {
    if (!message) return
    const t = setTimeout(() => setMessage(null), 2500)
    return () => clearTimeout(t)
  }, [message])

  const act = async (card: FactInboxCard, action: string, payload: Record<string, unknown> = {}) => {
    setBusy(card.id)
    try {
      await productApi.factAction(card.id, action, payload)
      if (action === 'PRACTICE') {
        const goalId = String(payload.goal_id || '')
        setMessage('已设为这个目标的 Next Focus，进入练习')
        setPracticeFor(null)
        setPracticeGoalId('')
        await reload()
        if (goalId) navigate(paths.practice(undefined, { goal: goalId }))
        return
      }
      setMessage('已更新')
      await reload()
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '操作失败')
    } finally {
      setBusy(null)
      setEditing(null)
      setSourceFor(null)
    }
  }

  const startPractice = (card: FactInboxCard) => {
    const activeGoals = goals.data?.items ?? []
    const goalId = contextGoal || (activeGoals.length === 1 ? activeGoals[0].id : '')
    if (goalId) {
      void act(card, 'PRACTICE', { goal_id: goalId })
      return
    }
    if (!activeGoals.length) {
      setMessage('先创建一个求职目标，再把这条事实变成练习重点')
      navigate(paths.goals())
      return
    }
    setPracticeFor(card.id)
    setPracticeGoalId('')
  }

  if (loading && !data) return <Loading />
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return null

  return (
    <div data-testid="fact-inbox" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-text-primary">需要你确认 · {data.count}</h2>
        {onShowAll ? <SecondaryButton onClick={onShowAll}>全部事实与来源</SecondaryButton> : null}
      </div>
      {data.policy.mode === 'HIGH_ONLY' ? (
        <p className="text-[11px] text-text-muted">待确认的条目较多，这里只列出高风险的；其余合并成一组，可以一次处理。</p>
      ) : null}
      {message ? <p role="status" className="text-xs text-status-direct">{message}</p> : null}
      {!data.items.length && !data.batch ? <EmptyState title="没有需要确认的事实" body="导入简历或项目资料后，成竹会把需要你判断的说法放在这里。" /> : null}
      <ul className="space-y-2">
        {data.items.map((card) => {
          const [tone, label] = RISK[card.risk] ?? RISK.LOW
          return (
            <li key={card.id} className="rounded-2xl border border-bg-hover/60 bg-bg-secondary/50 p-3" aria-busy={busy === card.id}>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-muted">
                {card.project ? <span className="font-semibold text-text-primary">{card.project}</span> : null}
                <StatusBadge tone={tone}>{label}</StatusBadge>
              </div>
              {editing?.id === card.id ? (
                <div className="mt-2 space-y-1.5">
                  <textarea aria-label="修改这条事实" className={`${inputCls} min-h-[56px]`} value={editing.text} onChange={(e) => setEditing({ ...editing, text: e.target.value })} />
                  <div className="flex gap-2">
                    <PrimaryButton onClick={() => void act(card, 'EDIT', { text: editing.text })}>保存并确认</PrimaryButton>
                    <SecondaryButton onClick={() => setEditing(null)}>取消</SecondaryButton>
                  </div>
                </div>
              ) : (
                <p className="mt-1 text-sm text-text-primary">“{card.text}”</p>
              )}
              <p className="mt-1 text-xs text-text-secondary">材料目前支持：<span className="font-medium">{card.supported_label}</span></p>
              {sourceFor?.id === card.id ? (
                <div className="mt-2 space-y-1.5">
                  <textarea aria-label="补充来源" className={`${inputCls} min-h-[56px]`} placeholder="粘贴能支持这条说法的原文（设计文档、周报、PR 描述…）" value={sourceFor.text} onChange={(e) => setSourceFor({ ...sourceFor, text: e.target.value })} />
                  <div className="flex gap-2">
                    <PrimaryButton disabled={!sourceFor.text.trim()} onClick={() => void act(card, 'ADD_SOURCE', { source_text: sourceFor.text })}>添加来源</PrimaryButton>
                    <SecondaryButton onClick={() => setSourceFor(null)}>取消</SecondaryButton>
                  </div>
                </div>
              ) : null}
              {editing?.id !== card.id && sourceFor?.id !== card.id ? (
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                  {card.lead_language ? (
                    <>
                      <PrimaryButton disabled={busy === card.id} onClick={() => void act(card, 'LEAD')}>我主导</PrimaryButton>
                      <SecondaryButton disabled={busy === card.id} onClick={() => void act(card, 'PARTICIPATE')}>我参与</SecondaryButton>
                    </>
                  ) : (
                    <>
                      <PrimaryButton disabled={busy === card.id} onClick={() => void act(card, 'CONFIRM')}>属实</PrimaryButton>
                      <SecondaryButton disabled={busy === card.id} onClick={() => void act(card, 'DENY')}>不属实</SecondaryButton>
                    </>
                  )}
                  <SecondaryButton onClick={() => setEditing({ id: card.id, text: card.text })}>修改</SecondaryButton>
                  <ActionMenu label="更多事实操作" actions={[
                    { key: 'source', label: '查看来源 / 补来源', onSelect: () => setSourceFor({ id: card.id, text: '' }) },
                    { key: 'practice', label: '练这个说法', onSelect: () => startPractice(card) },
                    { key: 'note', label: '记成速记', onSelect: () => void act(card, 'QUICK_NOTE', { goal_id: contextGoal }) },
                    ...(data.merge_suggestions.find((g) => g[0] === card.id)
                      ? [{ key: 'merge', label: '合并相似说法', onSelect: () => void act(card, 'MERGE', { merge_ids: data.merge_suggestions.find((g) => g[0] === card.id)!.slice(1) }) }]
                      : []),
                    { key: 'dismiss', label: '暂不处理', onSelect: () => void act(card, 'DISMISS') },
                    { key: 'delete', label: '删除草稿', danger: true, onSelect: () => void act(card, 'DELETE_DRAFT') },
                  ]} />
                </div>
              ) : null}
              {practiceFor === card.id ? (
                <div className="mt-2 rounded-lg border border-accent-blue/25 bg-accent-blue/5 p-2">
                  <label className="text-[11px] font-medium text-text-secondary" htmlFor={`fact-practice-goal-${card.id}`}>把这条事实放进哪个求职目标练？</label>
                  <div className="mt-1.5 flex flex-wrap gap-2">
                    <select id={`fact-practice-goal-${card.id}`} aria-label="选择练习目标" value={practiceGoalId}
                      onChange={(e) => setPracticeGoalId(e.target.value)} className={`${inputCls} min-w-[180px] flex-1`}>
                      <option value="">选择求职目标</option>
                      {(goals.data?.items ?? []).map((g) => <option key={g.id} value={g.id}>{g.title}</option>)}
                    </select>
                    <PrimaryButton disabled={!practiceGoalId || busy === card.id}
                      onClick={() => void act(card, 'PRACTICE', { goal_id: practiceGoalId })}>设为重点并去练习</PrimaryButton>
                    <SecondaryButton onClick={() => { setPracticeFor(null); setPracticeGoalId('') }}>取消</SecondaryButton>
                  </div>
                </div>
              ) : null}
            </li>
          )
        })}
      </ul>
      {data.batch ? (
        <div className="rounded-2xl border border-dashed border-bg-hover p-3">
          <p className="text-sm text-text-primary">还有 {data.batch.count} 条低风险说法</p>
          <p className="text-[11px] text-text-muted">都有材料支持或风险较低，可以一次确认。</p>
          <div className="mt-2 flex gap-2">
            <SecondaryButton onClick={() => void productApi.factBatch(data.batch!.ids, 'CONFIRM').then(reload)}>全部确认</SecondaryButton>
            <SecondaryButton onClick={() => void productApi.factBatch(data.batch!.ids, 'DISMISS').then(reload)}>暂不处理</SecondaryButton>
          </div>
        </div>
      ) : null}
    </div>
  )
}
