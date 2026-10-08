import { useEffect, useMemo, useState } from 'react'
import { Archive, ArrowLeft, Download, Play, Plus, RotateCcw, ShieldCheck, Trash2 } from 'lucide-react'
import { conversationApi } from '@/lib/conversationApi'
import { activateConversationSharePrivacy, restoreConversationSharePrivacy } from '@/lib/conversationSharePrivacy'
import { productApi } from '@/lib/productApi'
import type { AssistanceMode, CaptureMode, ConversationContinue, ConversationDraftAction, ConversationGoal, ConversationItem, ConversationParticipant, ConversationPreflight, ProcessingMode } from '@/lib/conversationContracts'
import { navigate, paths, type ConversationTab } from '@/lib/router'
import { EmptyState, ErrorState, Field, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, Section, StatusBadge, Tabs, inputCls, useAsync } from '@/components/os/ui'

function ItemRow({ item, onChanged, supersedeOptions = [] }: { item: ConversationItem; onChanged: () => void; supersedeOptions?: ConversationItem[] }) {
  const [busy, setBusy] = useState(false)
  const [supersedesId, setSupersedesId] = useState('')
  const [reviewOwner, setReviewOwner] = useState(item.owner_id || '')
  const [timeNormalized, setTimeNormalized] = useState(item.time_semantics?.normalized_datetime || item.due_at || '')
  const [timeTimezone, setTimeTimezone] = useState(item.time_semantics?.timezone || '')
  const [rowError, setRowError] = useState('')
  const temporalAmbiguity = item.time_semantics?.ambiguity || (item.type === 'Deadline' ? 'AMBIGUOUS' : 'NOT_APPLICABLE')
  const needsTimeReview = item.review_status === 'AI_EXTRACTED'
    && ['Deadline', 'Commitment', 'Task'].includes(item.type)
    && temporalAmbiguity !== 'NOT_APPLICABLE'
    && temporalAmbiguity !== 'EXACT'
  const review = async (action: 'CONFIRM' | 'REJECT' | 'DONE' | 'RESOLVE' | 'SUPERSEDE') => {
    setBusy(true); setRowError('')
    try {
      let patch: Record<string, unknown> = {}
      if (action === 'SUPERSEDE') patch = { supersedes_id: supersedesId }
      else if (action === 'CONFIRM') {
        if (['Commitment', 'Task'].includes(item.type) && !item.owner_id) {
          if (!reviewOwner.trim()) throw new Error('确认 Commitment / Task 前需要明确 owner')
          patch.owner_id = reviewOwner.trim()
        }
        if (needsTimeReview) {
          if (!timeNormalized.trim() || !timeTimezone.trim()) throw new Error('确认时间事项前需要 normalized datetime 与 timezone')
          patch.due_at = timeNormalized.trim()
          patch.time_semantics = {
            original_text: item.time_semantics?.original_text || item.title,
            normalized_datetime: timeNormalized.trim(),
            timezone: timeTimezone.trim(),
            ambiguity: 'EXACT',
          }
        }
      }
      await conversationApi.reviewItem(item.id, action, patch)
      onChanged()
    } catch (e) {
      setRowError(e instanceof Error ? e.message : String(e))
    } finally { setBusy(false) }
  }
  const tone = item.state === 'AGREED' || item.state === 'COMMITTED' || item.state === 'DONE' ? 'ok' : item.review_status === 'AI_EXTRACTED' ? 'warn' : 'muted'
  return (
    <div className="rounded-xl border border-bg-tertiary/70 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2"><span className="text-sm text-text-primary">{item.title}</span><StatusBadge tone={tone}>{item.state}</StatusBadge>{item.review_status === 'AI_EXTRACTED' ? <StatusBadge tone="warn">待确认</StatusBadge> : null}</div>
      <div className="mt-1 text-[11px] text-text-muted">来源 {item.source_refs.length ? item.source_refs.map((s) => s.kind).join(' · ') : '未附来源'}{item.speaker_id ? ` · speaker ${item.speaker_id}` : ''}{item.owner_id ? ` · owner ${item.owner_id}` : ''}{item.due_at ? ` · due ${item.due_at}` : ''}{item.supersedes_id ? ` · supersedes ${item.supersedes_id}` : ''}</div>
      {item.time_semantics && temporalAmbiguity !== 'NOT_APPLICABLE' ? <div className="mt-1 text-[10px] text-text-muted">
        时间 · 原话 {item.time_semantics.original_text || '—'} · normalized {item.time_semantics.normalized_datetime || '未确认'} · timezone {item.time_semantics.timezone || '未确认'} · <span className={temporalAmbiguity === 'EXACT' ? 'text-status-direct' : 'text-status-inferred'}>{temporalAmbiguity}</span>
      </div> : null}
      {item.review_status === 'AI_EXTRACTED' && ['Commitment', 'Task'].includes(item.type) && !item.owner_id ? <div className="mt-2 rounded-lg bg-bg-secondary/35 p-2">
        <div className="text-[10px] text-text-muted">Owner 当前未知；不要把主音频里的“我”自动当成当前用户。</div>
        <input aria-label="确认 Owner" className={`${inputCls} mt-2`} value={reviewOwner} onChange={(e) => setReviewOwner(e.target.value)} placeholder="明确 owner，例如 me / Alex" />
      </div> : null}
      {needsTimeReview ? <div className="mt-2 rounded-lg border border-status-inferred/30 bg-status-inferred/5 p-2">
        <div className="text-[10px] text-text-muted">原始时间表达仍有歧义。成竹不会自动把“下周五 / Friday”升级成长期 Deadline；请在确认前明确归一化时间和时区。</div>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <input aria-label="归一化时间" type="datetime-local" className={inputCls} value={timeNormalized} onChange={(e) => setTimeNormalized(e.target.value)} />
          <input aria-label="时区" className={inputCls} value={timeTimezone} onChange={(e) => setTimeTimezone(e.target.value)} placeholder="例如 Asia/Shanghai" />
        </div>
      </div> : null}
      {item.review_status === 'AI_EXTRACTED' ? <div className="mt-2 flex flex-wrap gap-2"><SecondaryButton disabled={busy || (['Commitment', 'Task'].includes(item.type) && !item.owner_id && !reviewOwner.trim()) || (needsTimeReview && (!timeNormalized.trim() || !timeTimezone.trim()))} onClick={() => review('CONFIRM')}>确认</SecondaryButton><SecondaryButton disabled={busy} onClick={() => review('REJECT')}>拒绝</SecondaryButton></div> : item.state === 'COMMITTED' ? <div className="mt-2"><SecondaryButton disabled={busy} onClick={() => review('DONE')}>标记完成</SecondaryButton></div> : ['OpenQuestion', 'Risk', 'Objection'].includes(item.type) && !['DONE', 'SUPERSEDED', 'UNKNOWN'].includes(item.state) ? <div className="mt-2"><SecondaryButton disabled={busy} onClick={() => review('RESOLVE')}>标记已解决</SecondaryButton></div> : null}
      {item.type === 'Decision' && item.state === 'PROPOSED' && item.review_status === 'AI_EXTRACTED' && supersedeOptions.length ? (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg bg-bg-secondary/35 p-2">
          <select aria-label="要替代的旧 Decision" className={inputCls} value={supersedesId} onChange={(e) => setSupersedesId(e.target.value)}>
            <option value="">选择旧 Decision（可选）</option>
            {supersedeOptions.filter((x) => x.id !== item.id && x.state === 'AGREED').map((x) => <option key={x.id} value={x.id}>{x.title}</option>)}
          </select>
          <SecondaryButton disabled={busy || !supersedesId || !item.source_refs.length} onClick={() => review('SUPERSEDE')}>确认并替代旧 Decision</SecondaryButton>
        </div>
      ) : null}
      {rowError ? <div className="mt-2 text-[11px] text-status-risk">{rowError}</div> : null}
    </div>
  )
}

