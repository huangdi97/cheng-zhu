import { useCallback, useEffect, useRef, useState } from 'react'
import dayjs from 'dayjs'
import { Mic, MicOff, Activity, Volume2, Radio, Languages, ClipboardPaste, Keyboard, Brain, ArrowDown } from 'lucide-react'
import { useInterviewStore } from '@/stores/configStore'

export default function TranscriptionPanel() {
  const transcriptions = useInterviewStore((s) => s.transcriptions)
  const transcriptionTimes = useInterviewStore((s) => s.transcriptionTimes)
  const candidateTranscriptions = useInterviewStore((s) => s.candidateTranscriptions)
  const interviewerPartial = useInterviewStore((s) => s.interviewerPartial)
  const isRecording = useInterviewStore((s) => s.isRecording)
  const audioLevel = useInterviewStore((s) => s.audioLevel)
  const isTranscribing = useInterviewStore((s) => s.isTranscribing)
  const config = useInterviewStore((s) => s.config)
  const translationsByQuestion = useInterviewStore((s) => s.translationsByQuestion)
  const isExamMode = config?.written_exam_mode === true
  const contentRef = useRef<HTMLDivElement>(null)
  const autoFollowRef = useRef(true)
  const [showJumpToLatest, setShowJumpToLatest] = useState(false)

  const updateAutoFollow = useCallback(() => {
    const el = contentRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= 36
    autoFollowRef.current = nearBottom
    setShowJumpToLatest(!nearBottom && transcriptions.length > 0)
  }, [transcriptions.length])

  const scrollToLatest = useCallback((behavior: ScrollBehavior = 'smooth') => {
    const el = contentRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior })
    autoFollowRef.current = true
    setShowJumpToLatest(false)
  }, [])

  useEffect(() => {
    if (!autoFollowRef.current) {
      setShowJumpToLatest(transcriptions.length > 0)
      return
    }
    requestAnimationFrame(() => scrollToLatest('auto'))
  }, [scrollToLatest, transcriptions])

  useEffect(() => {
    updateAutoFollow()
  }, [updateAutoFollow])

  const levelPercent = Math.min(audioLevel * 500, 100)

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-bg-tertiary/60 flex-shrink-0">
        <div className="flex items-center gap-2">
          {isRecording ? (
            <div className="relative">
              <Mic className="w-4 h-4 text-accent-green" />
              <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-accent-green recording-pulse" />
            </div>
          ) : (
            <MicOff className="w-4 h-4 text-text-muted" />
          )}
          <span className="text-sm font-semibold tracking-tight">
            {isRecording ? (isExamMode ? '答题中' : '正在录音') : (isExamMode ? '答题记录' : '实时转录')}
          </span>
        </div>
        {isRecording && (
          <div className="flex items-center gap-2.5 ml-auto">
            {isTranscribing && (
              <span className="flex items-center gap-1 text-xs text-accent-amber font-medium">
                <Activity className="w-3 h-3 animate-pulse" />
                转写中
              </span>
            )}
            <div className="flex items-end gap-[2px] h-4">
              {[0.6, 1.0, 0.75, 0.9, 0.5].map((scale, i) => (
                <div
                  key={i}
                  className="w-[3px] rounded-full bg-accent-green/80 transition-all duration-75"
                  style={{
                    height: `${Math.max(15, Math.min(100, levelPercent * scale))}%`,
                    opacity: levelPercent > 5 ? 0.5 + (levelPercent / 200) : 0.2,
                  }}
                />
              ))}
            </div>
            <span className="text-[10px] text-text-muted font-mono tabular-nums w-8 text-right">
              {Math.round(levelPercent)}%
            </span>
          </div>
        )}
      </div>

      <div
        ref={contentRef}
        aria-label="转写记录"
        className="relative flex-1 overflow-y-auto p-4 md:p-5 space-y-2.5"
        onScroll={updateAutoFollow}
      >
        {transcriptions.length === 0 && candidateTranscriptions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-4">
            <div className="relative w-14 h-14">
              <div className={`absolute inset-0 rounded-2xl bg-gradient-to-br from-accent-blue/15 to-accent-green/10 ${isRecording ? 'animate-glow' : ''}`} />
              <div className="relative flex items-center justify-center w-14 h-14 rounded-2xl bg-bg-tertiary/50">
                {isRecording ? (
                  <Activity className="w-6 h-6 text-accent-amber animate-pulse" />
                ) : (
                  <Mic className="w-6 h-6 text-text-muted/60" />
                )}
              </div>
            </div>
            <div className="text-center space-y-1">
              <p className="text-text-primary text-sm font-semibold">
                {isRecording ? (isExamMode ? '等待截图或手动输入…' : '等待语音输入…') : (isExamMode ? '笔试答题记录' : '实时语音转录')}
              </p>
              <p className="text-text-muted text-xs leading-relaxed">
                {isRecording
                  ? isExamMode
                    ? '截图审题或手动输入问题后，AI 会自动生成答案'
                    : '检测到语音会自动分段转录,问题会发给 AI 生成答案'
                  : isExamMode
                  ? '点击「开始笔试」，通过截图或输入题目获取答案'
                  : '选择音频设备后,点击「开始面试」启动实时识别'}
              </p>
            </div>
            {!isRecording && (
              <div className="flex items-center gap-1.5 flex-wrap justify-center pt-1">
                {(isExamMode
                  ? [
                      { icon: ClipboardPaste, label: '截图审题', hint: '输入框 Ctrl/⌘+V 粘贴' },
                      { icon: Keyboard, label: '手动输入', hint: '底部输入框 + Enter' },
                      { icon: Brain, label: 'AI 答题', hint: '自动识别题目类型并生成答案' },
                    ]
                  : [
                      { icon: Volume2, label: '会议拾音', hint: '优先选 BlackHole / 系统音频 (loopback), 可录远端声音' },
                      { icon: Radio, label: '自动断句', hint: 'VAD 静音超阈值即切段并识别' },
                      { icon: Languages, label: '中英混读', hint: '默认中文优先, 英文术语保留原样' },
                    ]
                ).map(({ icon: Icon, label, hint }: { icon: typeof Mic; label: string; hint: string }) => (
                  <span
                    key={label}
                    title={hint}
                    className="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded-full bg-bg-tertiary/50 border border-bg-hover/40 text-text-secondary"
                  >
                    <Icon className="w-3 h-3 text-accent-blue/70" />
                    {label}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
          {transcriptions.map((text, i) => {
            const translation = translationsByQuestion[text.trim()]
            const ts = transcriptionTimes[i]
            return (
              <div
                key={i}
                className="transcription-item px-3.5 py-2.5 rounded-lg bg-bg-tertiary/40 text-sm leading-relaxed text-text-primary"
                style={{ animationDelay: `${Math.min(i * 30, 300)}ms` }}
              >
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="inline-flex items-center gap-1 rounded-full bg-accent-blue/10 border border-accent-blue/25 text-accent-blue text-[10px] font-medium px-1.5 py-0.5">
                    <Mic className="w-2.5 h-2.5" />
                    面试官
                  </span>
                  <span className="text-[10px] font-mono text-text-muted tabular-nums">{String(i + 1).padStart(2, '0')}</span>
                  {ts ? <span className="text-[10px] font-mono text-text-muted tabular-nums ml-auto">{dayjs(ts * 1000).format('HH:mm:ss')}</span> : null}
                </div>
                <div className="whitespace-pre-wrap">{text}</div>
                {translation && (
                  <div className="mt-1.5 pt-1.5 border-t border-bg-hover/40 text-xs text-text-secondary leading-relaxed">
                    <span className="inline-flex items-center gap-1 text-[10px] text-accent-blue/70 mr-1.5">
                      <Languages className="w-3 h-3" />
                      {translation.to === '中文' ? '译文' : 'Translation'}
                    </span>
                    {translation.translated}
                  </div>
                )}
              </div>
            )
          })}
          {candidateTranscriptions.length > 0 && (
            <div className="pt-2 mt-1 border-t border-bg-hover/40">
              <div className="text-[10px] font-semibold text-text-muted uppercase tracking-wider px-1 pb-1.5">
                你的口述
              </div>
              {candidateTranscriptions.map((text, i) => (
                <div
                  key={`c-${i}`}
                  className="transcription-item px-3.5 py-2.5 rounded-lg bg-accent-green/5 border border-accent-green/15 text-sm leading-relaxed text-text-primary mb-2"
                >
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="inline-flex items-center gap-1 rounded-full bg-accent-green/10 border border-accent-green/25 text-accent-green text-[10px] font-medium px-1.5 py-0.5">
                      <Volume2 className="w-2.5 h-2.5" />
                      你自己
                    </span>
                  </div>
                  <div className="whitespace-pre-wrap">{text}</div>
                </div>
              ))}
            </div>
          )}
          </>
        )}
        {interviewerPartial && (
          <div className="px-3.5 py-2.5 rounded-lg bg-accent-blue/10 border border-accent-blue/30 text-sm leading-relaxed text-accent-blue">
            <div className="inline-flex items-center gap-1.5 text-[10px] text-accent-blue/70 mb-1">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-blue animate-pulse" />
              正在识别…
            </div>
            <div className="whitespace-pre-wrap">{interviewerPartial}</div>
          </div>
        )}

        {showJumpToLatest && (
          <button
            type="button"
            onClick={() => scrollToLatest()}
            className="sticky bottom-2 left-1/2 z-10 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-accent-blue/35 bg-bg-secondary/95 px-3 py-1.5 text-[11px] font-medium text-accent-blue shadow-lg shadow-black/10 backdrop-blur"
            aria-label="回到最新转写"
          >
            <ArrowDown className="h-3 w-3" />
            回到最新转写
          </button>
        )}
      </div>
    </div>
  )
}
