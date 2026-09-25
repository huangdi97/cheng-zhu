import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, Send, Sparkles, Loader2, CheckCircle2, XCircle, AlertTriangle, RotateCcw, Mic, Target } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { api, PrepPracticeQuestion, PrepPracticeAnswerResult } from '@/lib/api'

interface TurnItem {
  question: PrepPracticeQuestion
  answer: string
  result: PrepPracticeAnswerResult
}

interface Props {
  spaceId: number
  onClose: () => void
}

function scoreSummary(scorecard: Record<string, number> | undefined): string | null {
  if (!scorecard) return null
  const values = Object.values(scorecard).filter((v) => typeof v === 'number')
  if (values.length === 0) return null
  const avg = values.reduce((a, b) => a + b, 0) / values.length
  return avg.toFixed(1)
}

export default function PracticePanel({ spaceId, onClose }: Props) {
  const [practiceId, setPracticeId] = useState<string | null>(null)
  const [rounds, setRounds] = useState(5)
  const [current, setCurrent] = useState<PrepPracticeQuestion | null>(null)
  const [turns, setTurns] = useState<TurnItem[]>([])
  const [answer, setAnswer] = useState('')
  const [devices, setDevices] = useState<{ id: number; name: string; is_loopback?: boolean }[]>([])
  const [micDeviceId, setMicDeviceId] = useState<number>(0)
  const [recording, setRecording] = useState(false)
  const [recordingMsg, setRecordingMsg] = useState<string | null>(null)
  const [liveText, setLiveText] = useState('')
  const [liveLevel, setLiveLevel] = useState(0)
  const [starting, setStarting] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [report, setReport] = useState<PrepPracticeAnswerResult['report'] | null>(null)
  const [weakPoints, setWeakPoints] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  const start = useCallback(async () => {
    setStarting(true)
    setError(null)
    try {
      const res = await api.prepPracticeStart(spaceId, 5) as { practice_id: string; rounds: number; question: PrepPracticeQuestion; weak_points?: string[] }
      setPracticeId(res.practice_id)
      setRounds(res.rounds)
      setCurrent(res.question)
      setWeakPoints(res.weak_points ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '开始练习失败')
    } finally {
      setStarting(false)
    }
  }, [spaceId])

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
  }, [turns, current, report, submitting])

  const submit = async () => {
    if (!practiceId || !answer.trim() || submitting) return
    setSubmitting(true)
    setError(null)
    const text = answer.trim()
    try {
      const res = await api.prepPracticeAnswer(practiceId, text)
      if (current) {
        setTurns((prev) => [...prev, { question: current, answer: text, result: res }])
      }
      setAnswer('')
      if (res.done) {
        setReport(res.report ?? null)
        setCurrent(null)
      } else {
        setCurrent(res.next_question ?? null)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const finishEarly = async () => {
    if (!practiceId || submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const res = await api.prepPracticeFinish(practiceId)
      setReport(res.report)
      setCurrent(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : '结束失败')
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

  const restart = () => {
    setPracticeId(null)
    setTurns([])
    setReport(null)
    setCurrent(null)
    setAnswer('')
    setError(null)
    start()
  }

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between gap-2 pb-3 border-b border-bg-hover/40">
        <div className="flex items-center gap-2">
          <button onClick={onClose} className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-accent-blue transition-colors">
            <ArrowLeft className="h-4 w-4" /> 返回准备空间
          </button>
          <span className="text-sm font-semibold text-text-primary">模拟面试练习</span>
          {practiceId && !report ? (
            <span className="rounded-lg bg-bg-tertiary px-2 py-0.5 text-[11px] text-text-secondary">
              {turns.length}/{rounds} 轮
            </span>
          ) : null}
        </div>
        {practiceId && !report && (
          <button onClick={finishEarly} disabled={submitting || turns.length === 0}
            className="inline-flex items-center gap-1 rounded-lg border border-bg-hover/50 px-2.5 py-1.5 text-xs text-text-muted hover:text-accent-red hover:border-accent-red/40 disabled:opacity-40 transition-colors">
            结束练习
          </button>
        )}
      </div>

      {error ? (
        <div className="mt-3 flex items-start gap-2 rounded-xl bg-accent-red/10 border border-accent-red/30 p-3 text-sm text-accent-red">
          <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" /> {error}
        </div>
      ) : null}
      {!error && weakPoints.length > 0 && !report && (
        <div className="mt-3 flex items-start gap-2 rounded-xl border border-accent-amber/25 bg-accent-amber/10 px-3 py-2 text-xs text-accent-amber">
          <Target className="h-3.5 w-3.5 mt-0.5 flex-shrink-0" />
          <span>
            本场优先补弱项：{weakPoints.slice(0, 4).join('、')} —— 题目已按薄弱点排序
          </span>
        </div>
      )}

      <div className="flex-1 overflow-y-auto min-h-0 py-4 space-y-4">
        {starting ? (
          <div className="py-16 text-center text-sm text-text-muted flex items-center justify-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" /> 正在准备第一题…
          </div>
        ) : (
          <>
            {turns.map((t, i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-bg-hover/40 bg-bg-secondary/70 px-4 py-3">
                    <div className="text-[11px] text-text-muted mb-1">面试官 Q{i + 1}</div>
                    <div className="text-sm text-text-primary leading-relaxed">{t.question.question}</div>
                  </div>
                </div>
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-accent-blue/10 border border-accent-blue/20 px-4 py-3">
                    <div className="text-[11px] text-text-muted mb-1">我的回答</div>
                    <div className="text-sm text-text-primary leading-relaxed whitespace-pre-wrap">{t.answer}</div>
                  </div>
                </div>
                {t.result.feedback ? (
                  <div className="ml-2 rounded-2xl border border-bg-hover/40 bg-bg-secondary/40 px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2 mb-2">
                      <span className="text-[11px] font-semibold text-text-muted uppercase tracking-wide">即时反馈</span>
                      {t.result.feedback.scorecard && Object.keys(t.result.feedback.scorecard).length > 0 ? (
                        <span className="rounded-lg bg-accent-blue/15 text-accent-blue px-2 py-0.5 text-[11px]">均分 {scoreSummary(t.result.feedback.scorecard)}</span>
                      ) : null}
                    </div>
                    {t.result.feedback.strengths && t.result.feedback.strengths.length > 0 ? (
                      <div className="flex items-start gap-1.5 mb-1">
                        <CheckCircle2 className="h-3.5 w-3.5 text-accent-green mt-0.5 flex-shrink-0" />
                        <div className="text-[13px] text-text-secondary">{t.result.feedback.strengths.join('；')}</div>
                      </div>
                    ) : null}
                    {t.result.feedback.risks && t.result.feedback.risks.length > 0 ? (
                      <div className="flex items-start gap-1.5 mb-1">
                        <XCircle className="h-3.5 w-3.5 text-accent-red mt-0.5 flex-shrink-0" />
                        <div className="text-[13px] text-text-secondary">{t.result.feedback.risks.join('；')}</div>
                      </div>
                    ) : null}
                    {t.result.feedback.improvement_advice ? (
                      <div className="text-[13px] text-text-muted mt-1">💡 {t.result.feedback.improvement_advice}</div>
                    ) : null}
                    {t.result.feedback.follow_up_questions && t.result.feedback.follow_up_questions.length > 0 ? (
                      <div className="text-[12px] text-text-muted mt-1">可能被追问：{t.result.feedback.follow_up_questions.join('；')}</div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ))}

            {current && !report ? (
              <div className="space-y-2">
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-accent-blue/30 bg-accent-blue/10 px-4 py-3">
                    <div className="text-[11px] text-text-muted mb-1">面试官 · 第 {turns.length + 1} 题</div>
                    <div className="text-sm text-text-primary leading-relaxed">{current.question}</div>
                    {current.why ? <div className="mt-1 text-xs text-text-muted">考察：{current.why}</div> : null}
                  </div>
                </div>
              </div>
            ) : null}

            {report ? (
              <div className="rounded-2xl border border-accent-green/30 bg-accent-green/5 p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-accent-green" />
                  <h3 className="text-sm font-bold text-text-primary">练习完成 · 整场总结</h3>
                  {report.avg_score != null ? (
                    <span className="rounded-lg bg-accent-green/15 text-accent-green px-2 py-0.5 text-[11px]">整场均分 {report.avg_score}</span>
                  ) : null}
                </div>
                {report.summary_markdown ? (
                  <div className="text-[13px] text-text-secondary leading-relaxed">
                    <ReactMarkdown>{report.summary_markdown}</ReactMarkdown>
                  </div>
                ) : null}
                {report.strong_points && report.strong_points.length > 0 ? (
                  <div className="text-[13px] text-text-secondary"><span className="text-text-muted">亮点关键词：</span>{report.strong_points.join('、')}</div>
                ) : null}
                {report.weak_points && report.weak_points.length > 0 ? (
                  <div className="text-[13px] text-text-secondary"><span className="text-text-muted">待加强：</span>{report.weak_points.join('、')}</div>
                ) : null}
                {report.review_session_id ? (
                  <div className="text-xs text-text-muted">本场已自动保存到「面试复盘」（记录 #{report.review_session_id}），可去复盘模块查看逐题分析。</div>
                ) : null}
                <button onClick={restart} className="inline-flex items-center gap-1.5 rounded-xl bg-accent-blue px-3.5 py-1.5 text-xs font-medium text-white shadow-sm shadow-accent-blue/20 hover:bg-accent-blue/90">
                  <RotateCcw className="h-3.5 w-3.5" /> 再练一场
                </button>
              </div>
            ) : null}
          </>
        )}
        <div ref={bottomRef} />
      </div>

      {!report && current ? (
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
            <button onClick={handleRecord} disabled={recording || !current}
              className="inline-flex items-center gap-1.5 rounded-xl border border-accent-blue/40 bg-accent-blue/10 px-3 py-1.5 text-xs font-medium text-accent-blue hover:bg-accent-blue/20 disabled:opacity-40 transition-colors">
              <Mic className="h-3.5 w-3.5" /> {recording ? '聆听中…' : '语音作答'}
            </button>
            {recordingMsg ? <span className="text-[11px] text-text-muted">{recordingMsg}</span> : null}
          </div>
          <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} rows={3} placeholder="把你的回答打在这里（尽量像面试一样完整表达）…"
            className="w-full rounded-xl border border-bg-hover/50 bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-blue/60 focus:outline-none resize-y" />
          <div className="flex items-center justify-between mt-2">
            <span className="text-[11px] text-text-muted">回答后 AI 会即时评分并继续追问 / 下一题</span>
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
          <Sparkles className="h-3.5 w-3.5" /> 请稍候，正在生成第一题…
        </div>
      )}
    </div>
  )
}