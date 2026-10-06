import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Download, Play, Plus, ShieldCheck, Trash2 } from 'lucide-react'
import { conversationApi } from '@/lib/conversationApi'
import { productApi } from '@/lib/productApi'
import type { AssistanceMode, CaptureMode, ConversationContinue, ConversationItem, ConversationPreflight, ProcessingMode } from '@/lib/conversationContracts'
import { navigate, paths, type ConversationTab } from '@/lib/router'
import { EmptyState, ErrorState, Field, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, Section, StatusBadge, Tabs, inputCls, useAsync } from '@/components/os/ui'

function ItemRow({ item, onChanged }: { item: ConversationItem; onChanged: () => void }) {
  const [busy, setBusy] = useState(false)
  const review = async (action: 'CONFIRM' | 'REJECT' | 'DONE') => {
    setBusy(true)
    try { await conversationApi.reviewItem(item.id, action, item.owner_id ? {} : { owner_id: 'me' }); onChanged() } finally { setBusy(false) }
  }
  const tone = item.state === 'AGREED' || item.state === 'COMMITTED' || item.state === 'DONE' ? 'ok' : item.review_status === 'AI_EXTRACTED' ? 'warn' : 'muted'
  return (
    <div className="rounded-xl border border-bg-tertiary/70 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2"><span className="text-sm text-text-primary">{item.title}</span><StatusBadge tone={tone}>{item.state}</StatusBadge>{item.review_status === 'AI_EXTRACTED' ? <StatusBadge tone="warn">待确认</StatusBadge> : null}</div>
      <div className="mt-1 text-[11px] text-text-muted">来源 {item.source_refs.length ? item.source_refs.map((s) => s.kind).join(' · ') : '未附来源'}{item.owner_id ? ` · owner ${item.owner_id}` : ''}</div>
      {item.review_status === 'AI_EXTRACTED' ? <div className="mt-2 flex gap-2"><SecondaryButton disabled={busy} onClick={() => review('CONFIRM')}>确认</SecondaryButton><SecondaryButton disabled={busy} onClick={() => review('REJECT')}>拒绝</SecondaryButton></div> : item.state === 'COMMITTED' ? <div className="mt-2"><SecondaryButton disabled={busy} onClick={() => review('DONE')}>标记完成</SecondaryButton></div> : null}
    </div>
  )
}

