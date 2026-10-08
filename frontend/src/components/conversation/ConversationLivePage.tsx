import { useEffect, useRef, useState } from 'react'
import { Camera, Mic, PauseCircle, Pin, Play, Square, Volume2 } from 'lucide-react'
import { api } from '@/lib/api'
import { conversationApi } from '@/lib/conversationApi'
import { activateConversationSharePrivacy, inspectConversationSharePrivacy, restoreConversationSharePrivacy, type ConversationSharePrivacyRuntime } from '@/lib/conversationSharePrivacy'
import { captureViewState, createLivePollGate, latestVisibleGuidance } from './liveViewState'
import type { AssistanceMode, ConversationAskResult, ConversationCaptureStatus, ConversationContinue, ConversationExpressionPlan, ConversationGuidance, ConversationItemType, ConversationScreenAutoStatus, ConversationScreenContext, ConversationTranscriptSegment } from '@/lib/conversationContracts'
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
  const [talkingPoint, setTalkingPoint] = useState('')
  const [deliveryFocus, setDeliveryFocus] = useState('')
  const [criticalRisk, setCriticalRisk] = useState('')
  const [source, setSource] = useState('')
  const [audienceParticipantId, setAudienceParticipantId] = useState('')
  const [audienceRole, setAudienceRole] = useState('')
  const [audiencePriority, setAudiencePriority] = useState('')
  const [audienceConcern, setAudienceConcern] = useState('')
  const [decisionAuthority, setDecisionAuthority] = useState('')
  const [relationshipContext, setRelationshipContext] = useState('')
  const [speaking, setSpeaking] = useState(false)
  const [guidance, setGuidance] = useState<ConversationGuidance | null>(null)
  const [silentPlan, setSilentPlan] = useState<ConversationExpressionPlan | null>(null)
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
  const [captureStatusError, setCaptureStatusError] = useState(false)
  const [segments, setSegments] = useState<ConversationTranscriptSegment[]>([])
  const [primaryDevice, setPrimaryDevice] = useState('')
  const [selfMic, setSelfMic] = useState('')
  const [captureBusy, setCaptureBusy] = useState(false)
  const [screenRegion, setScreenRegion] = useState<'configured' | 'full' | 'left_half' | 'right_half' | 'top_half' | 'bottom_half'>('configured')
  const [screenBusy, setScreenBusy] = useState(false)
  const [screenObservations, setScreenObservations] = useState<ConversationScreenContext[]>([])
  const [screenAuto, setScreenAuto] = useState<ConversationScreenAutoStatus | null>(null)
  const [screenAutoStatusError, setScreenAutoStatusError] = useState(true)
  const [screenAutoInterval, setScreenAutoInterval] = useState('30')
  const [sharePrivacyRuntime, setSharePrivacyRuntime] = useState<ConversationSharePrivacyRuntime | null>(null)
  const [sharePrivacyStatusError, setSharePrivacyStatusError] = useState(false)
  const capturePollGate = useRef(createLivePollGate()).current

  useEffect(() => {
    if (session.data?.assistance_mode) setMode(session.data.assistance_mode)
  }, [session.data?.assistance_mode])

  useEffect(() => {
    let alive = true
    const requested = session.data?.policy?.share_privacy
    const status = session.data?.status
    if (!requested) return () => { alive = false }

    const sync = async () => {
      try {
        let runtime = await inspectConversationSharePrivacy(requested)
        // The Session policy is stronger than tray/settings drift while ACTIVE.
        // If another UI path drops content protection, re-assert it rather than
        // continuing to show a stale "ACTIVE" badge.
        if (requested === 'PRIVATE_OVERLAY' && status === 'ACTIVE' && !runtime.protected) {
          runtime = await activateConversationSharePrivacy(sessionId, 'PRIVATE_OVERLAY')
        }
        if (!alive) return
        setSharePrivacyRuntime(runtime)
        setSharePrivacyStatusError(false)
      } catch {
        if (!alive) return
        setSharePrivacyRuntime(null)
        setSharePrivacyStatusError(true)
      }
    }
    void sync()
    const timer = requested === 'PRIVATE_OVERLAY' && status === 'ACTIVE'
      ? window.setInterval(() => void sync(), 2000)
      : null
    return () => {
      alive = false
      if (timer !== null) window.clearInterval(timer)
    }
  }, [sessionId, session.data?.policy?.share_privacy, session.data?.status])

  useEffect(() => {
    const participants = liveContext.data?.participants ?? []
    if (!audienceParticipantId && participants.length) setAudienceParticipantId(participants[0].id)
  }, [liveContext.data?.participants, audienceParticipantId])

  useEffect(() => {
    if (!audienceParticipantId) return
    const participant = liveContext.data?.participants.find((item) => item.id === audienceParticipantId)
    if (!participant) return
    const known = participant.counterparty_state.known_explicit ?? {}
    setAudienceRole(participant.role || '')
    setAudiencePriority(known.priority || '')
    setAudienceConcern(known.concern || '')
    setDecisionAuthority(known.decision_authority || '')
    setRelationshipContext(known.relationship_context || '')
  }, [audienceParticipantId, liveContext.data?.participants])

  useEffect(() => {
    const all = devices.data?.devices ?? []
    if (!primaryDevice && all.length) {
      const preferred = all.find((d) => d.is_loopback) ?? all[0]
      setPrimaryDevice(String(preferred.id))
    }
  }, [devices.data, primaryDevice])

  useEffect(() => {
    let alive = true
    const mode = liveContext.data?.screen_runtime?.mode
    if (mode !== 'MANUAL' && mode !== 'AUTO') {
      setScreenObservations([])
      setScreenAuto(null)
      setScreenAutoStatusError(false)
      return () => { alive = false }
    }

    const refreshObservations = async () => {
      try {
        const payload = await conversationApi.screenContext(sessionId, 12)
        if (alive) setScreenObservations(payload.items)
      } catch { /* optional observation surface */ }
    }

    void refreshObservations()
    if (mode !== 'AUTO') {
      setScreenAuto(null)
      setScreenAutoStatusError(false)
      return () => { alive = false }
    }

    const pollAuto = async () => {
      try {
        const status = await conversationApi.screenAutoStatus(sessionId)
        if (!alive) return
        setScreenAuto(status)
        setScreenAutoStatusError(false)
        if (status.last_capture_at) await refreshObservations()
      } catch {
        // UNKNOWN is not OFF. Preserve the last known ownership/state and
        // prevent a second start until the backend can be queried again.
        if (alive) setScreenAutoStatusError(true)
      }
    }
    void pollAuto()
    const timer = window.setInterval(() => void pollAuto(), 1500)
    return () => { alive = false; window.clearInterval(timer) }
  }, [sessionId, liveContext.data?.screen_runtime?.mode])

  useEffect(() => {
    let alive = true
    const poll = async () => {
      // Slow responses cannot race newer polls or resurrect an old CAPTURING
      // state after a pause, stop, start or end action.
      const ticket = capturePollGate.begin()
      if (ticket === null) return
      try {
        const [captureResult, transcriptResult, guidanceResult] = await Promise.allSettled([
          conversationApi.captureStatus(sessionId),
          conversationApi.transcript(sessionId, 80),
          conversationApi.guidanceHistory(sessionId, 12),
        ])
        if (!alive) return
        if (capturePollGate.current(ticket)) {
          // A failed ownership check is UNKNOWN, never proof of stopped capture.
          setCaptureStatusError(captureResult.status !== 'fulfilled')
          if (captureResult.status === 'fulfilled') setCapture(captureResult.value)
        }
        if (transcriptResult.status === 'fulfilled') setSegments(transcriptResult.value.items)
        if (guidanceResult.status === 'fulfilled') {
          const events = guidanceResult.value.items
          const newest = events[0]
          const latest = latestVisibleGuidance(events)
          setGuidance((current) => current?.id === latest?.id ? current : latest)
          if (latest) {
            setSilentPlan(null)
            setSuppressed('')
          } else if (newest) {
            setSilentPlan(newest.expression_plan?.render_as === 'SILENCE' ? newest.expression_plan : null)
            setSuppressed(newest.expression_plan?.suppression_reasons?.[0] ?? newest.reason ?? '')
          }
        } else {
          setGuidance(null)
          setSilentPlan(null)
        }
      } finally {
        capturePollGate.finish()
      }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 1200)
    return () => { alive = false; window.clearInterval(timer) }
  }, [sessionId, capturePollGate])

  if (session.loading) return <Page><Loading /></Page>
  if (session.error || !session.data) return <Page><ErrorState message={session.error ?? '会话不存在'} onRetry={session.reload} /></Page>
  const s = session.data
  const captureOwned = Boolean(capture?.owns_requested_session && capture.session_id === sessionId)
  const captureUnverified = Boolean(capture?.owns_requested_session && !captureOwned)
  const captureView = captureViewState(s, capture, captureStatusError || captureBusy)

  const startCapture = async () => {
    if (!primaryDevice) {
      setError('请选择主音频设备')
      return
    }
    capturePollGate.invalidate()
    setCaptureBusy(true); setError('')
    try {
      const next = await conversationApi.captureStart(
        sessionId,
        Number(primaryDevice),
        selfMic ? Number(selfMic) : null,
      )
      setCapture(next)
      setCaptureStatusError(false)
    } catch (e) { setCaptureStatusError(true); setError(e instanceof Error ? e.message : String(e)) }
    finally { setCaptureBusy(false) }
  }

  const toggleCapturePause = async () => {
    capturePollGate.invalidate()
    setCaptureBusy(true); setError('')
    try {
      const next = capture?.paused
        ? await conversationApi.captureResume(sessionId)
        : await conversationApi.capturePause(sessionId)
      setCapture(next)
      setCaptureStatusError(false)
    } catch (e) { setCaptureStatusError(true); setError(e instanceof Error ? e.message : String(e)) }
    finally { setCaptureBusy(false) }
  }

  const stopCapture = async () => {
    capturePollGate.invalidate()
    setCaptureBusy(true); setError('')
    try { setCapture(await conversationApi.captureStop(sessionId)); setCaptureStatusError(false) }
    catch (e) { setCaptureStatusError(true); setError(e instanceof Error ? e.message : String(e)) }
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
        talking_point: talkingPoint,
        delivery_focus: deliveryFocus,
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
        relationship_context: relationshipContext,
        audience_participant_id: audienceParticipantId,
      })
      setGuidance(result.guidance)
      setSilentPlan(result.guidance ? null : (result.event?.expression_plan ?? null))
      setSuppressed(result.guidance ? '' : (result.event?.expression_plan?.suppression_reasons?.[0] ?? result.suppressed ?? ''))
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

  const captureScreen = async () => {
    setScreenBusy(true); setError('')
    try {
      const saved = await conversationApi.captureScreenContext(sessionId, screenRegion)
      setScreenObservations((current) => [saved, ...current.filter((item) => item.id !== saved.id)].slice(0, 12))
    } catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setScreenBusy(false) }
  }

  const startAutoScreen = async () => {
    setScreenBusy(true); setError('')
    try {
      setScreenAuto(await conversationApi.screenAutoStart(sessionId, Number(screenAutoInterval), screenRegion))
      setScreenAutoStatusError(false)
    } catch (e) { setScreenAutoStatusError(true); setError(e instanceof Error ? e.message : String(e)) }
    finally { setScreenBusy(false) }
  }

  const toggleAutoScreenPause = async () => {
    setScreenBusy(true); setError('')
    try {
      const next = screenAuto?.paused
        ? await conversationApi.screenAutoResume(sessionId)
        : await conversationApi.screenAutoPause(sessionId)
      setScreenAuto(next)
      setScreenAutoStatusError(false)
    } catch (e) { setScreenAutoStatusError(true); setError(e instanceof Error ? e.message : String(e)) }
    finally { setScreenBusy(false) }
  }

  const stopAutoScreen = async () => {
    setScreenBusy(true); setError('')
    try { setScreenAuto(await conversationApi.screenAutoStop(sessionId)); setScreenAutoStatusError(false) }
    catch (e) { setScreenAutoStatusError(true); setError(e instanceof Error ? e.message : String(e)) }
    finally { setScreenBusy(false) }
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
    capturePollGate.invalidate()
    setBusy(true); setError('')
    try {
      if (captureOwned) setCapture(await conversationApi.captureStop(sessionId))
      const ended = await conversationApi.end(sessionId)
      setSummary(ended)
      if (s.policy?.share_privacy === 'PRIVATE_OVERLAY') {
        try {
          const restored = await restoreConversationSharePrivacy(sessionId)
          setSharePrivacyRuntime(restored)
          setSharePrivacyStatusError(false)
        } catch {
          setSharePrivacyStatusError(true)
          setError('会话已结束，但无法确认 Share Privacy 已恢复到会话前状态。为安全起见，请在设置或托盘中检查共享隐私状态。')
        }
      }
      await session.reload()
    }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setBusy(false) }
  }

  return (
    <Page wide testId="conversation-live">
      <PageHeader eyebrow="Conversation Beta" title={s.title} subtitle={`${s.status} · ${s.assistance_mode} · ${s.processing_mode} · AI ${s.policy?.ai_assistance ?? 'AI_ALLOWED'} · Human ${s.policy?.human_assistance ?? 'HUMAN_PRACTICE_ONLY'}`}
        actions={<div className="flex flex-wrap items-center gap-2">
          {s.policy?.share_privacy === 'PRIVATE_OVERLAY' ? <StatusBadge tone={sharePrivacyStatusError ? 'warn' : sharePrivacyRuntime?.protected ? 'ok' : 'warn'}>SHARE PRIVACY · {sharePrivacyStatusError ? 'UNKNOWN' : sharePrivacyRuntime?.protected ? 'ACTIVE' : 'NOT VERIFIED'}</StatusBadge> : null}
          {s.policy?.screen_context === 'AUTO' ? <StatusBadge tone={screenAutoStatusError ? 'warn' : screenAuto?.active ? (screenAuto.paused ? 'warn' : 'ok') : screenAuto?.last_error ? 'warn' : 'muted'}>SCREEN AUTO · {screenAutoStatusError ? 'UNKNOWN' : screenAuto?.active ? (screenAuto.paused ? 'OFF THE RECORD' : 'ACTIVE') : screenAuto?.last_error ? 'STOPPED' : 'NOT STARTED'}</StatusBadge> : null}
          <PrimaryButton disabled={busy || captureBusy || s.status === 'ENDED'} onClick={end} icon={<Square className="h-3.5 w-3.5" />}>结束并 Continue</PrimaryButton>
        </div>} />

      {error ? <ErrorState message={error} /> : null}

      {s.policy?.share_privacy === 'PRIVATE_OVERLAY' ? <div className="mb-4 rounded-xl border border-bg-tertiary bg-bg-secondary/35 px-3 py-2 text-[11px] text-text-muted" data-testid="conversation-share-privacy-status">
        <span className="font-semibold text-text-secondary">Share Privacy · {sharePrivacyStatusError ? 'UNKNOWN' : sharePrivacyRuntime?.protected ? 'ACTIVE' : 'NOT VERIFIED'}</span>
        <span> · Electron content protection is best-effort and only reduces accidental exposure on supported capture paths; it is not a security or “undetectable” guarantee.</span>
      </div> : null}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <div className="rounded-2xl border border-bg-tertiary bg-bg-secondary/25 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div><div className="flex items-center gap-2" role="status" aria-live="polite" data-testid="conversation-live-capture-status"><span className="relative flex h-2 w-2" aria-hidden="true">{captureView.listening ? <><span className="absolute inline-flex h-full w-full motion-safe:animate-ping rounded-full bg-accent-green opacity-50" /><span className="relative inline-flex h-2 w-2 rounded-full bg-accent-green" /></> : <span className="relative inline-flex h-2 w-2 rounded-full bg-text-muted" />}</span><span className="text-xs font-semibold text-text-primary">{captureView.label}</span></div><p className="mt-1 text-[11px] text-text-muted">一次只显示一个最高价值 Guidance；没有足够价值时保持 SILENT。</p></div>
              <div className="flex items-center gap-2">
                <select value={mode} onChange={(e) => void changeMode(e.target.value as AssistanceMode)} aria-label="帮助方式"
                  className="rounded-xl border border-bg-hover bg-bg-primary px-2 py-1.5 text-xs text-text-primary outline-none">
                  <option value="QUIET">Quiet</option>
                  <option value="BALANCED">Balanced</option>
                  <option value="ACTIVE">Active</option>
                  <option value="PRESENTATION">Presentation</option>
                  <option value="ONE_ON_ONE">1:1</option>
                </select>
              </div>
            </div>
            {s.capture_mode === 'TRANSCRIPT' ? (
              <div className="mt-4 rounded-xl border border-bg-tertiary bg-bg-primary/55 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2"><Mic className="h-3.5 w-3.5 text-accent-blue" /><span className="text-xs font-semibold text-text-primary">真实转写</span>{captureBusy ? <StatusBadge tone="muted">UPDATING</StatusBadge> : (captureStatusError || captureUnverified) ? <StatusBadge tone="warn">UNKNOWN</StatusBadge> : captureOwned ? <StatusBadge tone={capture.paused ? 'warn' : 'ok'}>{capture.paused ? 'PAUSED' : 'CAPTURING'}</StatusBadge> : <StatusBadge tone="muted">OFF</StatusBadge>}</div>
                    <p className="mt-1 text-[11px] text-text-muted">只复用 Audio/VAD/STT；不会启动 Interview 自动答题、Fast Cue 或 Interview Review。</p>
                  </div>
                  {captureOwned ? <div className="flex gap-2"><SecondaryButton disabled={captureBusy || captureStatusError} onClick={toggleCapturePause} icon={capture.paused ? <Play className="h-3.5 w-3.5" /> : <PauseCircle className="h-3.5 w-3.5" />}>{capture.paused ? '继续' : '暂停'}</SecondaryButton><SecondaryButton disabled={captureBusy} onClick={stopCapture}>停止转写</SecondaryButton></div> : <PrimaryButton disabled={captureBusy || !primaryDevice || captureStatusError || captureUnverified} onClick={startCapture} icon={<Mic className="h-3.5 w-3.5" />}>{captureBusy ? '启动中…' : '开始转写'}</PrimaryButton>}
                </div>
                {captureStatusError ? <p role="alert" className="mt-2 text-[11px] text-status-risk">无法确认后端的当前采集状态。不要把断开连接视为录音已停止；请恢复连接并确认后再启动另一场。</p> : null}
                {!captureOwned ? <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <Field label="主音频（优先系统/会议音频）"><select className={inputCls} value={primaryDevice} onChange={(e) => setPrimaryDevice(e.target.value)}><option value="">请选择</option>{(devices.data?.devices ?? []).map((d) => <option key={d.id} value={d.id}>{d.name}{d.is_loopback ? ' · loopback' : ''}</option>)}</select></Field>
                  <Field label="我的麦克风（可选）"><select className={inputCls} value={selfMic} onChange={(e) => setSelfMic(e.target.value)}><option value="">不单独采集</option>{(devices.data?.devices ?? []).filter((d) => String(d.id) !== primaryDevice).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
                </div> : null}
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-bg-tertiary px-3 py-2 text-[11px] text-text-muted">本场 Preflight 选择的是 {s.capture_mode}；不会启动音频转写。结构化事项与 Manual Ask 仍可使用。</div>
            )}
            <details className="mt-4 rounded-xl border border-bg-tertiary/70 bg-bg-primary/35 p-3" data-testid="manual-guidance-lab">
              <summary className="cursor-pointer text-xs font-semibold text-text-secondary">高级 / 手动 Guidance 验证</summary>
              <p className="mt-2 text-[11px] text-text-muted">正常 TRANSCRIPT 会自动驱动 Direct Question / Recall / Opportunity。这里保留给 dogfood、无音频模拟和边界验证，不是主交互。</p>
              <div className="mt-3">
                <label className="flex items-center gap-2 text-xs text-text-secondary"><input type="checkbox" checked={speaking} onChange={(e) => setSpeaking(e.target.checked)} />模拟：我正在连续表达</label>
              </div>
            <div className="mt-4 grid gap-3">
                <Field label="当前话题"><input className={inputCls} value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="例如：offline migration" /></Field>
                <Field label="对方直接问我的问题（如有）"><input className={inputCls} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="直接问题优先于主动 Opportunity" /></Field>
                <Field label="高价值 Opportunity 候选（如有）"><textarea className={inputCls} rows={3} value={candidate} onChange={(e) => setCandidate(e.target.value)} placeholder="例如：Q4 benchmark 已覆盖 10x data scale；必须有来源，是否显示由 Arbiter 决定。" /></Field>
                <Field label="明确 Talking Point（如有）"><textarea className={inputCls} rows={2} value={talkingPoint} onChange={(e) => setTalkingPoint(e.target.value)} placeholder="你明确希望组织成 talking point 的内容；仍要求来源且受 Profile 允许项约束。" /></Field>
                <Field label="Delivery / 表达重点（如有）"><textarea className={inputCls} rows={2} value={deliveryFocus} onChange={(e) => setDeliveryFocus(e.target.value)} placeholder="例如：控制在 45 秒；先回答 CTO 的 rollback concern。只改表达结构，不改事实。" /></Field>
                <Field label="已知关键风险（如有）"><textarea className={inputCls} rows={2} value={criticalRisk} onChange={(e) => setCriticalRisk(e.target.value)} placeholder="仅填写有明确来源、需要优先提醒的事实 / 承诺 / 冲突风险。" /></Field>
                <Field label="来源 / 依据"><textarea className={inputCls} rows={2} value={source} onChange={(e) => setSource(e.target.value)} placeholder="主动 Contribution Opportunity 必须有来源；没有来源会被抑制。" /></Field>
                <div className="rounded-xl border border-bg-tertiary/70 bg-bg-secondary/20 p-3">
                  <div className="text-xs font-semibold text-text-secondary">Stakeholder-aware Expression · 只用明确信息</div>
                  <p className="mt-1 text-[11px] text-text-muted">这些字段只影响“是否值得说、怎么组织”，不会改写事实，也不会推断情绪、人格或隐藏意图。优先级：Direct Question &gt; Critical Risk &gt; Talking Point / Delivery explicit request &gt; proactive Opportunity / Recall / Question。</p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <select className={inputCls} value={audienceParticipantId} onChange={(e) => setAudienceParticipantId(e.target.value)} aria-label="当前受众">
                      <option value="">不绑定已知参与者</option>
                      {(liveContext.data?.participants ?? []).map((participant) => <option key={participant.id} value={participant.id}>{participant.display_name || '未命名'}{participant.role ? ` · ${participant.role}` : ''}</option>)}
                    </select>
                    <input className={inputCls} value={audienceRole} onChange={(e) => setAudienceRole(e.target.value)} placeholder="对方明确角色，例如 CTO / 客户" />
                    <input className={inputCls} value={decisionAuthority} onChange={(e) => setDecisionAuthority(e.target.value)} placeholder="明确决策权限（可选）" />
                    <input className={inputCls} value={audiencePriority} onChange={(e) => setAudiencePriority(e.target.value)} placeholder="对方明确优先级" />
                    <input className={inputCls} value={audienceConcern} onChange={(e) => setAudienceConcern(e.target.value)} placeholder="对方明确 concern" />
                    <input className={inputCls} value={relationshipContext} onChange={(e) => setRelationshipContext(e.target.value)} placeholder="关系上下文，例如客户技术负责人" />
                  </div>
                  {audienceParticipantId ? <p className="mt-2 text-[10px] text-text-muted">已从 Frozen Session Pack 带入该参与者的 explicit state；你可以在本场覆盖表达上下文，但不会改写长期 Counterparty State。</p> : null}
                </div>
              </div>
              <div className="mt-4"><PrimaryButton disabled={busy || s.status !== 'ACTIVE'} onClick={evaluate} icon={<Volume2 className="h-3.5 w-3.5" />}>评估当前 Guidance</PrimaryButton></div>
            </details>
          </div>

          <div className="min-h-[160px] rounded-2xl border border-accent-blue/20 bg-bg-primary p-5">
            {guidance ? (
              <>
                <div className="flex flex-wrap items-center gap-2"><StatusBadge tone={guidance.kind === 'RISK' ? 'risk' : guidance.kind === 'CONTRIBUTION_OPPORTUNITY' ? 'info' : 'ok'}>{guidance.kind}</StatusBadge><span className="text-[11px] text-text-muted">{guidance.expression_action}</span><StatusBadge tone="muted">{guidance.expression_plan.render_as}</StatusBadge>{guidance.expression_plan.target_participant_id ? <StatusBadge tone="info">target {guidance.expression_plan.target_participant_id}</StatusBadge> : null}</div>
                <p className="mt-4 text-lg font-medium leading-relaxed text-text-primary">{guidance.text}</p>
                <p className="mt-3 text-xs text-text-muted">来源：{guidance.source_refs.length ? guidance.source_refs.map((x) => x.kind).join(' · ') : '当前直接问题 / 会话状态'} · reason {guidance.reason}</p>
                {guidance.expression_plan.warnings.length ? <div className="mt-2 space-y-1">{guidance.expression_plan.warnings.map((warning) => <div key={warning} className="text-[11px] text-status-inferred">Plan · {warning}</div>)}</div> : null}
                <div className="mt-4 flex gap-2"><SecondaryButton onClick={() => void conversationApi.guidanceAction(guidance.id, 'PINNED')} icon={<Pin className="h-3.5 w-3.5" />}>Pin</SecondaryButton><SecondaryButton onClick={() => { void conversationApi.guidanceAction(guidance.id, 'DISMISSED'); setGuidance(null) }}>忽略</SecondaryButton></div>
              </>
            ) : (
              <div className="flex h-full min-h-[120px] flex-col items-center justify-center text-center">
                <PauseCircle className="h-7 w-7 text-text-muted" />
                <p className="mt-2 text-sm font-medium text-text-primary">{suppressed ? '这一次选择不打扰你' : '等待高价值 Guidance'}</p>
                <p className="mt-1 text-xs text-text-muted">{suppressed ? `SILENT · ${suppressed}` : 'Direct Question > Critical Risk > Recall / Opportunity > Question > Delivery'}</p>
                {silentPlan ? <p className="mt-2 text-[11px] text-text-muted">Expression Plan · {silentPlan.render_as}{silentPlan.target_participant_id ? ` · target ${silentPlan.target_participant_id}` : ''}</p> : null}
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
            {liveContext.data.profile_playbook ? <div className="mt-3 rounded-xl border border-bg-tertiary/70 bg-bg-primary/45 p-3">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Frozen Profile Playbook</div>
              <p className="mt-1 text-xs text-text-primary">{liveContext.data.profile_playbook.closing_objective}</p>
              <div className="mt-2 flex flex-wrap gap-1">{liveContext.data.profile_playbook.priority_truth_types.slice(0, 6).map((kind) => <StatusBadge key={kind} tone="muted">{kind}</StatusBadge>)}</div>
              <p className="mt-2 text-[10px] text-text-muted">本场使用开始时冻结的 {liveContext.data.profile_playbook.profile} 工作框架；不是实时成功评分。</p>
            </div> : null}
            {(liveContext.data.brief.agenda?.length ?? 0) > 0 ? <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Agenda</div>
              <div className="mt-1 space-y-1">{liveContext.data.brief.agenda!.slice(0, 5).map((item, index) => <div key={`${index}:${item}`} className="text-[11px] text-text-secondary">{index + 1}. {item}</div>)}</div>
            </div> : null}
            {(liveContext.data.brief.expected_questions?.length ?? 0) > 0 ? <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Expected Questions</div>
              <div className="mt-1 space-y-1">{liveContext.data.brief.expected_questions!.slice(0, 3).map((item) => <div key={item} className="text-[11px] text-text-secondary">• {item}</div>)}</div>
            </div> : null}
            {(liveContext.data.brief.open_threads?.length ?? 0) > 0 ? <div className="mt-3">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">Frozen Open Threads</div>
              <div className="mt-1 space-y-1">{liveContext.data.brief.open_threads!.slice(0, 4).map((thread) => <div key={thread.id} className="flex items-start gap-1.5 text-[11px] text-text-secondary"><StatusBadge tone="warn">{thread.kind}</StatusBadge><span>{thread.text}</span></div>)}</div>
              <p className="mt-1 text-[10px] text-text-muted">只来自开始前已 review 的 longitudinal state；本场新提取内容要到 Continue 审核后才会进入下一场。</p>
            </div> : null}
            <div className="mt-3 rounded-xl bg-bg-primary/55 px-3 py-2 text-[10px] text-text-muted">
              <span>State · {liveContext.data.conversation_state.phase}</span>
              {liveContext.data.conversation_state.current_topic ? <span className="ml-2">Topic · {liveContext.data.conversation_state.current_topic}</span> : null}
              <span className="ml-2">Threads · {liveContext.data.conversation_state.open_threads.length}</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-1 text-[10px] text-text-muted">
              <span>Sources {liveContext.data.sources.length}</span>
              <span>Quick Notes {liveContext.data.quick_notes.length}</span>
              <span>Participants {liveContext.data.participants.length}</span>
              <span>Open {liveContext.data.brief.unresolved_count ?? 0}</span>
            </div>
            <div className="mt-3 rounded-lg bg-bg-primary/55 px-2.5 py-2 text-[10px] text-text-muted">
              <div className="font-semibold text-text-secondary">Frozen AI behavior</div>
              <div className="mt-1 grid gap-1">
                <span>Policy · {liveContext.data.resolved_ai_behavior.policy}</span>
                <span>Manual · {liveContext.data.resolved_ai_behavior.manual_ask ? 'ON' : 'OFF'}</span>
                <span>Auto Guidance · {liveContext.data.resolved_ai_behavior.automatic_transcript_guidance ? 'ON' : 'OFF'}</span>
                <span>Auto Extraction · {liveContext.data.resolved_ai_behavior.automatic_candidate_extraction ? 'ON' : 'OFF'}</span>
              </div>
            </div>
            <div className="mt-3 rounded-lg bg-bg-primary/55 px-2.5 py-2 text-[10px] text-text-muted">
              <div className="font-semibold text-text-secondary">Frozen data path</div>
              <div className="mt-1 grid gap-1">
                <span>Capture · {liveContext.data.processing_runtime.data_path?.capture ?? '—'}</span>
                <span>STT · {liveContext.data.processing_runtime.data_path?.stt ?? '—'} / {liveContext.data.processing_runtime.configured_stt_provider ?? '—'}</span>
                <span>Inference · {liveContext.data.processing_runtime.data_path?.inference ?? '—'}</span>
                <span>Retention · {liveContext.data.processing_runtime.data_path?.retention ?? '—'}</span>
                <span>Write-back · {liveContext.data.processing_runtime.data_path?.writeback ?? '—'}</span>
                <span>Screen · {liveContext.data.screen_runtime?.mode === 'MANUAL' ? `${liveContext.data.screen_runtime.route ?? '—'} / ${liveContext.data.screen_runtime.model_id || liveContext.data.screen_runtime.model_name || 'vision'}` : liveContext.data.screen_runtime?.mode ?? 'OFF'}</span>
                <span>Raw screen image · {liveContext.data.screen_runtime?.raw_image_persisted ? 'PERSISTED' : 'NOT STORED'}</span>
              </div>
            </div>
          </div> : null}

          {liveContext.data?.screen_runtime?.mode === 'MANUAL' ? <div className="rounded-2xl border border-bg-tertiary p-4" data-testid="conversation-screen-context">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2"><Camera className="h-4 w-4 text-accent-blue" /><h2 className="text-sm font-semibold text-text-primary">Manual Screen Context</h2></div>
                <p className="mt-1 text-[11px] text-text-muted">只在你主动点击时抓取一次；原图不保存。仅保留提取文本、image hash 与视觉模型/route provenance。</p>
              </div>
              <StatusBadge tone={liveContext.data.screen_runtime.route === 'LOCAL' ? 'ok' : 'warn'}>{liveContext.data.screen_runtime.route ?? 'UNAVAILABLE'}</StatusBadge>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_auto]">
              <select className={inputCls} value={screenRegion} onChange={(e) => setScreenRegion(e.target.value as typeof screenRegion)} aria-label="屏幕区域">
                <option value="configured">使用设置中的区域</option><option value="full">全屏</option><option value="left_half">左半屏</option><option value="right_half">右半屏</option><option value="top_half">上半屏</option><option value="bottom_half">下半屏</option>
              </select>
              <SecondaryButton disabled={screenBusy || s.status !== 'ACTIVE'} onClick={captureScreen} icon={<Camera className="h-3.5 w-3.5" />}>{screenBusy ? '提取中…' : '抓取一次'}</SecondaryButton>
            </div>
            <div className="mt-2 text-[10px] text-text-muted">Model · {liveContext.data.screen_runtime.model_id || liveContext.data.screen_runtime.model_name || '—'} · fingerprint {liveContext.data.screen_runtime.fingerprint ? liveContext.data.screen_runtime.fingerprint.slice(0, 10) : '—'} · raw image NOT STORED</div>
            {screenObservations.length ? <div className="mt-3 space-y-2">{screenObservations.map((item) => <div key={item.id} className="rounded-xl bg-bg-secondary/40 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2"><StatusBadge tone="muted">OBSERVED_NOT_CONFIRMED</StatusBadge><span className="text-[10px] text-text-muted">{item.vision_route} · {item.vision_model} · {item.region}</span></div>
              <p className="mt-1 text-xs leading-relaxed text-text-primary">{item.text}</p>
            </div>)}</div> : <p className="mt-3 text-[11px] text-text-muted">本场还没有屏幕观察。截图提取结果不会自动升级成 Decision / Commitment。</p>}
          </div> : null}


          {liveContext.data?.screen_runtime?.mode === 'AUTO' ? <div className="rounded-2xl border border-bg-tertiary p-4" data-testid="conversation-screen-context-auto">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2"><Camera className="h-4 w-4 text-accent-blue" /><h2 className="text-sm font-semibold text-text-primary">Auto Screen Context</h2></div>
                <p className="mt-1 text-[11px] text-text-muted">AUTO 只表示本场允许自动屏幕上下文；不会随会话自动启动。你必须在这里再次显式开始，且可以随时 Off the record。原图永不持久化。</p>
              </div>
              <StatusBadge tone={screenAutoStatusError ? 'warn' : screenAuto?.active ? (screenAuto.paused ? 'warn' : 'ok') : screenAuto?.last_error ? 'warn' : 'muted'}>
                {screenAutoStatusError ? 'UNKNOWN' : screenAuto?.active ? (screenAuto.paused ? 'OFF THE RECORD' : 'ACTIVE') : screenAuto?.last_error ? 'AUTO STOPPED' : 'NOT STARTED'}
              </StatusBadge>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <select className={inputCls} value={screenRegion} onChange={(e) => setScreenRegion(e.target.value as typeof screenRegion)} aria-label="自动屏幕区域" disabled={Boolean(screenAuto?.active)}>
                <option value="configured">使用设置中的区域</option><option value="full">全屏</option><option value="left_half">左半屏</option><option value="right_half">右半屏</option><option value="top_half">上半屏</option><option value="bottom_half">下半屏</option>
              </select>
              <select className={inputCls} value={screenAutoInterval} onChange={(e) => setScreenAutoInterval(e.target.value)} aria-label="自动屏幕间隔" disabled={Boolean(screenAuto?.active)}>
                <option value="15">每 15 秒</option><option value="30">每 30 秒</option><option value="60">每 60 秒</option>
              </select>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {!screenAuto?.active && !screenAutoStatusError ? <PrimaryButton disabled={screenBusy || s.status !== 'ACTIVE'} onClick={startAutoScreen} icon={<Camera className="h-3.5 w-3.5" />}>{screenBusy ? '启动中…' : '开始自动屏幕上下文'}</PrimaryButton> : null}
              {screenAuto?.active && !screenAutoStatusError ? <SecondaryButton disabled={screenBusy} onClick={toggleAutoScreenPause}>{screenAuto.paused ? '恢复自动观察' : 'Off the record'}</SecondaryButton> : null}
              {screenAuto?.active ? <SecondaryButton disabled={screenBusy} onClick={stopAutoScreen}>停止 AUTO</SecondaryButton> : null}
              {screenAutoStatusError && !screenAuto?.active ? <SecondaryButton disabled={screenBusy} onClick={stopAutoScreen}>尝试停止 AUTO</SecondaryButton> : null}
            </div>
            {screenAutoStatusError ? <p role="alert" className="mt-3 text-[11px] text-status-risk">无法确认后端 AUTO Screen Context 的当前状态。不要把连接中断视为屏幕捕获已经停止；恢复连接并确认，或尝试发送停止命令。</p> : null}
            <div className="mt-3 rounded-xl bg-bg-secondary/35 px-3 py-2 text-[10px] text-text-muted">
              <div>Model · {liveContext.data.screen_runtime.model_id || liveContext.data.screen_runtime.model_name || '—'} · route {liveContext.data.screen_runtime.route ?? 'UNAVAILABLE'} · raw image NOT STORED</div>
              <div className="mt-1">Interval · {screenAuto?.interval_seconds ?? Number(screenAutoInterval)}s · last observation {screenAuto?.last_capture_at ? new Date(screenAuto.last_capture_at * 1000).toLocaleTimeString() : '—'} · duplicate frames skipped</div>
              {screenAuto?.last_error ? <div className="mt-1 text-status-risk">AUTO 已因错误停止/受限：{screenAuto.last_error}</div> : null}
            </div>
            {screenObservations.length ? <div className="mt-3 space-y-2">{screenObservations.map((item) => <div key={item.id} className="rounded-xl bg-bg-secondary/40 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2"><StatusBadge tone="muted">OBSERVED_NOT_CONFIRMED</StatusBadge><span className="text-[10px] text-text-muted">{item.capture_mode} · {item.vision_route} · {item.vision_model} · {item.region}</span></div>
              <p className="mt-1 text-xs leading-relaxed text-text-primary">{item.text}</p>
            </div>)}</div> : <p className="mt-3 text-[11px] text-text-muted">尚无自动屏幕观察。AUTO 不会把屏幕内容自动升级成 Decision / Commitment。</p>}
          </div> : null}

          <div className="rounded-2xl border border-bg-tertiary p-4">
            <h2 className="text-sm font-semibold text-text-primary">问成竹 · 本场可追溯上下文</h2>
            <p className="mt-1 text-[11px] text-text-muted">检索开始时冻结的 Ready sources / Quick Notes、已确认历史，以及本场当前 transcript。每条结果标明 authority；观察和笔记不会冒充 confirmed truth。</p>
            <div className="mt-3 space-y-2">
              <textarea className={inputCls} rows={2} value={askText} onChange={(e) => setAskText(e.target.value)} placeholder="例如：之前为什么用 v2？Q4 benchmark 说了什么？刚才是否提到 rollback？" />
              <SecondaryButton disabled={busy || !askText.trim() || s.policy?.ai_assistance === 'AI_FORBIDDEN'} onClick={ask}>查本场可用来源</SecondaryButton>
              {s.policy?.ai_assistance === 'AI_FORBIDDEN' ? <p className="text-[11px] text-status-inferred">本场 AI Assistance = AI_FORBIDDEN；Manual Ask 已禁用。冻结来源仍保留在 Pack 中，但不会由成竹检索回答。</p> : null}
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
        {summary.profile_outcome ? <div className="mt-4 rounded-xl border border-bg-tertiary/70 bg-bg-primary/45 p-3">
          <div className="text-xs font-semibold text-text-secondary">{summary.profile_outcome.profile} · Reviewed Outcome Evidence</div>
          <p className="mt-1 text-[11px] text-text-muted">{summary.profile_outcome.closing_objective}</p>
          <div className="mt-2 flex flex-wrap gap-2">{summary.profile_outcome.priority_truth_types.map((kind) => <StatusBadge key={kind} tone={summary.profile_outcome.reviewed_counts[kind] ? 'ok' : 'muted'}>{kind} {summary.profile_outcome.reviewed_counts[kind] ?? 0}</StatusBadge>)}</div>
          <p className="mt-2 text-[10px] text-text-muted">{summary.profile_outcome.interpretation}</p>
        </div> : null}
        {summary.next_focus ? <p className="mt-4 text-sm text-text-primary">Next Focus · {summary.next_focus.title}</p> : null}
        <div className="mt-4"><PrimaryButton onClick={() => navigate(paths.conversationSpace(s.space_id, 'sessions'))}>回到 Space · Continue</PrimaryButton></div>
      </div> : null}
    </Page>
  )
}