export default function ConversationSpacePage({ spaceId, tab }: { spaceId: string; tab: ConversationTab }) {
  const detail = useAsync(() => conversationApi.space(spaceId), [spaceId])
  const prepare = useAsync(() => conversationApi.prepare(spaceId), [spaceId])
  const materials = useAsync(() => productApi.materials(), [])
  const quickNotes = useAsync(() => productApi.quickNotes(), [])
  const retention = useAsync(() => conversationApi.retentionPreview(spaceId), [spaceId])
  const [sessionTitle, setSessionTitle] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [capture, setCapture] = useState<CaptureMode>('NOTES_ONLY')
  const [processing, setProcessing] = useState<ProcessingMode>('LOCAL')
  const [mode, setMode] = useState<AssistanceMode>('BALANCED')
  const [screenContext, setScreenContext] = useState<'OFF' | 'MANUAL' | 'AUTO'>('OFF')
  const [aiPolicy, setAiPolicy] = useState<'AI_FORBIDDEN' | 'AI_LIMITED' | 'AI_ALLOWED' | 'AI_EXPECTED'>('AI_ALLOWED')
  const [humanPolicy, setHumanPolicy] = useState<'HUMAN_FORBIDDEN' | 'HUMAN_PRACTICE_ONLY' | 'HUMAN_ALLOWED'>('HUMAN_PRACTICE_ONLY')
  const [sharePrivacy, setSharePrivacy] = useState<'OFF' | 'PRIVATE_OVERLAY'>('OFF')
  const [externalWriteback, setExternalWriteback] = useState<'OFF' | 'REVIEW_REQUIRED'>('REVIEW_REQUIRED')
  const [participantConsent, setParticipantConsent] = useState<'NOT_RECORDED' | 'USER_REPORTS_ALLOWED' | 'USER_REPORTS_CONSENTED' | 'NOT_APPLICABLE'>('NOT_RECORDED')
  const [participantTransparency, setParticipantTransparency] = useState<'NOT_RECORDED' | 'USER_WILL_NOTIFY_VERBALLY' | 'USER_WILL_NOTIFY_IN_CHAT' | 'USER_REPORTS_ALREADY_NOTIFIED' | 'NOT_APPLICABLE'>('NOT_RECORDED')
  const [consent, setConsent] = useState(false)
  const [preflight, setPreflight] = useState<ConversationPreflight | null>(null)
  const [sessionId, setSessionId] = useState('')
  const [sessionBusy, setSessionBusy] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [continueData, setContinueData] = useState<ConversationContinue | null>(null)
  const [participantName, setParticipantName] = useState('')
  const [participantRole, setParticipantRole] = useState('')
  const [participantPriority, setParticipantPriority] = useState('')
  const [participantConcern, setParticipantConcern] = useState('')
  const [participantPosition, setParticipantPosition] = useState('')
  const [participantAuthority, setParticipantAuthority] = useState('')
  const [participantRelationship, setParticipantRelationship] = useState('')
  const [editingParticipantId, setEditingParticipantId] = useState('')
  const [goalTitle, setGoalTitle] = useState('')
  const [goalOutcome, setGoalOutcome] = useState('')
  const [goalPriority, setGoalPriority] = useState('50')
  const [editingGoalId, setEditingGoalId] = useState('')
  const [sourceSaving, setSourceSaving] = useState(false)
  const [draft, setDraft] = useState<ConversationDraftAction | null>(null)
  const [lifecycleMessage, setLifecycleMessage] = useState('')

  const resolveThread = async (threadId: string) => {
    setSessionBusy(true); setSessionError('')
    try {
      await conversationApi.resolveThread(threadId)
      setLifecycleMessage('Open Thread 已通过其 reviewed Conversation Item provenance 标记为已解决。')
      await detail.reload()
      await prepare.reload()
    } catch (e) {
      setSessionError(e instanceof Error ? e.message : String(e))
    } finally { setSessionBusy(false) }
  }

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
      const session = await conversationApi.createSession(spaceId, {
        title: sessionTitle.trim() || undefined,
        scheduled_at: scheduledAt ? new Date(scheduledAt).getTime() / 1000 : null,
        capture_mode: capture,
        processing_mode: processing,
        assistance_mode: mode,
        consent_ack: consent,
        policy: {
          screen_context: screenContext,
          ai_assistance: aiPolicy,
          human_assistance: humanPolicy,
          share_privacy: sharePrivacy,
          external_writeback: externalWriteback,
          participant_consent_status: participantConsent,
          participant_transparency_plan: participantTransparency,
        },
      })
      setSessionId(session.id)
      setPreflight(await conversationApi.preflight(session.id))
      await detail.reload()
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const resetParticipantEditor = () => {
    setEditingParticipantId('')
    setParticipantName(''); setParticipantRole(''); setParticipantPriority(''); setParticipantConcern('')
    setParticipantPosition(''); setParticipantAuthority(''); setParticipantRelationship('')
  }

  const editParticipant = (participant: ConversationParticipant) => {
    const known = participant.counterparty_state?.known_explicit ?? {}
    setEditingParticipantId(participant.id)
    setParticipantName(participant.display_name || '')
    setParticipantRole(participant.role || '')
    setParticipantPriority(known.priority || '')
    setParticipantConcern(known.concern || '')
    setParticipantPosition(known.stated_position || '')
    setParticipantAuthority(known.decision_authority || '')
    setParticipantRelationship(known.relationship_context || '')
  }

  const addParticipant = async () => {
    if (!participantName.trim() && !participantRole.trim()) return
    setSessionBusy(true); setSessionError('')
    try {
      const body = {
        display_name: participantName.trim(),
        role: participantRole.trim(),
        explicit_priority: participantPriority.trim(),
        explicit_concern: participantConcern.trim(),
        stated_position: participantPosition.trim(),
        decision_authority: participantAuthority.trim(),
        relationship_context: participantRelationship.trim(),
      }
      if (editingParticipantId) await conversationApi.patchParticipant(editingParticipantId, body)
      else await conversationApi.addParticipant(spaceId, body)
      resetParticipantEditor()
      await detail.reload(); await prepare.reload()
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const resetGoalEditor = () => {
    setEditingGoalId('')
    setGoalTitle('')
    setGoalOutcome('')
    setGoalPriority('50')
  }

  const editGoal = (goal: ConversationGoal) => {
    setEditingGoalId(goal.id)
    setGoalTitle(goal.title)
    setGoalOutcome(goal.outcome_definition || '')
    setGoalPriority(String(goal.priority ?? 50))
  }

  const saveGoal = async () => {
    if (!goalTitle.trim()) return
    const parsedPriority = Number.parseInt(goalPriority, 10)
    const priority = Number.isFinite(parsedPriority) ? Math.max(0, Math.min(100, parsedPriority)) : 50
    setSessionBusy(true); setSessionError('')
    try {
      const body = {
        title: goalTitle.trim(),
        outcome_definition: goalOutcome.trim(),
        priority,
      }
      if (editingGoalId) await conversationApi.patchGoal(editingGoalId, body)
      else await conversationApi.addGoal(spaceId, body)
      resetGoalEditor()
      await detail.reload(); await prepare.reload()
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const setGoalStatus = async (goalId: string, status: 'ACTIVE' | 'RESOLVED') => {
    setSessionBusy(true); setSessionError('')
    try {
      await conversationApi.patchGoal(goalId, { status })
      await detail.reload(); await prepare.reload()
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const setArchived = async (archived: boolean) => {
    setSessionBusy(true); setSessionError(''); setLifecycleMessage('')
    try {
      await conversationApi.patchSpace(spaceId, { status: archived ? 'ARCHIVED' : 'ACTIVE' })
      await detail.reload()
      setLifecycleMessage(archived ? '已归档；历史与 provenance 保留。' : '已恢复为 Active。')
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const setRetentionPreset = async (preset: 'MINIMUM' | 'STANDARD') => {
    setSessionBusy(true); setSessionError(''); setLifecycleMessage('')
    try {
      await conversationApi.patchSpace(spaceId, { retention_policy: { preset } })
      await detail.reload(); await retention.reload()
      setLifecycleMessage(`已切换为 ${preset}；这里只更新策略，不会立即删除。`)
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const applyRetention = async () => {
    if (!retention.data) return
    const counts = retention.data.would_delete
    if (!window.confirm(`按当前策略清理本地数据？将删除 transcript ${counts.transcript_segments}、guidance ${counts.guidance_events}、draft ${counts.draft_actions}；已确认事项与 provenance 不删除。`)) return
    setSessionBusy(true); setSessionError(''); setLifecycleMessage('')
    try {
      const result = await conversationApi.applyRetention(spaceId, true)
      setLifecycleMessage(`已清理：transcript ${result.deleted.transcript_segments ?? 0} · guidance ${result.deleted.guidance_events ?? 0} · draft ${result.deleted.draft_actions ?? 0}`)
      await retention.reload()
    } catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const removeSession = async (id: string) => {
    if (!window.confirm('删除这场会话？如果其中有已确认事项，会先保存 provenance tombstone；该事项将不再参与后续 Recall。')) return
    setSessionBusy(true); setSessionError(''); setLifecycleMessage('')
    const target = space.sessions.find((item) => item.id === id)
    try {
      const result = await conversationApi.deleteSession(id, 'TOMBSTONE')
      let privacyNote = ''
      if (target?.status === 'ACTIVE' && target.policy?.share_privacy === 'PRIVATE_OVERLAY') {
        try { await restoreConversationSharePrivacy(id) }
        catch { privacyNote = '；但无法确认 Share Privacy 已恢复，请在设置/托盘检查' }
      }
      setLifecycleMessage(`已删除会话；保留 ${result.provenance_tombstones} 条 provenance tombstone，并移除 ${result.removed_open_thread_projections ?? 0} 条派生 Open Thread projection${privacyNote}。`)
      setContinueData(null)
      await detail.reload(); await prepare.reload(); await retention.reload()
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
    if (!window.confirm('彻底删除这个对话空间？这是 complete erase：Session、confirmed/candidate items、Session Packs、Guidance、Drafts 与 provenance tombstones 都会一起删除，无法再用于 Recall。若只是暂时不用，请选择“归档”。Interview 数据不受影响。')) return
    setSessionBusy(true); setSessionError('')
    const privateActiveIds = space.sessions
      .filter((item) => item.status === 'ACTIVE' && item.policy?.share_privacy === 'PRIVATE_OVERLAY')
      .map((item) => item.id)
    try {
      await conversationApi.deleteSpace(spaceId, true)
      for (const id of privateActiveIds) {
        try { await restoreConversationSharePrivacy(id) } catch { /* fail safer: protection may remain enabled */ }
      }
      navigate(paths.conversationSpaces())
    }
    catch (e) { setSessionError(e instanceof Error ? e.message : String(e)); setSessionBusy(false) }
  }

  const makeFollowupDraft = async (targetSessionId: string) => {
    setSessionBusy(true); setSessionError('')
    try { setDraft(await conversationApi.followupDraft(targetSessionId)) }
    catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const makeDerivedDraft = async (targetSessionId: string, kind: 'CREATE_TASK_DRAFT' | 'CREATE_ISSUE_DRAFT' | 'UPDATE_DECISION_LOG_DRAFT') => {
    setSessionBusy(true); setSessionError('')
    try { setDraft(await conversationApi.derivedDraft(targetSessionId, kind)) }
    catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const reviewDraft = async (action: 'APPROVE' | 'DISMISS') => {
    if (!draft) return
    setSessionBusy(true); setSessionError('')
    try { setDraft(await conversationApi.reviewDraftAction(draft.id, action)) }
    catch (e) { setSessionError(e instanceof Error ? e.message : String(e)) }
    finally { setSessionBusy(false) }
  }

  const start = async () => {
    if (!sessionId || !preflight) return
    setSessionBusy(true); setSessionError('')
    const requested = preflight.policy.share_privacy
    let privacyActivated = false
    try {
      let proof = ''
      if (requested === 'PRIVATE_OVERLAY') {
        const runtime = await activateConversationSharePrivacy(sessionId, 'PRIVATE_OVERLAY')
        proof = runtime.proof
        privacyActivated = runtime.protected
      }
      await conversationApi.start(sessionId, { share_privacy_runtime_proof: proof })
      navigate(paths.conversationLive(sessionId))
    } catch (e) {
      if (privacyActivated) {
        try { await restoreConversationSharePrivacy(sessionId) } catch { /* fail safer: protection may remain enabled */ }
      }
      setSessionError(e instanceof Error ? e.message : String(e))
    } finally { setSessionBusy(false) }
  }

  return (
    <Page wide testId="conversation-space">
      <button type="button" onClick={() => navigate(paths.conversationSpaces())} className="mb-3 inline-flex items-center gap-1 text-xs text-text-muted hover:text-text-primary"><ArrowLeft className="h-3.5 w-3.5" /> 对话空间</button>
      <PageHeader eyebrow={space.profile} title={space.title} subtitle={space.description || space.default_goal || '持续保留 Decision、Commitment 与 Open Question。'}
        actions={<>
          <SecondaryButton onClick={exportSpace} disabled={sessionBusy} icon={<Download className="h-3.5 w-3.5" />}>分类导出</SecondaryButton>
          <SecondaryButton onClick={() => setArchived(space.status !== 'ARCHIVED')} disabled={sessionBusy}
            icon={space.status === 'ARCHIVED' ? <RotateCcw className="h-3.5 w-3.5" /> : <Archive className="h-3.5 w-3.5" />}>
            {space.status === 'ARCHIVED' ? '恢复' : '归档'}
          </SecondaryButton>
          <SecondaryButton onClick={deleteSpace} disabled={sessionBusy} icon={<Trash2 className="h-3.5 w-3.5" />}>删除 Space</SecondaryButton>
          {space.status !== 'ARCHIVED' ? <PrimaryButton onClick={() => navigate(paths.conversationSpace(spaceId, 'prepare'))} icon={<Play className="h-3.5 w-3.5" />}>准备 / 开始</PrimaryButton> : null}
        </>} />
      <Tabs tabs={tabs} value={tab} label="对话空间" onChange={(v) => navigate(paths.conversationSpace(spaceId, v))} />
      {lifecycleMessage ? <p role="status" className="mt-3 rounded-xl bg-bg-secondary/50 px-3 py-2 text-xs text-text-secondary">{lifecycleMessage}</p> : null}

      {tab === 'overview' ? (
        <div className="pt-3">
          <Section title="Next Focus">
            {prepare.data?.open_questions[0] ? <p className="text-sm text-text-primary">{prepare.data.open_questions[0].title}</p> :
              prepare.data?.open_commitments[0] ? <p className="text-sm text-text-primary">{prepare.data.open_commitments[0].title}</p> :
              <p className="text-xs text-text-muted">{space.default_goal || '当前没有开放事项。'}</p>}
          </Section>
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Next Session">
              {space.next_session ? <div><div className="text-sm text-text-primary">{space.next_session.title}</div><div className="mt-1 text-[11px] text-text-muted">{space.next_session.scheduled_at ? new Date(space.next_session.scheduled_at * 1000).toLocaleString() : '未排期'} · {space.next_session.assistance_mode}</div></div> : <p className="text-xs text-text-muted">暂无已排期的下一场。</p>}
            </Section>
            <Section title="Recent Decisions">
              {space.recent_decisions?.length ? <div className="space-y-1">{space.recent_decisions.map((d) => <div key={d.id} className="text-xs text-text-primary">• {d.title}</div>)}</div> : <p className="text-xs text-text-muted">暂无已确认 Decision。</p>}
            </Section>
          </div>
          {space.last_session_delta ? <Section title="Last Session Delta">
            <p className="text-xs text-text-secondary">{space.last_session_delta.title} · {space.last_session_delta.what_changed.length} changes · {space.last_session_delta.pins.length} pins · {space.last_session_delta.review_required} 待确认</p>
            {space.last_session_delta.what_changed.slice(0, 3).map((item) => <div key={item.id} className="mt-1 text-xs text-text-primary">• {item.title} · {item.state}</div>)}
          </Section> : null}
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Open Commitments">{prepare.loading ? <Loading /> : prepare.data?.open_commitments.length ? <div className="space-y-2">{prepare.data.open_commitments.map((x) => <ItemRow key={x.id} item={x} onChanged={() => { void detail.reload(); void prepare.reload() }} />)}</div> : <p className="text-xs text-text-muted">暂无。</p>}</Section>
            <Section title="Open Questions">{prepare.loading ? <Loading /> : prepare.data?.open_questions.length ? <div className="space-y-2">{prepare.data.open_questions.map((x) => <ItemRow key={x.id} item={x} onChanged={() => { void detail.reload(); void prepare.reload() }} />)}</div> : <p className="text-xs text-text-muted">暂无。</p>}</Section>
            <Section title="Open Threads">{prepare.loading ? <Loading /> : prepare.data?.open_threads?.length ? <div className="space-y-2">{prepare.data.open_threads.map((thread) => <div key={thread.id} className="rounded-xl border border-bg-tertiary/70 px-3 py-2"><div className="flex flex-wrap items-start justify-between gap-2"><div><div className="flex items-center gap-2"><StatusBadge tone="warn">{thread.kind}</StatusBadge><span className="text-xs text-text-primary">{thread.text}</span></div><div className="mt-1 text-[10px] text-text-muted">reviewed longitudinal thread · source refs {thread.source_refs.length}{thread.owner_id ? ` · owner ${thread.owner_id}` : ''}</div></div><SecondaryButton disabled={sessionBusy} onClick={() => resolveThread(thread.id)}>标记已解决</SecondaryButton></div></div>)}</div> : <p className="text-xs text-text-muted">暂无已确认的跨场未解决 thread。</p>}</Section>
          </div>
          <Section title="参与者 / Counterparty State（只记录明确信息）">
            {space.participants.length ? <div className="space-y-2">{space.participants.map((p) => {
              const known = p.counterparty_state?.known_explicit ?? {}
              return <div key={p.id} className="rounded-xl border border-bg-tertiary/70 px-3 py-2">
                <div className="flex items-center justify-between gap-2"><div className="text-xs font-medium text-text-primary">{p.display_name || '未命名'}{p.role ? ` · ${p.role}` : ''}</div><SecondaryButton disabled={sessionBusy} onClick={() => editParticipant(p)}>修正</SecondaryButton></div>
                <div className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-text-muted">Known / Explicit · confidence {Math.round((p.counterparty_state?.confidence ?? 0) * 100)}%</div>
                {known.priority ? <div className="mt-1 text-[11px] text-text-muted">明确优先级：{known.priority}</div> : null}
                {known.concern ? <div className="mt-1 text-[11px] text-text-muted">明确关注：{known.concern}</div> : null}
                {known.stated_position ? <div className="mt-1 text-[11px] text-text-muted">明确立场：{known.stated_position}</div> : null}
                {known.decision_authority ? <div className="mt-1 text-[11px] text-text-muted">明确决策权限：{known.decision_authority}</div> : null}
                {known.relationship_context ? <div className="mt-1 text-[11px] text-text-muted">关系上下文：{known.relationship_context}</div> : null}
                <div className="mt-2 text-[10px] text-text-muted">Inferred / Temporary：{p.counterparty_state?.temporary_inferences?.length ? '仅本场临时存在' : '无'} · Unknown：{p.counterparty_state?.unknown?.length ?? 0}</div>
              </div>
            })}</div> : <p className="text-xs text-text-muted">还没有明确参与者；系统不会凭声音自动建立长期身份，也不会推断情绪、人格或隐藏意图。</p>}
            <div className="mt-3 grid gap-2 sm:grid-cols-2"><input className={inputCls} value={participantName} onChange={(e) => setParticipantName(e.target.value)} placeholder="姓名 / 昵称（可选）" /><input className={inputCls} value={participantRole} onChange={(e) => setParticipantRole(e.target.value)} placeholder="明确角色，例如 Backend / CTO" /><input className={inputCls} value={participantPriority} onChange={(e) => setParticipantPriority(e.target.value)} placeholder="对方明确说过的优先级（可选）" /><input className={inputCls} value={participantConcern} onChange={(e) => setParticipantConcern(e.target.value)} placeholder="对方明确表达的 concern（可选）" /><input className={inputCls} value={participantPosition} onChange={(e) => setParticipantPosition(e.target.value)} placeholder="对方明确立场，例如先灰度再全量" /><input className={inputCls} value={participantAuthority} onChange={(e) => setParticipantAuthority(e.target.value)} placeholder="明确决策权限，例如架构方案批准人" /><input className={inputCls} value={participantRelationship} onChange={(e) => setParticipantRelationship(e.target.value)} placeholder="关系上下文，例如客户技术负责人 / 跨组协作者" /></div>
            <div className="mt-2 flex gap-2"><SecondaryButton onClick={addParticipant} disabled={sessionBusy || (!participantName.trim() && !participantRole.trim())} icon={<Plus className="h-3.5 w-3.5" />}>{editingParticipantId ? '保存修正' : '添加明确信息'}</SecondaryButton>{editingParticipantId ? <SecondaryButton disabled={sessionBusy} onClick={resetParticipantEditor}>取消</SecondaryButton> : null}</div>
          </Section>
          <Section title="Conversation Goals">
            <p className="mb-3 text-[11px] text-text-muted">Goal 表是长期目标真值；最高优先级的 ACTIVE Goal 会成为 Space 的主目标投影，并自动进入后续 Session。已开始的 Session Pack 不会被后续编辑重写。</p>
            {space.goals.length ? <div className="space-y-2">{space.goals.map((g) => <div key={g.id} className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-bg-tertiary/70 px-3 py-2">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2"><div className="text-xs font-medium text-text-primary">{g.title}</div><StatusBadge tone={g.status === 'ACTIVE' ? 'ok' : 'muted'}>{g.status}</StatusBadge><StatusBadge tone="muted">P{g.priority}</StatusBadge></div>
                {g.outcome_definition ? <div className="mt-1 text-[11px] text-text-muted">达成定义 · {g.outcome_definition}</div> : <div className="mt-1 text-[11px] text-text-muted">尚未填写达成定义。</div>}
                {g.status === 'ACTIVE' && g.title === space.default_goal ? <div className="mt-1 text-[10px] font-semibold text-status-direct">PRIMARY ACTIVE GOAL</div> : null}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SecondaryButton disabled={sessionBusy} onClick={() => editGoal(g)}>编辑</SecondaryButton>
                <SecondaryButton disabled={sessionBusy} onClick={() => setGoalStatus(g.id, g.status === 'ACTIVE' ? 'RESOLVED' : 'ACTIVE')}>{g.status === 'ACTIVE' ? '完成目标' : '重新打开'}</SecondaryButton>
              </div>
            </div>)}</div> : <p className="text-xs text-text-muted">可把本次需要形成 Decision / 明确 owner 等目标写在这里；ACTIVE Goal 会自动进入下一场 Session Pack。</p>}
            <div className="mt-3 rounded-xl bg-bg-secondary/35 p-3">
              <div className="grid gap-2 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1.5fr)_110px]">
                <Field label="目标"><input className={inputCls} value={goalTitle} onChange={(e) => setGoalTitle(e.target.value)} placeholder="例如：形成 conflict merge strategy 决策" /></Field>
                <Field label="达成定义"><input className={inputCls} value={goalOutcome} onChange={(e) => setGoalOutcome(e.target.value)} placeholder="例如：方案、owner 与 rollout 条件均明确" /></Field>
                <Field label="优先级 0–100"><input aria-label="Goal 优先级" type="number" min={0} max={100} className={inputCls} value={goalPriority} onChange={(e) => setGoalPriority(e.target.value)} /></Field>
              </div>
              <div className="mt-2 flex gap-2">
                <SecondaryButton onClick={saveGoal} disabled={sessionBusy || !goalTitle.trim()} icon={<Plus className="h-3.5 w-3.5" />}>{editingGoalId ? '保存 Goal' : '添加 Goal'}</SecondaryButton>
                {editingGoalId ? <SecondaryButton disabled={sessionBusy} onClick={resetGoalEditor}>取消</SecondaryButton> : null}
              </div>
            </div>
          </Section>
          <Section title="数据保留与删除">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge tone="info">{String(space.retention_policy?.preset ?? 'STANDARD')}</StatusBadge>
              <SecondaryButton disabled={sessionBusy} onClick={() => setRetentionPreset('MINIMUM')}>Minimum</SecondaryButton>
              <SecondaryButton disabled={sessionBusy} onClick={() => setRetentionPreset('STANDARD')}>Standard</SecondaryButton>
            </div>
            {retention.loading ? <div className="mt-2"><Loading /></div> : retention.data ? <div className="mt-3 rounded-xl bg-bg-secondary/40 p-3">
              <p className="text-xs text-text-primary">当前策略若现在执行：transcript {retention.data.would_delete.transcript_segments} · guidance {retention.data.would_delete.guidance_events} · draft {retention.data.would_delete.draft_actions}</p>
              <p className="mt-1 text-[11px] text-text-muted">已确认事项、Session Pack 与 provenance tombstone 始终保留；原始音频当前默认不长期保存。</p>
              <div className="mt-3"><SecondaryButton disabled={sessionBusy || !retention.data.destructive} onClick={applyRetention}>预览后执行本地清理</SecondaryButton></div>
            </div> : null}
          </Section>
        </div>
      ) : null}

      {tab === 'prepare' ? (
        <div className="pt-3">
          {prepare.error ? <ErrorState message={prepare.error} onRetry={prepare.reload} /> : null}
          <Section title="Brief">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-xl bg-bg-secondary/40 p-3"><div className="text-[11px] text-text-muted">本次长期目标</div><div className="mt-1 text-sm text-text-primary">{space.default_goal || '未设置'}</div></div>
              <div className="rounded-xl bg-bg-secondary/40 p-3"><div className="text-[11px] text-text-muted">未解决事项</div><div className="mt-1 text-sm text-text-primary">{prepare.data?.brief?.unresolved_count ?? 0}</div></div>
              <div className="rounded-xl bg-bg-secondary/40 p-3"><div className="text-[11px] text-text-muted">已知参与者</div><div className="mt-1 text-sm text-text-primary">{prepare.data?.brief?.known_participants ?? 0}</div></div>
            </div>
            {prepare.data?.agenda?.length ? <div className="mt-3 rounded-xl border border-bg-tertiary/70 p-3"><div className="text-xs font-semibold text-text-secondary">Agenda</div><div className="mt-2 space-y-1">{(prepare.data.agenda ?? []).map((item) => <div key={item} className="text-xs text-text-primary">• {item}</div>)}</div></div> : null}
            {prepare.data?.expected_questions?.length ? <div className="mt-3 rounded-xl border border-bg-tertiary/70 p-3"><div className="text-xs font-semibold text-text-secondary">Expected Questions</div><div className="mt-2 space-y-1">{(prepare.data.expected_questions ?? []).map((q) => <div key={q} className="text-xs text-text-primary">• {q}</div>)}</div></div> : null}
            {prepare.data?.contribution_candidates?.length ? <div className="mt-3 rounded-xl border border-bg-tertiary/70 p-3"><div className="text-xs font-semibold text-text-secondary">Precomputed Contribution Candidates</div><div className="mt-2 space-y-1">{(prepare.data.contribution_candidates ?? []).map((x) => <div key={x.text} className="text-xs text-text-primary">• {x.text}</div>)}</div><p className="mt-2 text-[11px] text-text-muted">这里只是候选；Live 仍必须经过 provenance、novelty 与 interruption arbitration。</p></div> : null}
            {prepare.data?.open_threads?.length ? <div className="mt-3 rounded-xl border border-bg-tertiary/70 p-3"><div className="text-xs font-semibold text-text-secondary">Open Threads · 已确认</div><div className="mt-2 space-y-1">{prepare.data.open_threads.slice(0, 6).map((thread) => <div key={thread.id} className="text-xs text-text-primary">• {thread.kind} · {thread.text}</div>)}</div></div> : null}
          </Section>
          {prepare.data?.profile_playbook ? <Section title={`${prepare.data.profile_playbook.profile} · Profile Playbook`}>
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-xl bg-bg-secondary/40 p-3">
                <div className="text-[11px] font-semibold text-text-secondary">Success Conditions</div>
                <div className="mt-2 space-y-1">{prepare.data.profile_playbook.success_conditions.map((item) => <div key={item} className="text-xs text-text-primary">• {item}</div>)}</div>
              </div>
              <div className="rounded-xl bg-bg-secondary/40 p-3">
                <div className="text-[11px] font-semibold text-text-secondary">Prepare Prompts</div>
                <div className="mt-2 space-y-1">{prepare.data.profile_playbook.prepare_prompts.map((item) => <div key={item} className="text-xs text-text-primary">• {item}</div>)}</div>
              </div>
            </div>
            <div className="mt-3 rounded-xl border border-bg-tertiary/70 p-3">
              <div className="text-[11px] font-semibold text-text-secondary">Closing Objective</div>
              <p className="mt-1 text-xs text-text-primary">{prepare.data.profile_playbook.closing_objective}</p>
              <div className="mt-2 text-[11px] text-text-muted">Priority truth · {prepare.data.profile_playbook.priority_truth_types.join(' · ')}</div>
              <div className="mt-2 space-y-1">{prepare.data.profile_playbook.boundaries.map((item) => <div key={item} className="text-[11px] text-status-inferred">边界 · {item}</div>)}</div>
            </div>
            <p className="mt-2 text-[11px] text-text-muted">Playbook 会随 Session Pack 冻结；它是本 Profile 的工作框架，不是“会议成功评分”。</p>
          </Section> : null}
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
            <div className="mb-3 grid gap-3 md:grid-cols-2">
              <Field label="本场标题"><input className={inputCls} value={sessionTitle} onChange={(e) => setSessionTitle(e.target.value)} placeholder={space.title} /></Field>
              <Field label="人工排期（可选）"><input type="datetime-local" className={inputCls} value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} /></Field>
            </div>
            <p className="mb-3 text-[11px] text-text-muted">没有 Calendar connector 也可以人工排期；有时间的 UPCOMING Session 会进入 Home / Room 的 Next Session。</p>
            <div className="grid gap-3 md:grid-cols-3">
              <Field label="记录方式"><select className={inputCls} value={capture} onChange={(e) => setCapture(e.target.value as CaptureMode)}><option value="NOTES_ONLY">仅结构化笔记</option><option value="TRANSCRIPT">转写</option><option value="NO_CAPTURE">不记录</option></select></Field>
              <Field label="处理方式"><select className={inputCls} value={processing} onChange={(e) => setProcessing(e.target.value as ProcessingMode)}><option value="LOCAL">Local</option><option value="CLOUD">Cloud allowed</option><option value="OFF">Off（TRANSCRIPT / AI 会被阻止）</option></select></Field>
              <Field label="帮助方式"><select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value as AssistanceMode)}><option value="QUIET">Quiet</option><option value="BALANCED">Balanced</option><option value="ACTIVE">Active</option><option value="PRESENTATION">Presentation</option><option value="ONE_ON_ONE">1:1</option></select></Field>
              <Field label="屏幕上下文"><select className={inputCls} value={screenContext} onChange={(e) => setScreenContext(e.target.value as typeof screenContext)}><option value="OFF">Off</option><option value="MANUAL">Manual · 每次由我主动抓取</option><option value="AUTO">Auto · Live 中再次显式启动 / 可 Off the record</option></select></Field>
              <Field label="AI Assistance"><select className={inputCls} value={aiPolicy} onChange={(e) => setAiPolicy(e.target.value as typeof aiPolicy)}><option value="AI_FORBIDDEN">Forbidden · AI 全关闭</option><option value="AI_LIMITED">Limited · 仅用户主动调用</option><option value="AI_ALLOWED">Allowed · 允许自动辅助</option><option value="AI_EXPECTED">Expected · 用户报告本场预期自动辅助</option></select></Field>
              <Field label="Human Assistance"><select className={inputCls} value={humanPolicy} onChange={(e) => setHumanPolicy(e.target.value as typeof humanPolicy)}><option value="HUMAN_FORBIDDEN">Forbidden</option><option value="HUMAN_PRACTICE_ONLY">Practice only</option><option value="HUMAN_ALLOWED">Allowed（runtime 未接线，会阻止开始）</option></select></Field>
              <Field label="屏幕共享保护"><select className={inputCls} value={sharePrivacy} onChange={(e) => setSharePrivacy(e.target.value as typeof sharePrivacy)}><option value="OFF">Off</option><option value="PRIVATE_OVERLAY">Private overlay（桌面开始时验证）</option></select></Field>
              <Field label="外部写回"><select className={inputCls} value={externalWriteback} onChange={(e) => setExternalWriteback(e.target.value as typeof externalWriteback)}><option value="REVIEW_REQUIRED">只生成草稿，必须确认</option><option value="OFF">完全关闭</option></select></Field>
              <Field label="参与者同意状态（仅用户报告）"><select className={inputCls} value={participantConsent} onChange={(e) => setParticipantConsent(e.target.value as typeof participantConsent)}><option value="NOT_RECORDED">未记录 / 未确认</option><option value="USER_REPORTS_ALLOWED">用户报告当前场景允许</option><option value="USER_REPORTS_CONSENTED">用户报告已取得所需参与者同意</option><option value="NOT_APPLICABLE">不适用</option></select></Field>
              <Field label="透明告知计划（仅用户报告）"><select className={inputCls} value={participantTransparency} onChange={(e) => setParticipantTransparency(e.target.value as typeof participantTransparency)}><option value="NOT_RECORDED">尚未记录</option><option value="USER_WILL_NOTIFY_VERBALLY">我会口头告知</option><option value="USER_WILL_NOTIFY_IN_CHAT">我会在会议聊天中告知</option><option value="USER_REPORTS_ALREADY_NOTIFIED">我报告已完成告知</option><option value="NOT_APPLICABLE">不适用</option></select></Field>
              <div className="rounded-xl border border-bg-tertiary/70 bg-bg-secondary/25 p-3 text-[11px] text-text-muted">Speaker biometric identity、emotion/sentiment profiling、hidden-intent claims 在 v2 中固定为 OFF，不能由会话设置放开。</div>
            </div>
            <label className="mt-4 flex items-start gap-2 text-xs text-text-secondary"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5" /><span>我已确认当前场景允许我使用所选择的记录/转写方式。这个勾选不代表其他参与者已经同意，也不代表成竹已自动通知他们；上方“透明告知计划”只记录我的计划/报告。</span></label>
            <div className="mt-4 flex gap-2"><PrimaryButton disabled={sessionBusy} onClick={makePreflight} icon={<ShieldCheck className="h-3.5 w-3.5" />}>{sessionBusy ? '检查中…' : '生成本场并检查'}</PrimaryButton>{preflight && !preflight.blockers.length ? <PrimaryButton disabled={sessionBusy} onClick={start}>开始会话</PrimaryButton> : null}</div>
            {sessionError ? <div className="mt-3"><ErrorState message={sessionError} /></div> : null}
            {preflight ? <div className="mt-4 rounded-2xl border border-bg-tertiary p-3">
              <div className="space-y-1">{preflight.items.map((x) => <div key={x.key} className="flex items-center justify-between gap-3 text-xs"><span className="text-text-muted">{x.label}</span><span className={x.ok ? 'text-status-direct' : 'text-status-risk'}>{x.ok ? '✓ ' : '! '}{String(x.value)}</span></div>)}</div>
              <div className="mt-3 rounded-xl bg-bg-secondary/35 p-3 text-[11px] text-text-muted">
                <div className="font-semibold text-text-secondary">Resolved AI Behavior</div>
                <div className="mt-2 grid gap-1 sm:grid-cols-2">
                  <span>Manual Ask · {preflight.resolved_ai_behavior.manual_ask ? 'ON' : 'OFF'}</span>
                  <span>Manual Guidance · {preflight.resolved_ai_behavior.manual_guidance ? 'ON' : 'OFF'}</span>
                  <span>Auto transcript Guidance · {preflight.resolved_ai_behavior.automatic_transcript_guidance ? 'ON' : 'OFF'}</span>
                  <span>Auto candidate extraction · {preflight.resolved_ai_behavior.automatic_candidate_extraction ? 'ON' : 'OFF'}</span>
                </div>
                <p className="mt-2">{preflight.resolved_ai_behavior.expected_by_user_report ? 'Expected 只记录“用户报告本场预期 AI 辅助”；当前 Beta engine 与 Allowed 相同。' : '行为由本场 policy 显式解析，不用标签猜测。'}</p>
              </div>
              <div className="mt-3 rounded-xl bg-bg-secondary/35 p-3 text-[11px] text-text-muted">
                <div className="font-semibold text-text-secondary">Resolved Data Path</div>
                <div className="mt-2 grid gap-1 sm:grid-cols-2">
                  <span>Capture · {preflight.processing_runtime.data_path.capture}</span>
                  <span>STT · {preflight.processing_runtime.data_path.stt} ({preflight.processing_runtime.configured_stt_provider})</span>
                  <span>Inference · {preflight.processing_runtime.data_path.inference}</span>
                  <span>Retention · {preflight.processing_runtime.data_path.retention}</span>
                  <span>Write-back · {preflight.processing_runtime.data_path.writeback}</span>
                  <span>Audio retention · {preflight.processing_runtime.data_path.audio_retention}</span>
                  <span>Screen · {['MANUAL', 'AUTO'].includes(preflight.screen_runtime.mode) ? `${preflight.screen_runtime.mode} / ${preflight.screen_runtime.route} / ${preflight.screen_runtime.model_id || preflight.screen_runtime.model_name || 'vision'}` : preflight.screen_runtime.mode}</span>
                  <span>Share Privacy · {preflight.share_privacy_runtime.requested === 'PRIVATE_OVERLAY' ? 'VERIFY_AT_START / Electron content protection' : 'OFF'}</span>
                  <span>Raw screen image · {preflight.screen_runtime.raw_image_persisted ? 'PERSISTED' : 'NOT STORED'}</span>
                </div>
                <p className="mt-2">“Local”不会把 capture / STT / inference / retention / write-back / vision 混成一个标签；任何一段与 policy 不一致都会 fail-closed。MANUAL 每次由你主动抓取；AUTO 即使通过 Preflight，也必须在 Live 再次显式启动并持续显示 ACTIVE / OFF THE RECORD 状态。两种模式都不把原图写入 product.db。</p>
              </div>
              {preflight.blockers.map((x) => <div key={x.key} className="mt-2 text-xs text-status-risk">{x.message}</div>)}
              {preflight.warnings.map((x, index) => <div key={`${x.key}:${index}`} className="mt-2 text-xs text-status-inferred">提醒 · {x.message}</div>)}
              <div className="mt-3 rounded-xl bg-bg-secondary/40 p-3">
                <div className="text-xs font-semibold text-text-secondary">Session Pack Preview</div>
                <div className="mt-2 grid gap-1 text-[11px] text-text-muted sm:grid-cols-2">
                  <span>Goals {preflight.pack_preview.goal_ids.length}</span>
                  <span>Ready Sources {preflight.pack_preview.sources.length}/{preflight.pack_preview.selected_source_ids.length}</span>
                  <span>Quick Notes {preflight.pack_preview.quick_notes.length}/{preflight.pack_preview.selected_quick_note_ids.length}</span>
                  <span>Participants {preflight.pack_preview.participants_count}</span>
                  <span>Confirmed items {preflight.pack_preview.confirmed_items_count}</span>
                  <span>Expression {Object.keys(preflight.pack_preview.expression_profile ?? {}).length ? '已冻结' : '默认'}</span>
                  <span>AI {preflight.pack_preview.policy.ai_assistance}</span>
                  <span>STT {preflight.pack_preview.processing_runtime.data_path.stt}</span>
                  <span>Inference {preflight.pack_preview.processing_runtime.data_path.inference}</span>
                  <span>Write-back {preflight.pack_preview.processing_runtime.data_path.writeback}</span>
                  <span>Screen {preflight.pack_preview.screen_runtime.mode === 'MANUAL' ? `${preflight.pack_preview.screen_runtime.route} · ${preflight.pack_preview.screen_runtime.fingerprint.slice(0, 8)}` : preflight.pack_preview.screen_runtime.mode}</span>
                  <span>Share Privacy {preflight.pack_preview.share_privacy_runtime.requested === 'PRIVATE_OVERLAY' ? 'verify at start' : 'off'}</span>
                  <span>Raw image {preflight.pack_preview.screen_runtime.raw_image_persisted ? 'stored' : 'not stored'}</span>
                </div>
                {preflight.pack_preview.sources.length ? <div className="mt-3">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Frozen sources</div>
                  <div className="mt-1 space-y-1">{preflight.pack_preview.sources.map((source) => <div key={source.version_id || source.material_id} className="flex flex-wrap items-center gap-1 text-[11px] text-text-secondary"><span>• {source.title}</span><span className="text-text-muted">{source.kind} · {source.usage} · v {source.version_id.slice(0, 8)} · {source.is_personal_evidence ? 'personal evidence' : 'reference'}</span></div>)}</div>
                </div> : null}
                {preflight.pack_preview.quick_notes.length ? <div className="mt-3">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Frozen Quick Notes · 非证据</div>
                  <div className="mt-1 space-y-1">{preflight.pack_preview.quick_notes.map((note) => <div key={note.id} className="text-[11px] text-text-secondary">• {note.title || note.id}</div>)}</div>
                </div> : null}
                {preflight.pack_preview.skipped_sources.length ? <div className="mt-3 text-[11px] text-status-inferred">Skipped Sources · {preflight.pack_preview.skipped_sources.map((x) => x.title || x.id).join(' · ')}</div> : null}
                <p className="mt-2 text-[11px] text-text-muted">点击开始后，这一组上下文、我的表达与 policy 会被冻结进 Session Pack；后续资料或表达偏好变化不会静默改写本场。</p>
              </div>
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
                <div className="flex gap-2">{s.status !== 'ENDED' ? <SecondaryButton onClick={() => navigate(paths.conversationLive(s.id))}>进入</SecondaryButton> : <><span data-testid={`conversation-continue-${s.id}`}><SecondaryButton onClick={async () => setContinueData(await conversationApi.continue(s.id))}>Continue</SecondaryButton></span><SecondaryButton disabled={sessionBusy} onClick={() => removeSession(s.id)} icon={<Trash2 className="h-3.5 w-3.5" />}>删除</SecondaryButton></>}</div>
              </div>
            </div>
          ))}</div> : <EmptyState title="还没有会话" body="从“准备”创建本场 Preflight。" />}
          {continueData ? <div data-testid="conversation-continue-panel" className="mt-4 rounded-2xl border border-accent-blue/25 bg-accent-blue/5 p-4">
            <h3 className="text-sm font-semibold text-text-primary">这场之后</h3>
            <p className="mt-1 text-xs text-text-muted">Decision {continueData.decisions.length} · Commitment {continueData.commitments.length} · Open Question {continueData.open_questions.length} · 待确认 {continueData.review_required}</p>
            {continueData.profile_outcome ? <div className="mt-3 rounded-xl border border-bg-tertiary/70 bg-bg-primary/45 p-3">
              <div className="text-xs font-semibold text-text-secondary">{continueData.profile_outcome.profile} · Reviewed Outcome Evidence</div>
              <p className="mt-1 text-[11px] text-text-muted">{continueData.profile_outcome.closing_objective}</p>
              <div className="mt-2 flex flex-wrap gap-2">{continueData.profile_outcome.priority_truth_types.map((kind) => <StatusBadge key={kind} tone={continueData.profile_outcome.reviewed_counts[kind] ? 'ok' : 'muted'}>{kind} {continueData.profile_outcome.reviewed_counts[kind] ?? 0}</StatusBadge>)}</div>
              <p className="mt-2 text-[10px] text-text-muted">{continueData.profile_outcome.interpretation}</p>
            </div> : null}
            {continueData.what_changed?.length ? <div className="mt-3"><div className="text-xs font-semibold text-text-secondary">What changed</div><div className="mt-1 space-y-1">{continueData.what_changed.map((item) => <div key={item.id} className="text-xs text-text-primary">• {item.title} · {item.state}</div>)}</div></div> : null}
            {continueData.pins?.length ? <div className="mt-3"><div className="text-xs font-semibold text-text-secondary">Pins</div><div className="mt-1 space-y-1">{continueData.pins.map((pin) => <div key={pin.id} className="text-xs text-text-primary">• {pin.text || pin.kind}</div>)}</div></div> : null}
            {continueData.next_focus ? <p className="mt-3 text-sm text-text-primary">Next Focus · {continueData.next_focus.title}</p> : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <SecondaryButton disabled={sessionBusy || continueData.session.policy?.external_writeback === 'OFF'} onClick={() => makeFollowupDraft(continueData.session.id)}>Follow-up Draft</SecondaryButton>
              <SecondaryButton disabled={sessionBusy || continueData.session.policy?.external_writeback === 'OFF' || !continueData.commitments.length} onClick={() => makeDerivedDraft(continueData.session.id, 'CREATE_TASK_DRAFT')}>Task Draft</SecondaryButton>
              <SecondaryButton
                disabled={sessionBusy || continueData.session.policy?.external_writeback === 'OFF' || !continueData.open_questions.some((item) => ['USER_CONFIRMED', 'USER_EDITED', 'SOURCE_CONFIRMED'].includes(item.review_status))}
                onClick={() => makeDerivedDraft(continueData.session.id, 'CREATE_ISSUE_DRAFT')}
              >Issue Draft</SecondaryButton>
              <SecondaryButton disabled={sessionBusy || continueData.session.policy?.external_writeback === 'OFF' || !continueData.decisions.length} onClick={() => makeDerivedDraft(continueData.session.id, 'UPDATE_DECISION_LOG_DRAFT')}>Decision Log Draft</SecondaryButton>
            </div>
            {continueData.session.policy?.external_writeback === 'OFF' ? <p className="mt-2 text-[11px] text-text-muted">本场 External Write-back = OFF，因此不会生成 follow-up / task / issue 草稿。</p> : null}
            {draft ? <div className="mt-3 rounded-xl border border-bg-tertiary bg-bg-primary/60 p-3"><div className="flex items-center gap-2"><StatusBadge tone={draft.status === 'APPROVED' ? 'ok' : draft.status === 'DISMISSED' ? 'muted' : 'warn'}>{draft.status}</StatusBadge><span className="text-xs font-semibold text-text-primary">{draft.title}</span></div><pre className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-text-secondary">{draft.content}</pre>{draft.status === 'DRAFT' ? <div className="mt-3 flex gap-2"><SecondaryButton onClick={() => reviewDraft('APPROVE')}>确认草稿</SecondaryButton><SecondaryButton onClick={() => reviewDraft('DISMISS')}>丢弃</SecondaryButton></div> : null}<p className="mt-2 text-[11px] text-text-muted">确认只代表你审核了本地草稿，不代表已发送邮件、创建 task / issue 或写入 decision log。真正的 connector execution 尚未接线。</p></div> : null}
            {continueData.candidates.length ? <div className="mt-4 space-y-2"><div className="text-xs font-semibold text-text-secondary">逐项确认 AI / 会中提取</div>{continueData.candidates.map((item) => <ItemRow key={item.id} item={item} onChanged={async () => { setContinueData(await conversationApi.continue(continueData.session.id)); await detail.reload(); await prepare.reload() }} />)}</div> : <p className="mt-3 text-xs text-status-direct">没有未确认事项。</p>}
          </div> : null}
        </div>
      ) : null}

      {tab === 'decisions' ? (
        <div className="pt-3">
          <Section title="Decision Timeline / Supersession">
            <p className="mb-3 text-[11px] text-text-muted">按时间保留 Proposed / Agreed / Superseded；冲突的新 Decision 通过 supersession 链保留旧事实，不直接删除。</p>
            {space.decisions.length ? <div className="space-y-2">{space.decisions.map((x) => <ItemRow key={x.id} item={x} supersedeOptions={space.decisions.filter((d) => d.state === 'AGREED')} onChanged={() => { void detail.reload(); void prepare.reload() }} />)}</div> : <EmptyState title="还没有 Decision" body="会中抽取默认只是 Proposed；只有有来源且确认后才会升级为 Agreed。" />}
          </Section>
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Related Objections">
              {space.objections?.length ? <div className="space-y-2">{space.objections.map((x) => <ItemRow key={x.id} item={x} onChanged={() => { void detail.reload(); void prepare.reload() }} />)}</div> : <p className="text-xs text-text-muted">暂无已记录 Objection。</p>}
            </Section>
            <Section title="Follow-up Commitments">
              {space.commitments.length ? <div className="space-y-2">{space.commitments.slice(0, 8).map((x) => <ItemRow key={x.id} item={x} onChanged={() => { void detail.reload(); void prepare.reload() }} />)}</div> : <p className="text-xs text-text-muted">暂无 follow-up commitment。</p>}
            </Section>
          </div>
        </div>
      ) : null}
    </Page>
  )
}
