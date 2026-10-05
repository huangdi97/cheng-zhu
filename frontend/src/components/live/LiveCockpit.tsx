/**
 * Live Cockpit 3.0 (canonical §17). First layer: Question · Fast Cue ·
 * Source/Warning (AnswerPanel's cue-first card). One status line. Second
 * layer: deep answer, transcript, screen, references, coach, quick notes.
 * Session end returns to Reflection.
 *
 * Moved out of App.tsx (v1.2 assist view) without changing the v1.2 core
 * panels; v1.3 adds the status line, companion actions, Nudge and Closing.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Camera, MonitorSmartphone, Mic, NotebookPen, Pin } from 'lucide-react'
import { api } from '@/lib/api'
import { deriveLiveStatus, LIVE_STATUS_LABELS } from '@/lib/guidanceViewModel'
import { setLiveContextLabel } from '@/lib/liveContext'
import { navigate, paths } from '@/lib/router'
import { productApi, track } from '@/lib/productApi'
import { useAssistSplit } from '@/hooks/useAssistSplit'
import { useInterviewStore } from '@/stores/configStore'
import { useOsStore } from '@/stores/osStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'
import TranscriptionPanel from '@/components/TranscriptionPanel'
import MemoPanel from '@/components/MemoPanel'
import AnswerPanel from '@/components/AnswerPanel'
import ControlBar from '@/components/ControlBar'
import CopilotHintPanel from '@/components/CopilotHintPanel'
import LivePackBar from '@/components/live/LivePackBar'
import SessionClaimWarnings from '@/components/live/SessionClaimWarnings'
import CoachCues from '@/components/coach/CoachCues'
import QuestionBoundaryPanel from '@/components/QuestionBoundaryPanel'
import ScreenshotModePanel from '@/components/ScreenshotModePanel'
import { NudgeBar, ClosingPanel } from './LiveCompanions'

function LiveStatusLine() {
  const isRecording = useInterviewStore((s) => s.isRecording)
  const wsConnected = useInterviewStore((s) => s.wsConnected)
  const qaPairs = useInterviewStore((s) => s.qaPairs)
  const streamingIds = useInterviewStore((s) => s.streamingIds)
  const live = useOsStore((s) => s.live)
  const setQuickNotes = useOsStore((s) => s.setQuickNotes)
  const setPin = useOsStore((s) => s.setPinDialog)
  const latest = qaPairs[qaPairs.length - 1] ?? null
  const streaming = latest ? streamingIds.includes(latest.id) : false
  const ageMs = latest?.timestamp ? Date.now() - latest.timestamp : null
  const status = deriveLiveStatus({ isRecording, wsConnected, qa: latest, streaming, questionAgeMs: ageMs })
  const tone = status === 'RECONNECTING' ? 'text-status-risk' : status === 'CUE_READY' ? 'text-status-direct' : 'text-text-secondary'
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-bg-tertiary/70 bg-bg-secondary/40 px-3 py-1.5 md:px-5" data-testid="live-status-line">
      <span role="status" aria-live="polite" className={`inline-flex items-center gap-1.5 text-xs font-medium ${tone}`}>
        <span className={`h-2 w-2 rounded-full ${isRecording ? 'bg-accent-green' : 'bg-text-muted'}`} aria-hidden />
        {LIVE_STATUS_LABELS[status]}
      </span>
      {live?.goalTitle ? <span className="truncate text-xs text-text-muted">· {live.goalTitle}</span> : <span className="text-xs text-text-muted">· 未关联目标</span>}
      <span className="ml-auto flex items-center gap-1">
        <button type="button" data-testid="live-quick-notes" onClick={() => { setQuickNotes(true); track('quick_note_opened_in_live', {}, { goal_id: live?.goalId ?? '' }) }}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-text-secondary hover:bg-bg-hover" title="速记（只读）">
          <NotebookPen className="h-3.5 w-3.5" aria-hidden /> 速记
        </button>
        <button type="button" onClick={() => setPin(true)} disabled={!live}
          className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-text-secondary hover:bg-bg-hover disabled:opacity-40" title="标记这一刻 (Ctrl+P)">
          <Pin className="h-3.5 w-3.5" aria-hidden /> 标记
        </button>
      </span>
    </div>
  )
}

/** Cue signals for v1.4 (local): rendered + candidate speaking within 10 s after a cue. */
function useCueSignals() {
  const qaPairs = useInterviewStore((s) => s.qaPairs)
  const candidateTranscriptions = useInterviewStore((s) => s.candidateTranscriptions)
  const live = useOsStore((s) => s.live)
  const seen = useRef<Set<string>>(new Set())
  const lastCueAt = useRef<number>(0)
  const lastCandidateLen = useRef(candidateTranscriptions.length)
  useEffect(() => {
    for (const qa of qaPairs) {
      if (qa.fastCue && !seen.current.has(qa.id)) {
        seen.current.add(qa.id)
        lastCueAt.current = Date.now()
        track('fast_cue_rendered', {}, { goal_id: live?.goalId ?? '', session_id: live?.sessionId ?? '' })
      }
    }
  }, [qaPairs, live])
  useEffect(() => {
    if (candidateTranscriptions.length > lastCandidateLen.current && lastCueAt.current && Date.now() - lastCueAt.current < 10000) {
      track('speech_after_cue', {}, { session_id: live?.sessionId ?? '' })
      lastCueAt.current = 0
    }
    lastCandidateLen.current = candidateTranscriptions.length
  }, [candidateTranscriptions, live])
}

