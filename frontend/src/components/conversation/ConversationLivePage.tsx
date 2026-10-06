import { useEffect, useState } from 'react'
import { Mic, PauseCircle, Pin, Play, Square, Volume2 } from 'lucide-react'
import { api } from '@/lib/api'
import { conversationApi } from '@/lib/conversationApi'
import type { AssistanceMode, ConversationAskResult, ConversationCaptureStatus, ConversationContinue, ConversationGuidance, ConversationItemType, ConversationTranscriptSegment } from '@/lib/conversationContracts'
import { navigate, paths } from '@/lib/router'
import { ErrorState, Field, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, StatusBadge, inputCls, useAsync } from '@/components/os/ui'

type AudioDevice = { id: number; name: string; is_loopback?: boolean }
type DevicePayload = { devices?: AudioDevice[] }

export default function ConversationLivePage({ sessionId }: { sessionId: string }) {
  const session = useAsync(() => conversationApi.session(sessionId), [sessionId])
  const liveContext = useAsync(() => conversationApi.sessionContext(sessionId), [sessionId])
  const devices = useAsync(async () => (await api.getDevices()) as DevicePayload, [])
  const [topic, setTopic] = useState('')
  const [question, setQuestion] = useState('')
  const [candidate, setCandidate] = useState('')
  const [criticalRisk, setCriticalRisk] = useState('')
  const [source, setSource] = useState('')
  const [audienceRole, setAudienceRole] = useState('')
  const [audiencePriority, setAudiencePriority] = useState('')
  const [audienceConcern, setAudienceConcern] = useState('')
  const [decisionAuthority, setDecisionAuthority] = useState('')
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
  const [askResult, setAskResult] = useState<ConversationAskResult | null>(null)
  const [capture, setCapture] = useState<ConversationCaptureStatus | null>(null)
  const [segments, setSegments] = useState<ConversationTranscriptSegment[]>([])
  const [primaryDevice, setPrimaryDevice] = useState('')
  const [selfMic, setSelfMic] = useState('')
  const [captureBusy, setCaptureBusy] = useState(false)

  useEffect(() => {
    if (session.data?.assistance_mode) setMode(session.data.assistance_mode)
  }, [session.data?.assistance_mode])

  useEffect(() => {
    const all = devices.data?.devices ?? []
    if (!primaryDevice && all.length) {
      const preferred = all.find((d) => d.is_loopback) ?? all[0]
      setPrimaryDevice(String(preferred.id))
    }
  }, [devices.data, primaryDevice])

  useEffect(() => {
    let alive = true
    const poll = async () => {
      try {
        const [nextCapture, transcript, history] = await Promise.all([
          conversationApi.captureStatus(sessionId),
          conversationApi.transcript(sessionId, 80),
          conversationApi.guidanceHistory(sessionId, 12),
        ])
        if (!alive) return
        setCapture(nextCapture)
        setSegments(transcript.items)
        const latest = history.items.find((x) => x.status === 'SHOWN' && x.user_action !== 'DISMISSED')
        if (latest) setGuidance((current) => current?.id === latest.id ? current : latest)
      } catch {
        // Capture/timeline polling is additive. Manual Conversation Live stays usable
        // even if an older backend does not expose the v2 endpoints yet.
      }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 1200)
    return () => { alive = false; window.clearInterval(timer) }
  }, [sessionId])

  if (session.loading) return <Page><Loading /></Page>
  if (session.error || !session.data) return <Page><ErrorState message={session.error ?? '会话不存在'} onRetry={session.reload} /></Page>
  const s = session.data

  const startCapture = async () => {
    if (!primaryDevice) {
      setError('请选择主音频设备')
      return
    }
    setCaptureBusy(true); setError('')
    try {
      const next = await conversationApi.captureStart(
        sessionId,
        Number(primaryDevice),
        selfMic ? Number(selfMic) : null,
      )
      setCapture(next)
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setCaptureBusy(false) }
  }

  const toggleCapturePause = async () => {
    setCaptureBusy(true); setError('')
    try {
      const next = capture?.paused
        ? await conversationApi.captureResume(sessionId)
        : await conversationApi.capturePause(sessionId)
      setCapture(next)
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setCaptureBusy(false) }
  }

  const stopCapture = async () => {
    setCaptureBusy(true); setError('')
    try { setCapture(await conversationApi.captureStop(sessionId)) }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setCaptureBusy(false) }
  }

  const evaluate = async () => {
    setBusy(true); setError('')
    try {
      const refs = source.trim() ? [{ kind: 'USER_NOTE', excerpt: source.trim(), id: `manual:${sessionId}` }] : []
      const result = await conversationApi.evaluateGuidance(sessionId, {
        current_topic: topic,
        direct_question: question,
        critical_risk: criticalRisk,
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
        audience_role: audienceRole,
        audience_priority: audiencePriority,
        audience_concern: audienceConcern,
        decision_authority: decisionAuthority,
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
    try {
      if (capture?.owns_requested_session) setCapture(await conversationApi.captureStop(sessionId))
      setSummary(await conversationApi.end(sessionId)); await session.reload()
    }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  return (
    <Page wide testId="conversation-live">
      <PageHeader eyebrow="Conversation Beta" title={s.title} subtitle={`${s.status} · ${s.assistance_mode} · ${s.processing_mode} · AI ${s.policy?.ai_assistance ?? 'AI_ALLOWED'} · Human ${s.policy?.human_assistance ?? 'HUMAN_PRACTICE_ONLY'}`}
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
            {s.capture_mode === 'TRANSCRIPT' ? (
              <div className="mt-4 rounded-xl border border-bg-tertiary bg-bg-primary/55 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2"><Mic className="h-3.5 w-3.5 text-accent-blue" /><span className="text-xs font-semibold text-text-primary">真实转写</span>{capture?.owns_requested_session ? <StatusBadge tone="ok">{capture.paused ? 'PAUSED' : 'CAPTURING'}</StatusBadge> : <StatusBadge tone="muted">OFF</StatusBadge>}</div>
                    <p className="mt-1 text-[11px] text-text-muted">只复用 Audio/VAD/STT；不会启动 Interview 自动答题、Fast Cue 或 Interview Review。</p>
                  </div>
                  {capture?.owns_requested_session ? <div className="flex gap-2"><SecondaryButton disabled={captureBusy} onClick={toggleCapturePause} icon={capture.paused ? <Play className="h-3.5 w-3.5" /> : <PauseCircle className="h-3.5 w-3.5" />}>{capture.paused ? '继续' : '暂停'}</SecondaryButton><SecondaryButton disabled={captureBusy} onClick={stopCapture}>停止转写</SecondaryButton></div> : <PrimaryButton disabled={captureBusy || !primaryDevice} onClick={startCapture} icon={<Mic className="h-3.5 w-3.5" />}>{captureBusy ? '启动中…' : '开始转写'}</PrimaryButton>}
                </div>
                {!capture?.owns_requested_session ? <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <Field label="主音频（优先系统/会议音频）"><select className={inputCls} value={primaryDevice} onChange={(e) => setPrimaryDevice(e.target.value)}><option value="">请选择</option>{(devices.data?.devices ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}{d.is_loopback ? ' · loopback' : ''}</option>)}</select></Field>
                  <Field label="我的麦克风（可选）"><select className={inputCls} value={selfMic} onChange={(e) => setSelfMic(e.target.value)}><option value="">不单独采集</option>{(devices.data?.devices ?? []).filter((d) => String(d.id) !== primaryDevice).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
                </div> : null}
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-bg-tertiary px-3 py-2 text-[11px] text-text-muted">本场 Preflight 选择的是 {s.capture_mode}；不会启动音频转写。结构化事项与 Manual Ask 仍可使用。</div>
            )}
            <div className="mt-4 grid gap-3">
              <Field label="当前话题"><input className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="例如：offline migration" /></Field>
              <Field label="对方直接问我的问题（如有）"><input className={inputCls} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="直接问题优先于主动 Opportunity" /></Field>
              <Field label="值得补充的候选内容（如有）"><textarea className={inputCls} rows={3} value={candidate} onChange={(e) => setCandidate(e.target.value)} placeholder="例如：Q4 benchmark 已覆盖 10x data scale" /></Field>
              <Field label="已知关键风险（如有）"><textarea className={inputCls} rows={2} value={criticalRisk} onChange={(e) => setCriticalRisk(e.target.value)} placeholder="仅填写有明确来源、需要优先提醒的事实 / 承诺 / 冲突风险。" /></Field>
              <Field label="来源 / 依据"><textarea className={inputCls} rows={2} value={source} onChange={(e) => setSource(e.target.value)} placeholder="主动 Contribution Opportunity 必须有来源；没有来源会被抑制。" /></Field>
              <div className="rounded-xl border border-bg-tertiary/70 bg-bg-secondary/20 p-3">
                <div className="text-xs font-semibold text-text-secondary">Stakeholder-aware Expression · 只用明确信息</div>
                <p className="mt-1 text-[11px] text-text-muted">这些字段只影响“是否值得说、怎么组织”，不会改写事实，也不会推断情绪、人格或隐藏意图。</p>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <input className={inputCls} value={audienceRole} onChange={(e) => setAudienceRole(e.target.value)} placeholder="对方明确角色，例如 CTO / 客户" />
                  <input className={inputCls} value={decisionAuthority} onChange={(e) => setDecisionAuthority(e.target.value)} placeholder="明确决策权限（可选）" />
                  <input className={inputCls} value={audiencePriority} onChange={(e) => setAudiencePriority(e.target.value)} placeholder="对方明确优先级" />
                  <input className={inputCls} value={audienceConcern} onChange={(e) => setAudienceConcern(e.target.value)} placeholder="对方明确 concern" />
                </div>
              </div>
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

          <div className="rounded-2xl border border-bg-tertiary bg-bg-secondary/20 p-4">
            <div className="flex items-center justify-between gap-2"><h2 className="text-sm font-semibold text-text-primary">Live Transcript</h2><span className="text-[11px] text-text-muted">{segments.length} final segments</span></div>
            {segments.length ? <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">{segments.slice(-20).map((seg) => <div key={seg.id} className="rounded-xl bg-bg-primary/65 px-3 py-2"><div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">{seg.channel === 'SELF_MIC' ? '我的麦克风' : '主音频'} · {seg.provider || 'ASR'}</div><p className="mt-1 text-xs leading-relaxed text-text-primary">{seg.text}</p></div>)}</div> : <p className="mt-3 text-xs text-text-muted">还没有最终转写。开启真实转写后，这里只显示 Conversation 自己的 timeline。</p>}
          </div>
        </div>

        <aside className="space-y-4">
          {liveContext.data ? <div className="rounded-2xl border border-bg-tertiary bg-bg-secondary/20 p-4" data-testid="conversation-session-pulse">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-text-primary">Session Pulse</h2>
                <p className="mt-1 text-[11px] text-text-muted">来自开始时冻结的 Session Pack，不随会中资料替换静默变化。</p>
              </div>
              <StatusBadge tone="muted">PACK {liveContext.data.pack_digest ? liveContext.data.pack_digest.slice(0, 8) : '—'}</StatusBadge>
            </div>
            {liveContext.data.brief.goal ? <div className="mt-3"><div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Goal</div><p className="mt-1 text-xs text-text-primary">{liveContext.data.brief.goal}</p></div> : null}
            {(liveContext.data.brief.agenda?.length ?? 0) > 0 ? <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Agenda</div>
              <div className="mt-1 space-y-1">{liveContext.data.brief.agenda!.slice(0, 5).map((item, index) => <div key={`${index}:${item}`} className="text-[11px] text-text-secondary">{index + 1}. {item}</div>)}</div>
            </div> : null}
            {(liveContext.data.brief.expected_questions?.length ?? 0) > 0 ? <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Expected Questions</div>
              <div className="mt-1 space-y-1">{liveContext.data.brief.expected_questions!.slice(0, 3).map((item) => <div key={item} className="text-[11px] text-text-secondary">• {item}</div>)}</div>
            </div> : null}
            <div className="mt-3 grid grid-cols-2 gap-1 text-[10px] text-text-muted">
              <span>Sources {liveContext.data.sources.length}</span>
              <span>Quick Notes {liveContext.data.quick_notes.length}</span>
              <span>Participants {liveContext.data.participants.length}</span>
              <span>Open {liveContext.data.brief.unresolved_count ?? 0}</span>
            </div>
            <div className="mt-2 text-[10px] text-text-muted">Data path · {liveContext.data.processing_runtime.mode ?? s.processing_mode} / STT {liveContext.data.processing_runtime.configured_stt_provider ?? '—'}</div>
          </div> : null}

          <div className="rounded-2xl border border-bg-tertiary p-4">
            <h2 className="text-sm font-semibold text-text-primary">问成竹 · 本场可追溯上下文</h2>
            <p className="mt-1 text-[11px] text-text-muted">检索开始时冻结的 Ready sources / Quick Notes、已确认历史，以及本场当前 transcript。每条结果标明 authority；观察和笔记不会冒充 confirmed truth。</p>
            <div className="mt-3 space-y-2">
              <textarea className={inputCls} rows={2} value={askText} onChange={(e) => setAskText(e.target.value)} placeholder="例如：之前为什么用 v2？Q4 benchmark 说了什么？刚才是否提到 rollback？" />
              <SecondaryButton disabled={busy || !askText.trim()} onClick={ask}>查本场可用来源</SecondaryButton>
            </div>
            {askResult ? <div className="mt-3 rounded-xl bg-bg-secondary/45 p-3">
              <p className="text-xs text-text-primary">{askResult.answer}</p>
              <p className="mt-1 text-[11px] text-text-muted">{askResult.grounded ? `已找到 ${askResult.matches.length} 条可追溯来源 · ${askResult.truth_confirmed ? '顶部命中为已确认事实' : '顶部命中不是已确认事实'}` : '没有用模型猜测答案'}</p>
              {askResult.matches.length ? <div className="mt-3 space-y-2">{askResult.matches.slice(0, 4).map((match) => (
                <div key={`${match.kind}:${match.id}`} className="rounded-lg border border-bg-tertiary/70 bg-bg-primary/55 px-2.5 py-2">
                  <div className="flex flex-wrap items-center gap-1.5"><StatusBadge tone={match.authority === 'CONFIRMED_TRUTH' ? 'ok' : match.authority === 'PERSONAL_EVIDENCE' ? 'info' : 'muted'}>{match.kind}</StatusBadge><span className="text-[10px] font-semibold text-text-muted">{match.authority}</span></div>
                  <div className="mt-1 text-xs font-medium text-text-primary">{match.title}</div>
                  {match.excerpt ? <div className="mt-1 line-clamp-3 text-[11px] leading-relaxed text-text-muted">{match.excerpt}</div> : null}
                </div>
              ))}</div> : null}
            </div> : null}
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
