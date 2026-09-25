import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Send, Sparkles, Loader2, CheckCircle2, Mic, SkipForward, FolderKanban } from 'lucide-react'
import { api, SkillBuilderAnswerResult } from '@/lib/api'

interface Props {
  spaceId: number
  onClose: () => void
}

interface TurnItem {
  question: string
  answer: string
}

export default function SkillBuilderPanel({ spaceId, onClose }: Props) {
  const [builderId, setBuilderId] = useState<string | null>(null)
  const [project, setProject] = useState('')
  const [projectIndex, setProjectIndex] = useState(0)
  const [projectTotal, setProjectTotal] = useState(0)
  const [question, setQuestion] = useState('')
  const [questionIndex, setQuestionIndex] = useState(0)
  const [questionTotal, setQuestionTotal] = useState(0)
  const [turns, setTurns] = useState<TurnItem[]>([])
  const [savedCards, setSavedCards] = useState<Record<string, unknown>[]>([])
  const [answer, setAnswer] = useState('')
  const [starting, setStarting] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [devices, setDevices] = useState<{ id: number; name: string; is_loopback?: boolean }[]>([])
  const [micDeviceId, setMicDeviceId] = useState<number>(0)
  const [recording, setRecording] = useState(false)
  const [recordingMsg, setRecordingMsg] = useState<string | null>(null)
  const [liveText, setLiveText] = useState('')
  const [liveLevel, setLiveLevel] = useState(0)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  const applyState = useCallback((res: SkillBuilderAnswerResult) => {
    setDone(res.done === true)
    if (res.card_saved) setSavedCards((prev) => [...prev, res.card_saved])
    if (res.project) setProject(res.project)
    if (typeof res.project_index === 'number') setProjectIndex(res.project_index)
    if (typeof res.project_total === 'number') setProjectTotal(res.project_total)
    if (res.question) setQuestion(res.question)
    if (typeof res.question_index === 'number') setQuestionIndex(res.question_index)
    if (typeof res.question_total === 'number') setQuestionTotal(res.question_total)
  }, [])

  const start = useCallback(async () => {
    setStarting(true)
    setError(null)
    try {
      const res = await api.prepSkillBuilderStart(spaceId)
      setBuilderId(res.builder_id)
      applyState(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '开始失败')
    } finally {
      setStarting(false)
    }
  }, [spaceId, applyState])

  useEffect(() => {
    start()
  }, [start])

  useEffect(() => {
    api.getDevices().then((res: any) => {
      const inputs = ((res?.devices as any[]) || []).filter((d) => !d?.is_loopback)
      if (inputs.length > 0) {
        setDevices(inputs)
        setMicDeviceId(Number(inputs[0].id))
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [turns, question, submitting, done])

  const submit = async () => {
    if (!builderId || !answer.trim() || submitting) return
    setSubmitting(true)
    setError(null)
    const text = answer.trim()
    try {
      const res = await api.prepSkillBuilderAnswer(builderId, text)
      setTurns((prev) => [...prev, { question, answer: text }])
      setAnswer('')
      applyState(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const skip = async () => {
    if (!builderId || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.prepSkillBuilderSkip(builderId)
      setTurns((prev) => [...prev, { question: `[跳过] ${question}`, answer: '（跳过）' }])
      setAnswer('')
      applyState(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : '跳过失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handleRecord = async () => {
    if (recording) return
    setRecording(true)
    setLiveText('')
    setRecordingMsg('正在听…（说话时文字实时出现，停顿 1-2 秒自动识别）')
    try {
      await api.prepListenStart(micDeviceId, 60)
      let done = false
      while (!done) {
        await new Promise((r) => setTimeout(r, 250))
        const st = await api.prepListenStatus()
        setLiveText(st.partial_text || st.final_text || '')
        setLiveLevel(st.level ?? 0)
        if (st.done || !st.active) done = true
      }
      const res = await api.prepListenStop()
      if (res.text) {
        setAnswer(res.text)
        setRecordingMsg('已识别，可修改后提交')
      } else {
        setRecordingMsg(res.heard_speech ? '未识别到内容，请重试' : '没有听到声音，请确认选中的麦克风设备后重试')
      }
    } catch (e) {
      setRecordingMsg(e instanceof Error ? e.message : '录音失败')
    } finally {
      setRecording(false)
    }
  }

  const cardName = (c: Record<string, unknown>) => String(c?.name || c?.project || '技能卡')

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between gap-2 pb-3 border-b border-bg-hover/40">
        <div className="flex items-center gap-2">
          <button onClick={onClose} className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-accent-blue transition-colors">
            <ArrowLeft className="h-4 w-4" /> 返回准备空间
          </button>
          <span className="text-sm font-semibold text-text-primary">技能卡工作台</span>
          {builderId && !done ? (
            <span className="rounded-lg bg-bg-tertiary px-2 py-0.5 text-[11px] text-text-secondary">
              项目 {Math.min(projectIndex + 1, projectTotal)}/{projectTotal} · 追问 {questionIndex}/{questionTotal}
            </span>
          ) : null}
        </div>
        {builderId && !done ? (
          <button onClick={skip} disabled={submitting || turns.length === 0}
            className="inline-flex items-center gap-1 rounded-lg border border-bg-hover/50 px-2.5 py-1.5 text-xs text-text-muted hover:text-accent-red hover:border-accent-red/40 disabled:opacity-40 transition-colors">
            <SkipForward className="h-3.5 w-3.5" /> 跳过本项
          </button>
        ) : null}
      </div>

      {error ? (
        <div className="mt-3 rounded-xl bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">{error}</div>
      ) : null}

      <div className="flex-1 overflow-y-auto min-h-0 py-4 space-y-4">
        {starting ? (
          <div className="py-16 text-center text-sm text-text-muted flex items-center justify-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" /> 正在从简历识别项目并准备第一问…
          </div>
        ) : (
          <>
            {turns.map((t, i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-bg-hover/40 bg-bg-secondary/70 px-4 py-3">
                    <div className="text-[11px] text-text-muted mb-1">面试官追问 {i + 1}</div>
                    <div className="text-sm text-text-primary leading-relaxed">{t.question}</div>
                  </div>
                </div>
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent-blue/10 border border-accent-blue/20 px-4 py-3">
                    <div className="text-[11px] text-text-muted mb-1">我的回答</div>
                    <div className="text-sm text-text-primary leading-relaxed whitespace-pre-wrap">{t.answer}</div>
                  </div>
                </div>
              </div>
            ))}

            {question && !done ? (
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-accent-blue/30 bg-accent-blue/10 px-4 py-3">
                  <div className="text-[11px] text-text-muted mb-1">项目「{project}」· 第 {questionIndex} 问</div>
                  <div className="text-sm text-text-primary leading-relaxed">{question}</div>
                </div>
              </div>
            ) : null}

            {savedCards.length > 0 ? (
              <div className="rounded-2xl border border-accent-green/30 bg-accent-green/5 p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-accent-green" />
                  <h3 className="text-sm font-bold text-text-primary">已沉淀技能卡（{savedCards.length}）</h3>
                </div>
                {savedCards.map((c, i) => (
                  <div key={i} className="text-[13px] text-text-secondary">
                    <span className="font-semibold text-text-primary">{cardName(c)}</span>
                    {c.my_role ? ` · 角色：${String(c.my_role)}` : ''}
                  </div>
                ))}
              </div>
            ) : null}

            {done ? (
              <div className="rounded-2xl border border-accent-green/30 bg-accent-green/5 p-4 space-y-2">
                <div className="flex items-center gap-2">
                  <FolderKanban className="h-5 w-5 text-accent-green" />
                  <h3 className="text-sm font-bold text-text-primary">全部项目已整理完成</h3>
                </div>
                <p className="text-[13px] text-text-secondary">技能卡已保存到准备空间，去详情页查看完整卡片，或直接开始模拟面试。</p>
                <button onClick={onClose} className="inline-flex items-center gap-1.5 rounded-xl bg-accent-blue px-3.5 py-1.5 text-xs font-medium text-white shadow-sm shadow-accent-blue/20 hover:bg-accent-blue/90">
                  返回准备空间
                </button>
              </div>
            ) : null}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {!done && question ? (
        <div className="border-t border-bg-hover/40 pt-3 pb-1">
          {recording && (
            <div className="mb-2 rounded-xl border border-accent-blue/40 bg-accent-blue/10 px-4 py-3">
              <div className="flex items-center gap-2 text-[11px] text-accent-blue mb-1">
                <Loader2 className="h-3 w-3 animate-spin" /> 正在实时听写…（边说话边出字）
              </div>
              <div className="text-lg font-semibold text-text-primary min-h-[28px] whitespace-pre-wrap">{liveText || '（开始说话…）'}</div>
              <div className="mt-2">
                <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, (liveLevel / 300) * 100)}%`, background: liveLevel > 30 ? '#34d399' : '#60a5fa' }} />
                </div>
                <div className="mt-0.5 text-[10px] text-text-muted">输入电平 {Math.round(liveLevel)} {liveLevel > 30 ? '· 正在收音' : '· 没听到声音，请换一个麦克风'}</div>
              </div>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <select value={micDeviceId} onChange={(e) => setMicDeviceId(Number(e.target.value))}
              className="flex-1 min-w-[150px] rounded-xl border border-bg-hover/50 bg-bg-primary px-2.5 py-1.5 text-xs text-text-primary focus:border-accent-blue/60 focus:outline-none">
              {devices.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <button onClick={handleRecord} disabled={recording}
              className="inline-flex items-center gap-1.5 rounded-xl border border-accent-blue/40 bg-accent-blue/10 px-3 py-1.5 text-xs font-medium text-accent-blue hover:bg-accent-blue/20 disabled:opacity-40 transition-colors">
              <Mic className="h-3.5 w-3.5" /> {recording ? '聆听中…' : '语音作答'}
            </button>
            {recordingMsg ? <span className="text-[11px] text-text-muted">{recordingMsg}</span> : null}
          </div>
          <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} rows={3} placeholder="直接回答这个问题（越具体越好，之后会整理进技能卡）…"
            className="w-full rounded-xl border border-bg-hover/50 bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 focus:outline-none resize-y" />
          <div className="flex items-center justify-between mt-2">
            <span className="text-[11px] text-text-muted">答完自动进入下一问，6 问后生成技能卡并进入下一个项目</span>
            <button onClick={submit} disabled={submitting || !answer.trim()}
              className="inline-flex items-center gap-1.5 rounded-xl bg-accent-blue px-4 py-2 text-xs font-medium text-white shadow-sm shadow-accent-blue/20 hover:bg-accent-blue/90 disabled:opacity-40">
              {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              提交回答
            </button>
          </div>
        </div>
      ) : null}

      {starting && (
        <div className="text-center py-2 text-xs text-text-muted flex items-center justify-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5" /> 请稍候，正在准备…
        </div>
      )}
    </div>
  )
}