export default function ConversationSpacePage({ spaceId, tab }: { spaceId: string; tab: ConversationTab }) {
  const detail = useAsync(() => conversationApi.space(spaceId), [spaceId])
  const prepare = useAsync(() => conversationApi.prepare(spaceId), [spaceId])
  const materials = useAsync(() => productApi.materials(), [])
  const quickNotes = useAsync(() => productApi.quickNotes(), [])
  const [capture, setCapture] = useState<CaptureMode>('NOTES_ONLY')
  const [processing, setProcessing] = useState<ProcessingMode>('LOCAL')
  const [mode, setMode] = useState<AssistanceMode>('BALANCED')
  const [consent, setConsent] = useState(false)
  const [preflight, setPreflight] = useState<ConversationPreflight | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [sessionBusy, setSessionBusy] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [continueData, setContinueData] = useState<ConversationContinue | null>(null)
  const [participantName, setParticipantName] = useState('')
  const [participantRole, setParticipantRole] = useState('')
  const [goalTitle, setGoalTitle] = useState('')
  const [sourceSaving, setSourceSaving] = useState(false)

  useEffect(() => { if (detail.data?.default_mode) setMode(detail.data.default_mode) }, [detail.data?.default_mode])

  const tabs = useMemo<Array<[ConversationTab, string, number?]>>(() => [
    ['overview', '概览'],
    ['prepare', '准备'],
    ['sessions', '会话', detail.data?.sessions.length ?? 0],
    ['decisions', '决策', detail.data?.decisions.filter((x) => x.state === 'AGREED').length ?? 0],
  ], [detail.data])

  if (detail.loading) return <Page><Loading /></Page>
  if (detail.error || !detail.data) return <Page><ErrorState message={detail.error ?? '对话空间不存在'} onRetry={detail.reload} /></Page>
  const space = detail.data

  const makePreflight = async () => {
    setSessionBusy(true); setSessionError('')
    try {
      const session = await conversationApi.createSession(spaceId, { capture_mode: capture, processing_mode: processing, assistance_mode: mode, consent_ack: consent })
      setSessionId(session.id)
      setPreflight(await conversationApi.preflight(session.id))
      await detail.reload()
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const addParticipant = async () => {
    if (!participantName.trim() && !participantRole.trim()) return
    setSessionBusy(true); setSessionError('')
    try {
      await conversationApi.addParticipant(spaceId, { display_name: participantName.trim(), role: participantRole.trim() })
      setParticipantName(''); setParticipantRole('')
      await detail.reload(); await prepare.reload()
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const addGoal = async () => {
    if (!goalTitle.trim()) return
    setSessionBusy(true); setSessionError('')
    try {
      await conversationApi.addGoal(spaceId, { title: goalTitle.trim() })
      setGoalTitle('')
      await detail.reload(); await prepare.reload()
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const toggleSource = async (id: string) => {
    const selected = new Set(space.selected_source_ids ?? [])
    if (selected.has(id)) selected.delete(id); else selected.add(id)
    setSourceSaving(true); setSessionError('')
    try { await conversationApi.patchSpace(spaceId, { selected_source_ids: Array.from(selected) }); await detail.reload(); await prepare.reload() }
    catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSourceSaving(false) }
  }

  const toggleQuickNote = async (id: string) => {
    const selected = new Set(space.selected_quick_note_ids ?? [])
    if (selected.has(id)) selected.delete(id); else selected.add(id)
    setSourceSaving(true); setSessionError('')
    try { await conversationApi.patchSpace(spaceId, { selected_quick_note_ids: Array.from(selected) }); await detail.reload(); await prepare.reload() }
    catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSourceSaving(false) }
  }

  const exportSpace = async () => {
    setSessionBusy(true); setSessionError('')
    try {
      const payload = await conversationApi.exportSpace(spaceId)
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `chengzhu-conversation-${spaceId}.json`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const deleteSpace = async () => {
    if (!window.confirm('删除这个对话空间？其中的 Session、Guidance 与派生事项会一起删除；Interview 数据不会受影响。')) return
    setSessionBusy(true); setSessionError('')
    try { await conversationApi.deleteSpace(spaceId); navigate(paths.conversationSpaces()) }
    catch (e) { setSessionError(e instanceof Error ? e.message : String(e)); setSessionBusy(false) }
  }

  const start = async () => {
    if (!sessionId) return
    setSessionBusy(true); setSessionError('')
    try {
      await conversationApi.start(sessionId)
      navigate(paths.conversationLive(sessionId))
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  return (
    <Page wide testId="conversation-space">
      <button type="button" onClick={() => navigate(paths.conversationSpaces())} className="mb-3 inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-primary"><ArrowLeft className="h-3.5 w-3.5" /> 对话空间</button>
      <PageHeader eyebrow={space.profile} title={space.title} subtitle={space.description || space.default_goal || '持续保留 Decision、Commitment 与 Open Question。'}
        actions={<>
          <SecondaryButton onClick={exportSpace} disabled={sessionBusy} icon={<Download className="h-3.5 w-3.5" />}>导出</SecondaryButton>
          <SecondaryButton onClick={deleteSpace} disabled={sessionBusy} icon={<Trash2 className="h-3.5 w-3.5" />}>删除</SecondaryButton>
          <PrimaryButton onClick={() => navigate(paths.conversationSpace(spaceId, 'prepare'))} icon={<Play className="h-3.5 w-3.5" />}>准备 / 开始</PrimaryButton>
        </>} />
      <Tabs tabs={tabs} value={tab} label="对话空间" onChange={(v) => navigate(paths.conversationSpace(spaceId, v))} />

      {tab === 'overview' ? (
        <div className="pt-3">
          <Section title="Next Focus">
            {prepare.data?.open_questions[0] ? <p className="text-sm text-text-primary">{prepare.data.open_questions[0].title}</p> :
              prepare.data?.open_commitments[0] ? <p className="text-sm text-text-primary">{prepare.data.open_commitments[0].title}</p> :
              <p className="text-xs text-text-muted">{space.default_goal || '当前没有开放事项。'}</p>}
          </Section>
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Open Commitments">{prepare.loading ? <Loading /> : prepare.data?.open_commitments.length ? <div className="space-y-2">{prepare.data.open_commitments.map((x) => <ItemRow key={x.id} item={x} onChanged={() => { void detail.reload(); void prepare.reload() }} />)}</div> : <p className="text-xs text-text-muted">暂无。</p>}</Section>
            <Section title="Open Questions">{prepare.loading ? <Loading /> : prepare.data?.open_questions.length ? <div className="space-y-2">{prepare.data.open_questions.map((x) => <ItemRow key={x.id} item={x} onChanged={() => { void detail.reload(); void prepare.reload() }} />)}</div> : <p className="text-xs text-text-muted">暂无。</p>}</Section>
          </div>
          <Section title="参与者（只记录明确信息）">
            {space.participants.length ? <div className="flex flex-wrap gap-2">{space.participants.map((p) => <span key={p.id} className="rounded-full border border-bg-tertiary px-2.5 py-1 text-xs text-text-secondary">{p.display_name || '未命名'}{p.role ? ` · ${p.role}` : ''}</span>)}</div> : <p className="text-xs text-text-muted">还没有明确参与者；系统不会凭声音自动建立长期身份。</p>}
            <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]"><input className={inputCls} value={participantName} onChange={(e) => setParticipantName(e.target.value)} placeholder="姓名 / 昵称（可选）" /><input className={inputCls} value={participantRole} onChange={(e) => setParticipantRole(e.target.value)} placeholder="明确角色，例如 Backend" /><SecondaryButton onClick={addParticipant} disabled={sessionBusy || (!participantName.trim() && !participantRole.trim())} icon={<Plus className="h-3.5 w-3.5" />}>添加</SecondaryButton></div>
          </Section>
          <Section title="Conversation Goals">
            {space.goals.length ? <div className="space-y-1">{space.goals.map((g) => <div key={g.id} className="text-xs text-text-primary">• {g.title}</div>)}</div> : <p className="text-xs text-text-muted">可把本次需要形成 Decision / 明确 owner 等目标写在这里。</p>}
            <div className="mt-3 flex gap-2"><input className={inputCls} value={goalTitle} onChange={(e) => setGoalTitle(e.target.value)} placeholder="新增一个可验证的对话目标" /><SecondaryButton onClick={addGoal} disabled={sessionBusy || !goalTitle.trim()} icon={<Plus className="h-3.5 w-3.5" />}>添加</SecondaryButton></div>
          </Section>
        </div>
      ) : null}

      {tab === 'prepare' ? (
        <div className="pt-3">
          {prepare.error ? <ErrorState message={prepare.error} onRetry={prepare.reload} /> : null}
          <Section title="Brief">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl bg-bg-secondary/40 p-3"><div className="text-[11px] text-text-muted">本次长期目标</div><div className="mt-1 text-sm text-text-primary">{space.default_goal || '未设置'}</div></div>
              <div className="rounded-xl bg-bg-secondary/40 p-3"><div className="text-[11px] text-text-muted">未完成承诺</div><div className="mt-1 text-sm text-text-primary">{prepare.data?.open_commitments.length ?? 0}</div></div>
              <div className="rounded-xl bg-bg-secondary/40 p-3"><div className="text-[11px] text-text-muted">开放问题</div><div className="mt-1 text-sm text-text-primary">{prepare.data?.open_questions.length ?? 0}</div></div>
            </div>
          </Section>
          <Section title="本场带入来源">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <div className="mb-2 text-xs font-semibold text-text-secondary">项目资料 / 知识库</div>
                {materials.loading ? <Loading /> : materials.data?.items.length ? <div className="space-y-1.5">{materials.data.items.map((m) => {
                  const ready = m.lifecycle.state === 'READY' || m.lifecycle.state === 'REPLACING'
                  const checked = (space.selected_source_ids ?? []).includes(m.id)
                  return <label key={m.id} className={`flex items-start gap-2 rounded-xl px-2 py-1.5 text-xs ${ready ? 'hover:bg-bg-hover/40' : 'opacity-50'}`}><input type="checkbox" checked={checked} disabled={!ready || sourceSaving} onChange={() => void toggleSource(m.id)} className="mt-0.5" /><span><span className="text-text-primary">{m.title}</span><span className="ml-1 text-text-muted">{m.kind} · {m.usage} · {m.lifecycle.state}</span></span></label>
                })}</div> : <p className="text-xs text-text-muted">资料库里还没有 Ready 资料。可以先不带资料开始。</p>}
              </div>
              <div>
                <div className="mb-2 text-xs font-semibold text-text-secondary">Quick Notes</div>
                {quickNotes.loading ? <Loading /> : quickNotes.data?.items.length ? <div className="space-y-1.5">{quickNotes.data.items.map((n) => <label key={n.id} className="flex items-start gap-2 rounded-xl px-2 py-1.5 text-xs hover:bg-bg-hover/40"><input type="checkbox" checked={(space.selected_quick_note_ids ?? []).includes(n.id)} disabled={sourceSaving} onChange={() => void toggleQuickNote(n.id)} className="mt-0.5" /><span><span className="text-text-primary">{n.title || n.content.slice(0, 50)}</span><span className="ml-1 text-text-muted">用户速记 · 非证据</span></span></label>)}</div> : <p className="text-xs text-text-muted">没有 Quick Notes。</p>}
              </div>
            </div>
            <p className="mt-3 text-[11px] text-text-muted">Session 开始时会冻结 Ready 版本与所选 Quick Notes；后续替换资料不会静默改写这场的 Pack。</p>
          </Section>
          <Section title="Preflight">
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="记录方式"><select className={inputCls} value={capture} onChange={(e) => setCapture(e.target.value as CaptureMode)}><option value="NOTES_ONLY">仅结构化笔记</option><option value="TRANSCRIPT">转写</option><option value="NO_CAPTURE">不记录</option></select></Field>
              <Field label="处理方式"><select className={inputCls} value={processing} onChange={(e) => setProcessing(e.target.value as ProcessingMode)}><option value="LOCAL">Local</option><option value="CLOUD">Cloud</option><option value="OFF">Off</option></select></Field>
              <Field label="帮助方式"><select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value as AssistanceMode)}><option value="QUIET">Quiet</option><option value="BALANCED">Balanced</option><option value="ACTIVE">Active</option><option value="PRESENTATION">Presentation</option><option value="ONE_ON_ONE">1:1</option></select></Field>
            </div>
            <label className="mt-4 flex items-start gap-2 text-xs text-text-secondary"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5" /><span>我已确认当前场景允许我使用所选择的记录/转写方式。这个勾选不代表其他参与者已经同意。</span></label>
            <div className="mt-4 flex gap-2"><PrimaryButton disabled={sessionBusy} onClick={makePreflight} icon={<ShieldCheck className="h-3.5 w-3.5" />}>{sessionBusy ? '检查中…' : '生成本场并检查'}</PrimaryButton>{preflight && !preflight.blockers.length ? <PrimaryButton disabled={sessionBusy} onClick={start}>开始会话</PrimaryButton> : null}</div>
            {sessionError ? <div className="mt-3"><ErrorState message={sessionError} /></div> : null}
            {preflight ? <div className="mt-4 rounded-2xl border border-bg-tertiary p-3">
              <div className="space-y-1">{preflight.items.map((x) => <div key={x.key} className="flex items-center justify-between text-xs"><span className="text-text-muted">{x.label}</span><span className="text-text-primary">{String(x.value)}</span></div>)}</div>
              {preflight.blockers.map((x) => <div key={x.key} className="mt-2 text-xs text-status-risk">{x.message}</div>)}
              <p className="mt-3 text-[11px] text-text-muted">{preflight.privacy_note}</p>
            </div> : null}
          </Section>
        </div>
      ) : null}

      {tab === 'sessions' ? (
        <div className="pt-3">
          {space.sessions.length ? <div className="space-y-2">{space.sessions.map((s) => (
            <div key={s.id} className="rounded-xl border border-bg-tertiary/70 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2"><div><div className="text-sm font-medium text-text-primary">{s.title}</div><div className="text-[11px] text-text-muted">{s.status} · {s.assistance_mode} · {s.capture_mode}</div></div>
                <div className="flex gap-2">{s.status !== 'ENDED' ? <SecondaryButton onClick={() => navigate(paths.conversationLive(s.id))}>进入</SecondaryButton> : <SecondaryButton onClick={async () => setContinueData(await conversationApi.continue(s.id))}>Continue</SecondaryButton>}</div>
              </div>
            </div>
          ))}</div> : <EmptyState title="还没有会话" body="从“准备”创建本场 Preflight。" />}
          {continueData ? <div className="mt-4 rounded-2xl border border-accent-blue/25 bg-accent-blue/5 p-4">
            <h3 className="text-sm font-semibold text-text-primary">这场之后</h3>
            <p className="mt-1 text-xs text-text-muted">Decision {continueData.decisions.length} · Commitment {continueData.commitments.length} · Open Question {continueData.open_questions.length} · 待确认 {continueData.review_required}</p>
            {continueData.next_focus ? <p className="mt-3 text-sm text-text-primary">Next Focus · {continueData.next_focus.title}</p> : null}
            {continueData.candidates.length ? <div className="mt-4 space-y-2"><div className="text-xs font-semibold text-text-secondary">逐项确认 AI / 会中提取</div>{continueData.candidates.map((item) => <ItemRow key={item.id} item={item} onChanged={async () => { setContinueData(await conversationApi.continue(continueData.session.id)); await detail.reload(); await prepare.reload() }} />)}</div> : <p className="mt-3 text-xs text-status-direct">没有未确认事项。</p>}
          </div> : null}
        </div>
      ) : null}

      {tab === 'decisions' ? (
        <div className="pt-3">
          <Section title="Decisions">
            {space.decisions.length ? <div className="space-y-2">{space.decisions.map((x) => <ItemRow key={x.id} item={x} onChanged={() => { void detail.reload(); void prepare.reload() }} />)}</div> : <EmptyState title="还没有 Decision" body="会中抽取默认只是 Proposed；只有有来源且确认后才会升级为 Agreed。" />}
          </Section>
        </div>
      ) : null}
    </Page>
  )
}
