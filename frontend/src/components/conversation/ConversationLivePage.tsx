import { useEffect, useState } from 'react'
import { PauseCircle, Pin, Square, Volume2 } from 'lucide-react'
import { conversationApi } from '@/lib/conversationApi'
import type { AssistanceMode, ConversationContinue, ConversationGuidance, ConversationItem, ConversationItemType } from '@/lib/conversationContracts'
import { navigate, paths } from '@/lib/router'
import { ErrorState, Field, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, StatusBadge, inputCls, useAsync } from '@/components/os/ui'

export default function ConversationLivePage({ sessionId }: { sessionId: string }) {
  const session = useAsync(() => conversationApi.session(sessionId), [sessionId])
  const [topic, setTopic] = useState('')
  const [question, setQuestion] = useState('')
  const [candidate, setCandidate] = useState('')
  const [source, setSource] = useState('')
  const [speaking, setSpeaking] = useState(false)
  const [guidance, setGuidance] = useState<ConversationGuidance | null>(null)
  const [suppressed, setSuppressed] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [itemType, setItemType] = useState<ConversationItemType>('OpenQuestion')
  const [itemTitle, setItemTitle] = useState('')
  const [owner, setOwner] = useState('')
  const [summary, setSummary] = useState<ConversationContinue | null>(null)
  const [mode, setMode] = useState<AssistanceMode>('BALANCED')
  const [askText, setAskText] = useState('')
  const [askResult, setAskResult] = useState<{ answer: string; matches: ConversationItem[]; grounded: boolean } | null>(null)

  useEffect(() => {
    if (session.data?.assistance_mode) setMode(session.data.assistance_mode)
  }, [session.data?.assistance_mode])

  if (session.loading) return <Page><Loading /></Page>
  if (session.error || !session.data) return <Page><ErrorState message={session.error ?? '会话不存在'} onRetry={session.reload} /></Page>
  const s = session.data

  const evaluate = async () => {
    setBusy(true); setError('')
    try {
      const refs = source.trim() ? [{ kind: 'USER_NOTE', excerpt: source.trim(), id: `manual:${sessionId}` }] : []
      const result = await conversationApi.evaluateGuidance(sessionId, {
        current_topic: topic,
        direct_question: question,
        candidate_text: candidate,
        source_refs: refs,
        user_speaking: speaking,
        relevance: candidate ? 1 : 0,
        novelty: candidate ? 1 : 0,
        provenance_strength: refs.length ? 1 : 0,
        role_relevance: 0.5,
        goal_relevance: 0.8,
        decision_impact: 0.8,
        interruption_cost: speaking ? 2 : 0,
      })
      setGuidance(result.guidance); setSuppressed(result.suppressed ?? '')
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  const changeMode = async (next: AssistanceMode) => {
    setMode(next)
    try { await conversationApi.patchSession(sessionId, { assistance_mode: next }); await session.reload() }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
  }

  const ask = async () => {
    if (!askText.trim()) return
    setBusy(true); setError('')
    try { setAskResult(await conversationApi.ask(sessionId, askText.trim())) }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  const addItem = async () => {
    if (!itemTitle.trim()) return
    setBusy(true); setError('')
    try {
      await conversationApi.addItem(sessionId, {
        item_type: itemType,
        title: itemTitle.trim(),
        owner_id: owner.trim(),
        source_excerpt: source.trim(),
        source_refs: source.trim() ? [{ kind: 'USER_NOTE', excerpt: source.trim(), id: `manual:${sessionId}` }] : [],
        epistemic_status: source.trim() ? 'OBSERVED' : 'UNKNOWN',
      })
      setItemTitle('')
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  const end = async () => {
    setBusy(true); setError('')
    try { setSummary(await conversationApi.end(sessionId)); await session.reload() }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  return (
    <Page wide testId="conversation-live">
      <PageHeader eyebrow="Conversation Beta" title={s.title} subtitle={`${s.status} · ${s.assistance_mode} · ${s.processing_mode}`}
        actions={<PrimaryButton disabled={busy || s.status === 'ENDED'} onClick={end} icon={<Square className="h-3.5 w-3.5" />}>结束并 Continue</PrimaryButton>} />

      {error ? <ErrorState message={error} /> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <div className="rounded-2xl border border-bg-tertiary bg-bg-secondary/25 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><div className="flex items-center gap-2"><span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent-green opacity-50" /><span className="relative inline-flex h-2 w-2 rounded-full bg-accent-green" /></span><span className="text-xs font-semibold text-text-primary">Listening / Context</span></div><p className="mt-1 text-[11px] text-text-muted">一次只显示一个最高价值 Guidance；没有足够价值时保持 SILENT。</p></div>
              <div className="flex items-center gap-2">
                <select value={mode} onChange={(e) => void changeMode(e.target.value as AssistanceMode)} aria-label="帮助方式"
                  className="rounded-xl border border-bg-hover bg-bg-primary px-2 py-1.5 text-xs text-text-primary outline-none">
                  <option value="QUIET">Quiet</option>
                  <option value="BALANCED">Balanced</option>
                  <option value="ACTIVE">Active</option>
                  <option value="PRESENTATION">Presentation</option>
                  <option value="ONE_ON_ONE">1:1</option>
                </select>
                <label className="flex items-center gap-2 text-xs text-text-secondary"><input type="checkbox" checked={speaking} onChange={(e) => setSpeaking(e.target.checked)} />我正在连续表达</label>
              </div>
            </div>
            <div className="mt-4 grid gap-3">
              <Field label="当前话题"><input className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="例如：offline migration" /></Field>
              <Field label="对方直接问我的问题（如有）"><input className={inputCls} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="直接问题优先于主动 Opportunity" /></Field>
              <Field label="值得补充的候选内容（如有）"><textarea className={inputCls} rows={3} value={candidate} onChange={(e) => setCandidate(e.target.value)} placeholder="例如：Q4 benchmark 已覆盖 10x data scale" /></Field>
              <Field label="来源 / 依据"><textarea className={inputCls} rows={2} value={source} onChange={(e) => setSource(e.target.value)} placeholder="主动 Contribution Opportunity 必须有来源；没有来源会被抑制。" /></Field>
            </div>
            <div className="mt-4"><PrimaryButton disabled={busy || s.status !== 'ACTIVE'} onClick={evaluate} icon={<Volume2 className="h-3.5 w-3.5" />}>评估当前 Guidance</PrimaryButton></div>
          </div>

          <div className="min-h-[160px] rounded-2xl border border-accent-blue/20 bg-bg-primary p-5">
            {guidance ? (
              <>
                <div className="flex flex-wrap items-center gap-2"><StatusBadge tone={guidance.kind === 'RISK' ? 'risk' : guidance.kind === 'CONTRIBUTION_OPPORTUNITY' ? 'info' : 'ok'}>{guidance.kind}</StatusBadge><span className="text-[11px] text-text-muted">{guidance.expression_action}</span></div>
                <p className="mt-4 text-lg font-medium leading-relaxed text-text-primary">{guidance.text}</p>
                <p className="mt-3 text-xs text-text-muted">来源：{guidance.source_refs.length ? guidance.source_refs.map((x) => x.kind).join(' · ') : '当前直接问题 / 会话状态'} · reason {guidance.reason}</p>
                <div className="mt-4 flex gap-2"><SecondaryButton onClick={() => void conversationApi.guidanceAction(guidance.id, 'PINNED')} icon={<Pin className="h-3.5 w-3.5" />}>Pin</SecondaryButton><SecondaryButton onClick={() => { void conversationApi.guidanceAction(guidance.id, 'DISMISSED'); setGuidance(null) }}>忽略</SecondaryButton></div>
              </>
            ) : (
              <div className="flex h-full min-h-[120px] flex-col items-center justify-center text-center">
                <PauseCircle className="h-7 w-7 text-text-muted" />
                <p className="mt-2 text-sm font-medium text-text-primary">{suppressed ? '这一次选择不打扰你' : '等待高价值 Guidance'}</p>
                <p className="mt-1 text-xs text-text-muted">{suppressed ? `SILENT · ${suppressed}` : 'Direct Question > Critical Risk > Recall / Opportunity > Question > Delivery'}</p>
              </div>
            )}
          </div>
        </div>

        <aside className="space-y-4">
          <div className="rounded-2xl border border-bg-tertiary p-4">
            <h2 className="text-sm font-semibold text-text-primary">问成竹 · 已确认历史</h2>
            <p className="mt-1 text-[11px] text-text-muted">只检索这个 Space 中已经确认、仍有效的 Decision / Commitment 等记录；找不到就明确说找不到。</p>
            <div className="mt-3 space-y-2">
              <textarea className={inputCls} rows={2} value={askText} onChange={(e) => setAskText(e.target.value)} placeholder="例如：我们之前为什么决定用 v2？" />
              <SecondaryButton disabled={busy || !askText.trim()} onClick={ask}>查已确认记录</SecondaryButton>
            </div>
            {askResult ? <div className="mt-3 rounded-xl bg-bg-secondary/45 p-3"><p className="text-xs text-text-primary">{askResult.answer}</p><p className="mt-1 text-[11px] text-text-muted">{askResult.grounded ? `已找到 ${askResult.matches.length} 条可追溯记录` : '没有用模型猜测答案'}</p></div> : null}
          </div>

          <div className="rounded-2xl border border-bg-tertiary p-4">
            <h2 className="text-sm font-semibold text-text-primary">记录结构化事项</h2>
            <p className="mt-1 text-[11px] text-text-muted">模型抽取默认只是待确认 Candidate，不会自动升级成团队 Decision。</p>
            <div className="mt-3 space-y-3">
              <Field label="类型"><select className={inputCls} value={itemType} onChange={(e) => setItemType(e.target.value as ConversationItemType)}><option>OpenQuestion</option><option>Decision</option><option>Commitment</option><option>Task</option><option>Risk</option><option>Proposal</option><option>Objection</option><option>Metric</option><option>Status</option></select></Field>
              <Field label="内容"><textarea className={inputCls} rows={3} value={itemTitle} onChange={(e) => setItemTitle(e.target.value)} /></Field>
              {itemType === 'Commitment' || itemType === 'Task' ? <Field label="Owner（可先未知）"><input className={inputCls} value={owner} onChange={(e) => setOwner(e.target.value)} placeholder="例如：me / Alex" /></Field> : null}
              <PrimaryButton disabled={busy || !itemTitle.trim()} onClick={addItem}>记录为待确认</PrimaryButton>
            </div>
          </div>
        </aside>
      </div>

      {summary ? <div className="mt-5 rounded-2xl border border-accent-blue/25 bg-accent-blue/5 p-5">
        <h2 className="text-sm font-semibold text-text-primary">这场之后</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-4"><div><div className="text-2xl font-semibold">{summary.decisions.length}</div><div className="text-[11px] text-text-muted">Decisions</div></div><div><div className="text-2xl font-semibold">{summary.commitments.length}</div><div className="text-[11px] text-text-muted">Commitments</div></div><div><div className="text-2xl font-semibold">{summary.open_questions.length}</div><div className="text-[11px] text-text-muted">Open Questions</div></div><div><div className="text-2xl font-semibold">{summary.review_required}</div><div className="text-[11px] text-text-muted">待确认</div></div></div>
        {summary.next_focus ? <p className="mt-4 text-sm text-text-primary">Next Focus · {summary.next_focus.title}</p> : null}
        <div className="mt-4"><PrimaryButton onClick={() => navigate(paths.conversationSpace(s.space_id, 'sessions'))}>回到 Space · Continue</PrimaryButton></div>
      </div> : null}
    </Page>
  )
}