/** Recording stopped on a Go Live session → attach review and open Reflection. */
function useSessionEnd() {
  const isRecording = useInterviewStore((s) => s.isRecording)
  const live = useOsStore((s) => s.live)
  const setLive = useOsStore((s) => s.setLive)
  const wasRecording = useRef(false)
  useEffect(() => {
    if (isRecording) {
      wasRecording.current = true
      return
    }
    if (!wasRecording.current || !live) return
    wasRecording.current = false
    const ending = live
    // review rows are written when the assist loop stops; give it a moment
    const timer = window.setTimeout(() => {
      productApi.liveEnd(ending.sessionId).then((res) => {
        setLive(null)
        setLiveContextLabel('')
        if (res.reflection_ref) navigate(paths.reflection(res.reflection_ref.session_kind, res.reflection_ref.session_ref))
        else if (ending.goalId) navigate(paths.goal(ending.goalId, 'interviews'))
      }).catch(() => undefined)
    }, 1500)
    return () => window.clearTimeout(timer)
  }, [isRecording, live, setLive])
}

export default function LiveCockpit() {
  const config = useInterviewStore((s) => s.config)
  const currentStreamingId = useInterviewStore((s) => s.currentStreamingId)
  const isExamMode = config?.written_exam_mode === true
  const assistMode = useUiPrefsStore((s) => s.assistMode)
  const setAssistMode = useUiPrefsStore((s) => s.setAssistMode)
  const assistTranscriptCollapsed = useUiPrefsStore((s) => s.assistTranscriptCollapsed)
  const memoVisible = useOsStore((s) => s.memoVisible)
  const [mobileTab, setMobileTab] = useState<'transcript' | 'answer'>('answer')
  const lastMobileStreamingIdRef = useRef<string | null>(null)
  const [serverScreenLoading, setServerScreenLoading] = useState(false)
  const serverScreenAskRef = useRef(false)
  const { assistSplitContainerRef, assistSplitDragging, assistSplitPct, assistSplitPctRef, persistAssistSplitPct } = useAssistSplit()
  useCueSignals()
  useSessionEnd()

  // v1.3 is cue-first on every viewport. A new question/answer stream should
  // bring the mobile user to the glanceable Cue/Answer layer instead of
  // leaving them on transcript. The user can always switch back explicitly.
  useEffect(() => {
    // During the very first layout pass some surfaces report width 0: treat as unknown, not mobile.
    const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 0
    const isMobileViewport = viewportWidth > 0 && viewportWidth < 768
    if (isMobileViewport && currentStreamingId && currentStreamingId !== lastMobileStreamingIdRef.current) {
      setMobileTab('answer')
    }
    lastMobileStreamingIdRef.current = currentStreamingId
  }, [currentStreamingId])

  const handleServerScreenAsk = useCallback(async () => {
    if (serverScreenAskRef.current) return
    serverScreenAskRef.current = true
    setServerScreenLoading(true)
    try {
      await api.askFromServerScreen()
      useInterviewStore.getState().setToastMessage('已按当前截图区域配置提交服务端截图审题，请在答案区查看')
    } catch (e: unknown) {
      useInterviewStore.getState().setToastMessage(e instanceof Error ? e.message : '提交失败')
    } finally {
      serverScreenAskRef.current = false
      setServerScreenLoading(false)
    }
  }, [])

  return (
    <>
      <LiveStatusLine />
      <div className="flex items-center gap-1.5 px-3 md:px-5 py-2 border-b border-bg-tertiary/70 bg-bg-secondary/40 flex-shrink-0">
        <button type="button" onClick={() => setAssistMode('voice')} aria-pressed={assistMode === 'voice'}
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${assistMode === 'voice' ? 'bg-container-primary text-container-on-primary font-semibold' : 'text-text-muted hover:text-text-primary'}`}>
          <Mic className="w-3.5 h-3.5" aria-hidden />
          语音模式
        </button>
        <button type="button" onClick={() => setAssistMode('screenshot')} aria-pressed={assistMode === 'screenshot'}
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${assistMode === 'screenshot' ? 'bg-container-primary text-container-on-primary font-semibold' : 'text-text-muted hover:text-text-primary'}`}>
          <Camera className="w-3.5 h-3.5" aria-hidden />
          截图模式
        </button>
      </div>
      <LivePackBar />
      {assistMode === 'voice' ? (
        <>
          <SessionClaimWarnings />
          <CoachCues />
          <div className="flex md:hidden border-b border-bg-tertiary flex-shrink-0" role="tablist" aria-label="实时辅助面板">
            <button role="tab" aria-selected={mobileTab === 'transcript'} onClick={() => setMobileTab('transcript')}
              className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${mobileTab === 'transcript' ? 'text-accent-blue border-b-2 border-accent-blue' : 'text-text-muted'}`}>
              {isExamMode ? '答题记录' : '实时转录'}
            </button>
            <button role="tab" aria-selected={mobileTab === 'answer'} onClick={() => setMobileTab('answer')}
              className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${mobileTab === 'answer' ? 'text-accent-blue border-b-2 border-accent-blue' : 'text-text-muted'}`}>
              提示与回答
            </button>
          </div>

          <div ref={assistSplitContainerRef} className="flex-1 hidden md:flex overflow-hidden min-h-0">
            {!assistTranscriptCollapsed && (
              <>
                <div className="flex flex-col min-w-0 flex-shrink-0 border-r border-bg-tertiary animate-slide-left"
                  style={{ width: `${assistSplitPct}%`, minWidth: '220px', maxWidth: '62%' }}>
                  <TranscriptionPanel />
                </div>
                <div
                  role="separator"
                  aria-orientation="vertical"
                  aria-label="拖动调节转录区与答案区宽度"
                  aria-valuemin={24}
                  aria-valuemax={62}
                  aria-valuenow={Math.round(assistSplitPct)}
                  tabIndex={0}
                  className="w-1 flex-shrink-0 cursor-col-resize group relative z-10 outline-none focus-visible:ring-2 focus-visible:ring-accent-blue/50 focus-visible:ring-inset bg-bg-hover/30 hover:bg-accent-blue/20 active:bg-accent-blue/40 transition-all duration-150"
                  title="拖动调节左右宽度；双击恢复默认比例"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    assistSplitDragging.current = true
                    document.body.style.cursor = 'col-resize'
                    document.body.style.userSelect = 'none'
                  }}
                  onDoubleClick={(e) => {
                    e.preventDefault()
                    assistSplitPctRef.current = 32
                    persistAssistSplitPct(32)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                      e.preventDefault()
                      const c = Math.min(62, Math.max(24, assistSplitPctRef.current + (e.key === 'ArrowLeft' ? -2 : 2)))
                      assistSplitPctRef.current = c
                      persistAssistSplitPct(c)
                    }
                    if (e.key === 'Home' || e.key === 'End') {
                      e.preventDefault()
                      const c = e.key === 'Home' ? 24 : 62
                      assistSplitPctRef.current = c
                      persistAssistSplitPct(c)
                    }
                  }}
                >
                  <span className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-bg-hover group-hover:bg-accent-blue/50 pointer-events-none" aria-hidden />
                </div>
              </>
            )}
            <div className="flex-1 flex flex-col min-w-0 min-h-0">
              <AnswerPanel />
            </div>
            {memoVisible && (
              <div className="flex flex-col w-72 flex-shrink-0 border-l border-bg-tertiary min-w-0 min-h-0 animate-slide-left">
                <MemoPanel />
              </div>
            )}
          </div>

          <div className="flex-1 flex md:hidden overflow-hidden min-h-0">
            {mobileTab === 'transcript' ? <TranscriptionPanel /> : <AnswerPanel />}
          </div>

          {/* 仅手机端：由服务端截本机主屏左半幅送 VL，手机不调用系统截图 */}
          {mobileTab === 'answer' && (
            <div className="md:hidden flex-shrink-0 px-3 py-3 border-t border-bg-tertiary bg-bg-secondary/95 backdrop-blur-sm">
              <button type="button" disabled={serverScreenLoading} onClick={handleServerScreenAsk}
                className="w-full flex items-center justify-center gap-3 min-h-[52px] py-3.5 rounded-xl bg-accent-blue text-white text-base font-semibold shadow-sm disabled:opacity-60 active:scale-[0.99] transition-transform">
                <MonitorSmartphone className="w-5 h-5 flex-shrink-0" />
                {serverScreenLoading ? '截图审题提交中…' : '服务端截图审题'}
              </button>
              <p className="text-[10px] text-text-muted text-center mt-1.5 leading-snug px-0.5">
                仅在当前会话允许 AI 辅助、且你有权处理屏幕内容时使用。截图按当前区域设置发送给你配置的视觉模型；本地访问日志开关只影响日志噪声，不改变会话政策或隐私边界。
              </p>
            </div>
          )}

          <ClosingPanel />
          <NudgeBar />
          <QuestionBoundaryPanel />
          <CopilotHintPanel />
          <ControlBar />
        </>
      ) : (
        <ScreenshotModePanel serverScreenLoading={serverScreenLoading} onAsk={handleServerScreenAsk} />
      )}
    </>
  )
}
