import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, CircleAlert, MonitorUp, NotebookPen, Play, Sparkles } from 'lucide-react'
import { api, getErrorMessage } from '@/lib/api'
import { buildFastCueViewModel, CUE_SOURCE_LABELS } from '@/lib/guidanceViewModel'
import { productApi, type PracticeFeedback, type PracticeReport } from '@/lib/productApi'
import { useInterviewStore } from '@/stores/configStore'

interface Props {
  goalId: string | null
  onCompleted: () => void
}

/**
 * Final onboarding step: one real guided Practice turn plus the real Fast Cue
 * pipeline. Hardware playback uses speechSynthesis when available; the user can
 * explicitly choose the fixture fallback when hardware/provider access is not
 * available. A fallback is labelled as such and never masquerades as real
 * runtime evidence.
 */
export default function GuidedFirstPractice({ goalId, onCompleted }: Props) {
  const qaPairs = useInterviewStore((s) => s.qaPairs)
  const [practiceId, setPracticeId] = useState('')
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [feedback, setFeedback] = useState<PracticeFeedback | null>(null)
  const [report, setReport] = useState<PracticeReport | null>(null)
  const [quickNote, setQuickNote] = useState('')
  const [quickNoteSaved, setQuickNoteSaved] = useState(false)
  const [overlayState, setOverlayState] = useState<'IDLE' | 'OPENED' | 'UNAVAILABLE' | 'ERROR'>('IDLE')
  const [screenshotState, setScreenshotState] = useState<'IDLE' | 'TRIED' | 'UNAVAILABLE'>('IDLE')
  const [busy, setBusy] = useState(false)
  const [cueBusy, setCueBusy] = useState(false)
  const [cueError, setCueError] = useState('')
  const [fixtureCue, setFixtureCue] = useState(false)
  const [audioState, setAudioState] = useState<'IDLE' | 'PLAYED' | 'BLOCKED_HARDWARE'>('IDLE')
  const [error, setError] = useState('')

  const cueQa = useMemo(
    () => [...qaPairs].reverse().find((q) => q.question.trim() === question.trim() && q.fastCue),
    [qaPairs, question],
  )
  const cue = useMemo(() => buildFastCueViewModel(cueQa?.fastCue), [cueQa])
  const cueReady = Boolean(cue || fixtureCue)
  const complete = Boolean(feedback && cueReady)

  useEffect(() => {
    if (complete) onCompleted()
  }, [complete, onCompleted])

  const start = async () => {
    if (practiceId || busy) return
    setBusy(true)
    setError('')
    try {
      const res = await productApi.startPractice({
        goal_id: goalId,
        round: 'TECHNICAL',
        personas: ['TECH_LEAD'],
        demeanor: 'FRIENDLY',
        difficulty: 'WARMUP',
        sources: ['ROLE_BANK'],
        questions: 1,
        language: 'zh',
        human_coach: false,
        guided: true,
        delivery_analytics: true,
      })
      setPracticeId(res.practice_id)
      setQuestion(res.question.question)
    } catch (e) {
      setError(getErrorMessage(e, '无法开始第一次演练'))
    } finally {
      setBusy(false)
    }
  }

  const playQuestion = () => {
    if (!question) return
    try {
      if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
        setAudioState('BLOCKED_HARDWARE')
        return
      }
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(question)
      utterance.lang = 'zh-CN'
      utterance.rate = 0.95
      utterance.onend = () => setAudioState('PLAYED')
      utterance.onerror = () => setAudioState('BLOCKED_HARDWARE')
      window.speechSynthesis.speak(utterance)
    } catch {
      setAudioState('BLOCKED_HARDWARE')
    }
  }

  const requestCue = async () => {
    if (!question || cueBusy) return
    setCueBusy(true)
    setCueError('')
    setFixtureCue(false)
    try {
      await api.ask(question)
    } catch (e) {
      setCueError(getErrorMessage(e, 'Fast Cue 链路暂时不可用'))
    } finally {
      setCueBusy(false)
    }
  }

  const submit = async () => {
    if (!practiceId || !answer.trim() || busy) return
    setBusy(true)
    setError('')
    try {
      const res = await productApi.answerPractice(practiceId, { answer: answer.trim() })
      setFeedback(res.feedback)
      if (res.report) setReport(res.report)
      else setReport(await productApi.finishPractice(practiceId))
    } catch (e) {
      setError(getErrorMessage(e, '提交演练失败'))
    } finally {
      setBusy(false)
    }
  }

  const tryOverlay = async () => {
    const electron = window.electronAPI
    if (!electron?.syncOverlayWindow) {
      setOverlayState('UNAVAILABLE')
      return
    }
    try {
      await electron.setOverlayLayout?.({ dock: 'TOP', interaction: 'INTERACTIVE', size: 'COMPACT' })
      await electron.syncOverlayWindow({
        enabled: true,
        visible: true,
        mode: 'prompt',
        opacity: 0.92,
        fontSize: 16,
        fontColor: '#ffffff',
        showBg: false,
        maxLines: 4,
      })
      setOverlayState('OPENED')
    } catch {
      setOverlayState('ERROR')
    }
  }

  const saveQuickNote = async () => {
    if (!quickNote.trim() || quickNoteSaved) return
    setBusy(true)
    setError('')
    try {
      await productApi.createQuickNote({
        title: '第一次演练速记',
        content: quickNote.trim(),
        scope: goalId ? 'GOAL' : 'GLOBAL',
        goal_id: goalId,
        pinned: true,
        tags: ['ONBOARDING'],
      })
      setQuickNoteSaved(true)
    } catch (e) {
      setError(getErrorMessage(e, '速记保存失败'))
    } finally {
      setBusy(false)
    }
  }

  const tryScreenshot = async () => {
    const capture = window.electronAPI?.captureRegion
    if (!capture) {
      setScreenshotState('UNAVAILABLE')
      return
    }
    try {
      await capture()
      setScreenshotState('TRIED')
    } catch {
      setScreenshotState('UNAVAILABLE')
    }
  }

  if (!practiceId) {
    return (
      <div className="space-y-3" data-testid="guided-first-practice">
        <p>最后跑一次 5 分钟内的完整小演练：真实 Practice 问题 → Fast Cue → 你的回答 → 内容/表达反馈。</p>
        <p className="text-xs text-text-muted">前面的麦克风、系统音频和 STT 检查负责硬件链路；这里验证成竹的产品闭环。没有音频硬件时可以用测试语音/文本继续，但会明确标成 fallback。</p>
        <button type="button" onClick={() => void start()} disabled={busy}
          className="rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">
          {busy ? '正在准备…' : '开始第一次演练'}
        </button>
        {error ? <p role="alert" className="text-xs text-status-risk">{error}</p> : null}
      </div>
    )
  }

  return (
    <div className="space-y-3" data-testid="guided-first-practice">
      <div className="rounded-xl border border-bg-hover/60 bg-bg-tertiary/20 p-3">
        <p className="text-[11px] text-text-muted">测试面试官问题</p>
        <p className="mt-1 font-medium text-text-primary" data-testid="guided-question">{question}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" onClick={playQuestion} className="inline-flex items-center gap-1 rounded-lg border border-bg-hover px-2.5 py-1 text-xs text-text-secondary hover:bg-bg-hover/60">
            <Play className="h-3.5 w-3.5" aria-hidden /> 播放测试问题
          </button>
          <button type="button" onClick={() => void requestCue()} disabled={cueBusy}
            className="inline-flex items-center gap-1 rounded-lg bg-accent-blue px-2.5 py-1 text-xs font-medium text-white disabled:opacity-50">
            <Sparkles className="h-3.5 w-3.5" aria-hidden /> {cueBusy ? '请求中…' : '生成 Fast Cue'}
          </button>
        </div>
        {audioState === 'PLAYED' ? <p className="mt-1 text-[11px] text-status-direct">测试问题已通过系统语音播放。</p> : null}
        {audioState === 'BLOCKED_HARDWARE' ? <p className="mt-1 text-[11px] text-status-inferred">当前环境无法播放测试语音（BLOCKED_HARDWARE）；可以继续用文字完成演练。</p> : null}
      </div>

      {cue ? (
        <div className="rounded-xl border border-status-direct/30 bg-status-direct/5 p-3" data-testid="guided-fast-cue">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
            <CheckCircle2 className="h-3.5 w-3.5 text-status-direct" aria-hidden /> Fast Cue 已就绪
            {cue.ttfugUserMs != null ? <span className="font-normal text-text-muted">· {cue.ttfugUserMs}ms</span> : null}
          </div>
          {cue.direction ? <p className="mt-1 text-xs text-text-secondary">{cue.direction}</p> : null}
          <ul className="mt-1.5 space-y-1">
            {cue.cues.map((item) => (
              <li key={item.text} className="text-xs text-text-primary">
                • {item.text}<span className="ml-1 text-[10px] text-text-muted">[{CUE_SOURCE_LABELS[item.source]}]</span>
              </li>
            ))}
          </ul>
        </div>
      ) : fixtureCue ? (
        <div className="rounded-xl border border-status-inferred/30 bg-status-inferred/5 p-3" data-testid="guided-fast-cue-fallback">
          <p className="text-xs font-semibold text-text-primary">Fixture fallback（不是实时模型证据）</p>
          <ul className="mt-1 text-xs text-text-secondary">
            <li>• 先给结论，再讲 2–3 个依据</li>
            <li>• 只引用你真正做过的经历</li>
          </ul>
        </div>
      ) : null}

      {cueError ? (
        <div className="rounded-xl border border-status-risk/30 p-2 text-xs">
          <p role="alert" className="text-status-risk">{cueError}</p>
          <button type="button" className="mt-1 text-accent-blue underline" onClick={() => setFixtureCue(true)}>使用标记明确的示例 Cue 继续</button>
        </div>
      ) : null}

      <div>
        <label className="text-xs font-medium text-text-secondary" htmlFor="guided-answer">你的回答</label>
        <textarea id="guided-answer" aria-label="第一次演练回答" value={answer} onChange={(e) => setAnswer(e.target.value)}
          placeholder="按刚才的 Cue，用自己的话回答…" className="mt-1 min-h-[88px] w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1.5 text-sm text-text-primary" />
        <button type="button" onClick={() => void submit()} disabled={busy || !answer.trim()}
          className="mt-2 rounded-lg bg-container-primary px-3 py-1.5 text-xs font-semibold text-container-on-primary disabled:opacity-50">
          {busy ? '分析中…' : '提交演练'}
        </button>
      </div>

      {feedback ? (
        <div className="grid gap-2 sm:grid-cols-2" data-testid="guided-feedback">
          <section className="rounded-xl border border-bg-hover/60 p-2">
            <h3 className="text-xs font-semibold text-text-primary">内容</h3>
            {(feedback.content.findings ?? []).slice(0, 2).map((f) => (
              <p key={f.signal} className="mt-1 text-[11px] text-text-secondary">{f.finding}<span className="block text-accent-blue">下一步：{f.action}</span></p>
            ))}
            {!feedback.content.findings?.length ? <p className="mt-1 text-[11px] text-text-secondary">内容维度没有明显缺口。</p> : null}
          </section>
          <section className="rounded-xl border border-bg-hover/60 p-2">
            <h3 className="text-xs font-semibold text-text-primary">表达</h3>
            {feedback.delivery?.advice?.length ? feedback.delivery.advice.slice(0, 2).map((a) => <p key={a} className="mt-1 text-[11px] text-text-secondary">{a}</p>)
              : <p className="mt-1 text-[11px] text-text-secondary">本次没有明显表达问题。</p>}
          </section>
        </div>
      ) : null}

      {cueReady ? (
        <section className="rounded-xl border border-bg-hover/60 bg-bg-tertiary/15 p-3" aria-label="第一次演练辅助工具">
          <h3 className="text-xs font-semibold text-text-primary">顺手试一下上场工具</h3>
          <p className="mt-0.5 text-[11px] text-text-muted">Overlay、速记和截图不是完成演练的硬门槛；不可用时会明确标记，不会伪装成功。</p>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg border border-bg-hover/50 p-2">
              <button type="button" onClick={() => void tryOverlay()} className="inline-flex items-center gap-1 text-xs font-medium text-accent-blue">
                <MonitorUp className="h-3.5 w-3.5" aria-hidden /> 打开 Compact Overlay
              </button>
              <p className="mt-1 text-[10px] text-text-muted" data-testid="guided-overlay-state">
                {overlayState === 'OPENED' ? 'Overlay 已打开；上场时 Cue 会出现在这里。'
                  : overlayState === 'UNAVAILABLE' ? '当前浏览器环境没有 Electron Overlay；安装版中可用。'
                    : overlayState === 'ERROR' ? 'Overlay 打开失败；进入设置 → Live & Overlay 可重试。'
                      : '可选：先看一下上场时的 Compact Overlay。'}
              </p>
            </div>
            <div className="rounded-lg border border-bg-hover/50 p-2">
              <label className="text-[11px] font-medium text-text-secondary" htmlFor="guided-note">速记一条容易忘的点</label>
              <div className="mt-1 flex gap-1.5">
                <input id="guided-note" aria-label="第一次演练速记" value={quickNote} disabled={quickNoteSaved}
                  onChange={(e) => setQuickNote(e.target.value)} placeholder="例如：Redis 没做过 Cluster"
                  className="min-w-0 flex-1 rounded-lg border border-bg-hover bg-bg-primary px-2 py-1 text-xs text-text-primary" />
                <button type="button" disabled={!quickNote.trim() || quickNoteSaved || busy} onClick={() => void saveQuickNote()}
                  className="inline-flex items-center gap-1 rounded-lg border border-bg-hover px-2 py-1 text-[11px] text-text-secondary disabled:opacity-40">
                  <NotebookPen className="h-3 w-3" aria-hidden /> {quickNoteSaved ? '已保存' : '存入速记'}
                </button>
              </div>
            </div>
          </div>
          <button type="button" onClick={() => void tryScreenshot()} className="mt-2 text-[11px] text-text-muted underline decoration-dotted">
            测试截图区域（可选，会让你选择一个区域）
          </button>
          {screenshotState !== 'IDLE' ? <span className="ml-2 text-[10px] text-text-muted">
            {screenshotState === 'TRIED' ? '已完成一次区域选择。' : '当前环境不支持区域截图；不影响完成。'}
          </span> : null}
        </section>
      ) : null}

      {report ? (
        <section className="rounded-xl border border-accent-blue/25 bg-accent-blue/5 p-3" data-testid="guided-reflection">
          <p className="text-xs font-semibold text-text-primary">第一次演练复盘</p>
          <p className="mt-1 text-[11px] text-text-muted">这不是综合分；只告诉你下一轮具体该保留和改什么。</p>
          {report.went_well?.slice(0, 2).map((x) => <p key={x} className="mt-1 text-[11px] text-status-direct">✓ {x}</p>)}
          {report.to_improve?.slice(0, 2).map((x) => <p key={x} className="mt-1 text-[11px] text-status-inferred">→ {x}</p>)}
          {!report.went_well?.length && !report.to_improve?.length ? <p className="mt-1 text-[11px] text-text-secondary">本场已保存；以后每场都会进入 Reflection，再回写到 Goal 的 Next Focus。</p> : null}
        </section>
      ) : null}

      {complete ? (
        <p role="status" data-testid="guided-practice-complete" className="flex items-center gap-1.5 text-xs font-medium text-status-direct">
          <CheckCircle2 className="h-4 w-4" aria-hidden /> 第一次演练已跑通，可以进入成竹。
        </p>
      ) : !cueReady ? (
        <p className="flex items-center gap-1.5 text-[11px] text-text-muted"><CircleAlert className="h-3.5 w-3.5" aria-hidden /> 先生成 Fast Cue，再提交回答。</p>
      ) : null}

      {error ? <p role="alert" className="text-xs text-status-risk">{error}</p> : null}
    </div>
  )
}
