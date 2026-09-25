import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import {
  Play,
  Square,
  Trash2,
  Send,
  X,
  Ellipsis,
  Zap,
  SpellCheck,
  AlertTriangle,
  Image as ImageIcon,
  Pause,
  PlayCircle,
  Loader2,
  BookOpen,
  Mic,
  Volume2,
  MessageSquarePlus,
} from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'
import { api, getErrorMessage } from '@/lib/api'
import { updateConfigAndRefresh } from '@/lib/configSync'
import { showExamOverlayPrompt } from '@/lib/examOverlay'
import { ResumeMountInline } from '@/components/resume/ResumeMount'
import { AudioDevicePicker } from './control-bar/AudioDevicePicker'
import { QuickPromptsRow } from './control-bar/QuickPromptsRow'
import { WsReconnectingBanner } from './control-bar/WsReconnectingBanner'
import { splitAudioDevices } from './control-bar/audioDevices'
import {
  bumpQuickPromptRecent,
  getQuickPrompts,
  orderByRecent,
  readQuickPromptRecent,
} from './control-bar/quickPrompts'

export {
  DEFAULT_QUICK_PROMPTS,
  RECENT_KEY,
  STORAGE_KEY,
  getQuickPrompts,
  saveQuickPrompts,
} from './control-bar/quickPrompts'

function getEnabledVisionModels(config: { models?: Array<{ name?: string; supports_vision?: boolean; enabled?: boolean }> } | null | undefined) {
  return (config?.models ?? []).filter((model) => model.enabled !== false && model.supports_vision)
}

export default function ControlBar() {
  // 精确订阅字段, 避免 store 任意字段(LLM token / audioLevel 等)变化触发 ControlBar 重渲染
  const {
    isRecording,
    isPaused,
    devices,
    setDevices,
    config,
    platformInfo,
    clearSession,
    streamingIds,
    qaPairs,
    transcriptions,
    interviewerPartial,
    candidateTranscriptions,
    candidatePartial,
    audioLevel,
    candidateAudioLevel,
    setToastMessage,
    lastWSError,
    setLastWSError,
    wsConnected,
    modelHealth,
    sttLoaded,
    sttLoading,
    sttActiveProvider,
    candidateSttLoaded,
    candidateSttLoading,
    candidateSttProvider,
  } = useInterviewStore(
    useShallow((s) => ({
      isRecording: s.isRecording,
      isPaused: s.isPaused,
      devices: s.devices,
      setDevices: s.setDevices,
      config: s.config,
      platformInfo: s.platformInfo,
      clearSession: s.clearSession,
      streamingIds: s.streamingIds,
      qaPairs: s.qaPairs,
      transcriptions: s.transcriptions,
      interviewerPartial: s.interviewerPartial,
      candidateTranscriptions: s.candidateTranscriptions,
      candidatePartial: s.candidatePartial,
      audioLevel: s.audioLevel,
      candidateAudioLevel: s.candidateAudioLevel,
      setToastMessage: s.setToastMessage,
      lastWSError: s.lastWSError,
      setLastWSError: s.setLastWSError,
      wsConnected: s.wsConnected,
      modelHealth: s.modelHealth,
      sttLoaded: s.sttLoaded ?? true,
      sttLoading: s.sttLoading ?? false,
      sttActiveProvider: s.sttActiveProvider ?? '',
      candidateSttLoaded: s.candidateSttLoaded ?? false,
      candidateSttLoading: s.candidateSttLoading ?? false,
      candidateSttProvider: s.candidateSttProvider ?? '',
    })),
  )
  const [selectedDevice, setSelectedDevice] = useState<number | null>(null)
  const [selectedCandidateMic, setSelectedCandidateMic] = useState<number | null>(null)
  const [manualQuestion, setManualQuestion] = useState('')
  const [pastedImage, setPastedImage] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [cancellingAsk, setCancellingAsk] = useState(false)
  const [asking, setAsking] = useState(false)
  const [refreshingDevices, setRefreshingDevices] = useState(false)
  const [testingOutput, setTestingOutput] = useState(false)
  const [testingInput, setTestingInput] = useState(false)
  const [inputMeterOpen, setInputMeterOpen] = useState(false)
  const [inputLevel, setInputLevel] = useState<{ level_pct: number; rms: number; peak: number; has_signal: boolean; error?: string | null } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [moreOpen, setMoreOpen] = useState(false)
  const moreRef = useRef<HTMLDivElement>(null)

  const enabledModelEntries = useMemo(
    () => (config?.models ?? []).map((model, index) => ({ model, index })).filter(({ model }) => model.enabled !== false),
    [config?.models],
  )
  const isExamMode = config?.written_exam_mode === true
  const noEnabledModels = (config?.models?.length ?? 0) > 0 && enabledModelEntries.length === 0
  const allModelsUnavailable = enabledModelEntries.length > 0 &&
    enabledModelEntries.every(({ index }) => modelHealth[index] === 'error')
  const enabledVisionModels = useMemo(() => getEnabledVisionModels(config), [config])
  const hasEnabledVisionModel = enabledVisionModels.length > 0
  const answerModelUnavailable = noEnabledModels || allModelsUnavailable
  const showColdStartHint =
    !isExamMode &&
    !isRecording &&
    transcriptions.length === 0 &&
    qaPairs.length === 0 &&
    (devices.length === 0 || selectedDevice === null)
  const showExamStartHint = isExamMode && !isRecording && qaPairs.length === 0
  const autoAnswerMode = config?.assist_auto_answer_mode ?? (config?.auto_detect ? 'smart' : 'off')
  const handleSetAutoAnswerMode = async (mode: 'off' | 'smart' | 'always') => {
    try {
      await updateConfigAndRefresh({ assist_auto_answer_mode: mode, auto_detect: mode !== 'off' })
      setToastMessage({
        off: '已关闭自动回答：仅保留转录',
        smart: '自动回答模式：智能判断，高置信度问题自动回答',
        always: '自动回答模式：全自动，有效问句直接进入队列',
      }[mode])
    } catch (e) {
      setToastMessage(getErrorMessage(e, '切换失败'))
    }
  }

  const handleToggleConcise = async () => {
    const next = !config?.assist_realtime_concise_answer
    try {
      await updateConfigAndRefresh({ assist_realtime_concise_answer: next })
      setToastMessage(next ? '回答长度已切换为简短：优先生成可直接说出口的话术' : '回答长度已切换为详细')
    } catch (e) {
      setToastMessage(getErrorMessage(e, '切换失败'))
    }
  }

  const handleToggleCorrection = async () => {
    const next = !config?.assist_answer_correction_enabled
    try {
      await updateConfigAndRefresh({ assist_answer_correction_enabled: next })
      setToastMessage(next ? '已开启答前纠错：回答前会用 LLM 修正转写错字/缺字（略慢 ~0.5s）' : '已关闭答前纠错（更快）')
    } catch (e) {
      setToastMessage(getErrorMessage(e, '切换失败'))
    }
  }

  const inputRef = useRef<HTMLInputElement>(null)
  const isComposingRef = useRef(false)
  const askingRef = useRef(false)
  const lifecycleActionRef = useRef(false)
  const clearingRef = useRef(false)
  const cancellingAskRef = useRef(false)
  const cancellingAskResetTimerRef = useRef<number | null>(null)
  const refreshingDevicesRef = useRef(false)
  const testingOutputRef = useRef(false)
  const testingInputRef = useRef(false)
  const inputMonitorStartSeqRef = useRef(0)
  const selectedCandidateMicRef = useRef<number | null>(null)
  const [quickPrompts, setQuickPrompts] = useState<string[]>(getQuickPrompts)
  const [quickPromptRecent, setQuickPromptRecent] = useState<Record<string, number>>(readQuickPromptRecent)
  const orderedQuickPrompts = useMemo(
    () => orderByRecent(quickPrompts, quickPromptRecent),
    [quickPrompts, quickPromptRecent],
  )
  const [quickPromptSessionUsed, setQuickPromptSessionUsed] = useState<Set<string>>(new Set())
  const recentSet = quickPromptSessionUsed

  const visibleDevices = useMemo(() => splitAudioDevices(devices).visible, [devices])
  const candidateMicDevices = useMemo(() => devices.filter((device) => !device.is_loopback), [devices])

  // WebSocket 从断开恢复时 toast 通知,避免用户误以为系统没反应
  const prevWsConnectedRef = useRef(wsConnected)
  useEffect(() => {
    if (!prevWsConnectedRef.current && wsConnected) {
      setToastMessage('连接已恢复')
    }
    prevWsConnectedRef.current = wsConnected
  }, [wsConnected, setToastMessage])

  useEffect(() => {
    const onStorage = () => setQuickPrompts(getQuickPrompts())
    window.addEventListener('storage', onStorage)
    window.addEventListener('quick-prompts-updated', onStorage)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('quick-prompts-updated', onStorage)
    }
  }, [])

  const selectedIsLoopback = devices.find((d) => d.id === selectedDevice)?.is_loopback ?? false
  const selectedCandidateDevice = devices.find((d) => d.id === selectedCandidateMic) ?? null
  selectedCandidateMicRef.current = selectedCandidateMic
  const selectedCandidateIsMic = selectedCandidateDevice?.is_loopback === false
  const candidateCaptureEnabled = config?.candidate_asr_enabled ?? false
  const candidateMicMatchesMeetingAudio = Boolean(
    !isExamMode &&
    candidateCaptureEnabled &&
    selectedDevice !== null &&
    selectedCandidateMic !== null &&
    selectedDevice === selectedCandidateMic,
  )
  const effectiveCandidateMic = !isExamMode &&
    candidateCaptureEnabled &&
    selectedCandidateMic !== null &&
    selectedCandidateMic !== selectedDevice
    ? selectedCandidateMic
    : null
  const hasLoopback = devices.some((d) => d.is_loopback)
  const activeModel = config?.models?.[config.active_model]
  const activeModelSupportsVision = activeModel?.supports_vision ?? false
  const pastedImageVisionHint = activeModelSupportsVision
    ? null
    : hasEnabledVisionModel
      ? `当前优先模型不支持图片，将自动使用「${enabledVisionModels[0]?.name ?? '识图模型'}」`
      : '没有已启用的识图模型，请先在设置中开启带 👁 的模型'

  useEffect(() => {
    if (devices.length === 0) {
      if (selectedDevice !== null) setSelectedDevice(null)
      return
    }
    if (selectedDevice !== null && devices.some((d) => d.id === selectedDevice)) return
    const defaultDevices = visibleDevices.length > 0 ? visibleDevices : devices
    const loopback = defaultDevices.find((d) => d.is_loopback && d.is_default_output) ?? defaultDevices.find((d) => d.is_loopback)
    setSelectedDevice(loopback?.id ?? defaultDevices[0]?.id ?? null)
  }, [devices, visibleDevices, selectedDevice])

  useEffect(() => {
    if (devices.length === 0) {
      if (selectedCandidateMic !== null) setSelectedCandidateMic(null)
      return
    }
    if (selectedCandidateMic !== null && devices.some((d) => d.id === selectedCandidateMic && !d.is_loopback)) {
      if (selectedDevice !== null && selectedCandidateMic === selectedDevice) {
        const alternativeMic = candidateMicDevices.find((d) => d.id !== selectedDevice)
        if (alternativeMic) setSelectedCandidateMic(alternativeMic.id)
      }
      return
    }
    const mic = candidateMicDevices.find((d) => d.id !== selectedDevice) ?? candidateMicDevices[0]
    setSelectedCandidateMic(mic?.id ?? null)
  }, [devices, candidateMicDevices, selectedCandidateMic, selectedDevice])

  useEffect(() => {
    setInputLevel(null)
  }, [selectedCandidateMic])

  useEffect(() => {
    if (!inputMeterOpen) return
    let cancelled = false
    const poll = async () => {
      try {
        const status = await api.audioInputMonitorStatus()
        if (cancelled) return
        setInputLevel({
          level_pct: status.level_pct ?? 0,
          rms: status.rms ?? 0,
          peak: status.peak ?? 0,
          has_signal: Boolean(status.has_signal),
          error: status.error,
        })
      } catch (e: unknown) {
        if (!cancelled) {
          setInputLevel((prev) => ({ ...(prev ?? { level_pct: 0, rms: 0, peak: 0, has_signal: false }), error: getErrorMessage(e, '读取麦克风音量失败') }))
        }
      }
    }
    void poll()
    const timer = window.setInterval(poll, 120)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      void api.audioInputMonitorStop().catch(() => undefined)
    }
  }, [inputMeterOpen])

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        e.preventDefault()
        const file = items[i].getAsFile()
        if (!file) continue
        const store = useInterviewStore.getState()
        if ((store.config?.models?.length ?? 0) > 0 && getEnabledVisionModels(store.config).length === 0) {
          setError('请先在设置中启用至少一个带 👁 的识图模型，再粘贴截图')
          return
        }
        const reader = new FileReader()
        reader.onload = (ev) => {
          const result = ev.target?.result as string
          if (result) setPastedImage(result)
        }
        reader.readAsDataURL(file)
        return
      }
    }
  }, [])

  const handleStart = useCallback(async () => {
    if (lifecycleActionRef.current) return
    if (!isExamMode && selectedDevice === null) { setError('请先选择音频设备'); return }
    lifecycleActionRef.current = true
    setLoading(true); setError(null)
    try {
      await api.start(
        isExamMode ? null : selectedDevice,
        effectiveCandidateMic,
      )
      if (isExamMode) {
        showExamOverlayPrompt()
        return
      }
      const s = useUiPrefsStore.getState()
      if (s.interviewOverlayEnabled && window.electronAPI?.syncOverlayWindow) {
        window.electronAPI.syncOverlayWindow({
          enabled: true,
          visible: true,
          opacity: s.interviewOverlayOpacity,
          fontSize: s.interviewOverlayFontSize,
          fontColor: s.interviewOverlayFontColor,
          showBg: s.interviewOverlayShowBg,
          mode: s.interviewOverlayMode,
          focusWidthPct: s.interviewOverlayFocusWidthPct,
          focusHeightPct: s.interviewOverlayFocusHeightPct,
          promptMaxWidth: s.interviewOverlayPromptMaxWidth,
          promptAutoFollow: s.interviewOverlayPromptAutoFollow,
          maxLines: s.interviewOverlayMaxLines,
        }).catch(() => {})
      }
    }
    catch (e: unknown) { setError(getErrorMessage(e, isExamMode ? '开始失败' : '开始面试失败')) }
    finally {
      lifecycleActionRef.current = false
      setLoading(false)
    }
  }, [selectedDevice, effectiveCandidateMic, isExamMode])
  const handleStop = useCallback(async () => {
    if (lifecycleActionRef.current) return
    if (isRecording && !window.confirm(isExamMode ? '结束本次笔试？当前答案会保留在页面上。' : '结束本次面试？将停止录音，当前转录与答案会保留在页面上。')) return
    lifecycleActionRef.current = true
    setLoading(true)
    try {
      await api.stop()
      window.electronAPI?.syncOverlayWindow?.({ visible: false }).catch(() => {})
    } catch (e: unknown) {
      setError(`结束${isExamMode ? '笔试' : '面试'}失败：${getErrorMessage(e)}`)
    } finally {
      lifecycleActionRef.current = false
      setLoading(false)
    }
  }, [isExamMode, isRecording])
  const handlePause = useCallback(async () => {
    if (lifecycleActionRef.current) return
    lifecycleActionRef.current = true
    setLoading(true)
    try { await api.pause() } catch (e: unknown) { setError(getErrorMessage(e, '暂停失败')) } finally {
      lifecycleActionRef.current = false
      setLoading(false)
    }
  }, [])

  useEffect(() => () => {
    if (cancellingAskResetTimerRef.current !== null) {
      window.clearTimeout(cancellingAskResetTimerRef.current)
      cancellingAskResetTimerRef.current = null
    }
    cancellingAskRef.current = false
  }, [])
  const handleResume = useCallback(async () => {
    if (lifecycleActionRef.current) return
    lifecycleActionRef.current = true
    setLoading(true)
    try { await api.resume(selectedDevice ?? undefined, effectiveCandidateMic) } catch (e: unknown) { setError(getErrorMessage(e, isExamMode ? '继续失败' : '继续录音失败')) } finally {
      lifecycleActionRef.current = false
      setLoading(false)
    }
  }, [selectedDevice, effectiveCandidateMic, isExamMode])
  const handleClear = useCallback(async () => {
    if (clearingRef.current) return
    if (qaPairs.length > 0 || transcriptions.length > 0 || candidateTranscriptions.length > 0) {
      if (!window.confirm('确定要清空当前页的转录与答案吗？清空后不可恢复。')) return
    }
    clearingRef.current = true
    setClearing(true)
    try {
      await api.clear()
      clearSession()
      setToastMessage('已清空')
    } catch (e: unknown) { setError(getErrorMessage(e, '清空失败')) }
    finally {
      clearingRef.current = false
      setClearing(false)
    }
  }, [qaPairs.length, transcriptions.length, candidateTranscriptions.length, clearSession, setToastMessage])

  const handleCancelAsk = useCallback(async () => {
    if (cancellingAskRef.current) return
    cancellingAskRef.current = true
    setCancellingAsk(true)
    try {
      await api.cancelAsk()
      setToastMessage('已发送取消')
    } catch (e: unknown) {
      setError(`取消生成失败：${getErrorMessage(e)}`)
    }
    if (cancellingAskResetTimerRef.current !== null) {
      window.clearTimeout(cancellingAskResetTimerRef.current)
    }
    cancellingAskResetTimerRef.current = window.setTimeout(() => {
      cancellingAskResetTimerRef.current = null
      cancellingAskRef.current = false
      setCancellingAsk(false)
    }, 500)
  }, [setToastMessage])

  const submitAsk = useCallback(async (text: string, image?: string | null) => {
    if (askingRef.current) return
    if (!text.trim() && !image) return
    if (noEnabledModels) {
      setError('请先在设置中启用至少一个模型')
      return
    }
    if (allModelsUnavailable) {
      setError('所有启用模型不可用，请先检查模型连接')
      return
    }
    if (image && !hasEnabledVisionModel) {
      setError('请先在设置中启用至少一个识图模型')
      return
    }
    askingRef.current = true
    setAsking(true)
    try {
      await api.ask(text.trim(), image || undefined)
      setManualQuestion('')
      setPastedImage(null)
    } catch (e: unknown) {
      setError(getErrorMessage(e, '提交问题失败'))
    } finally {
      askingRef.current = false
      setAsking(false)
    }
  }, [noEnabledModels, allModelsUnavailable, hasEnabledVisionModel])

  const handleAsk = useCallback(() => {
    void submitAsk(manualQuestion, pastedImage)
  }, [manualQuestion, pastedImage, submitAsk])

  // 成竹「空发最新问题」：把刚转录到的面试官问题直接发给 AI，不用手动打字。
  const latestAskText = useMemo(() => {
    const live = (interviewerPartial ?? '').trim()
    if (live) return live
    const last = transcriptions[transcriptions.length - 1]
    if (last) return last
    const candLive = (candidatePartial ?? '').trim()
    if (candLive) return candLive
    return candidateTranscriptions[candidateTranscriptions.length - 1] ?? ''
  }, [interviewerPartial, transcriptions, candidatePartial, candidateTranscriptions])

  const handleAskLatest = useCallback(() => {
    const text = latestAskText.trim()
    if (!text) return
    void submitAsk(text)
    inputRef.current?.focus()
  }, [latestAskText, submitAsk])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (isComposingRef.current) return
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk() }
  }, [handleAsk])

  // 成竹全局快捷键：Ctrl/Cmd + Enter 用最新转录提问
  useEffect(() => {
    const onGlobalKey = (e: KeyboardEvent) => {
      if (e.key !== 'Enter' || !(e.ctrlKey || e.metaKey)) return
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
      if (isExamMode) return
      if (!latestAskText.trim()) return
      e.preventDefault()
      handleAskLatest()
    }
    window.addEventListener('keydown', onGlobalKey)
    return () => window.removeEventListener('keydown', onGlobalKey)
  }, [handleAskLatest, latestAskText, isExamMode])

  const handleQuickPromptPick = useCallback((prompt: string) => {
    setManualQuestion((prev) => (prev ? `${prev} ${prompt}` : prompt))
    inputRef.current?.focus()
    setQuickPromptRecent(bumpQuickPromptRecent(prompt))
    setQuickPromptSessionUsed((prev) => new Set(prev).add(prompt))
  }, [])

  const handleRefreshDevices = useCallback(async () => {
    if (refreshingDevicesRef.current) return
    refreshingDevicesRef.current = true
    setRefreshingDevices(true)
    setError(null)
    try {
      const next = await api.getDevices()
      setDevices(next.devices ?? [], next.platform ?? null)
      setToastMessage(isExamMode ? '设备已刷新' : '音频设备已刷新')
    } catch (e: unknown) {
      setError(getErrorMessage(e, '刷新音频设备失败'))
    } finally {
      refreshingDevicesRef.current = false
      setRefreshingDevices(false)
    }
  }, [isExamMode, setDevices, setToastMessage])

  const handleOutputTest = useCallback(async () => {
    if (testingOutputRef.current) return
    if (isRecording && !isPaused) {
      setError('请先暂停或结束面试，再测试音频输出')
      return
    }
    testingOutputRef.current = true
    setTestingOutput(true)
    setError(null)
    try {
      await api.audioOutputTest()
      setToastMessage('已播放测试音频，请确认扬声器能听到声音')
    } catch (e: unknown) {
      setError(getErrorMessage(e, '测试音频输出失败'))
    } finally {
      testingOutputRef.current = false
      setTestingOutput(false)
    }
  }, [isRecording, isPaused, setToastMessage])

  const handleOpenInputMeter = useCallback(async () => {
    if (testingInputRef.current) return
    if (selectedCandidateMic === null) {
      setError('请先选择麦克风')
      return
    }
    if (isRecording && !isPaused) {
      setError('请先暂停或结束面试，再测试麦克风输入')
      return
    }
    const targetDeviceId = selectedCandidateMic
    const startSeq = inputMonitorStartSeqRef.current + 1
    inputMonitorStartSeqRef.current = startSeq
    const isCurrentStart = () =>
      inputMonitorStartSeqRef.current === startSeq &&
      selectedCandidateMicRef.current === targetDeviceId
    testingInputRef.current = true
    setTestingInput(true)
    setError(null)
    setInputLevel({ level_pct: 0, rms: 0, peak: 0, has_signal: false })
    try {
      const status = await api.audioInputMonitorStart(targetDeviceId)
      if (!isCurrentStart()) {
        void api.audioInputMonitorStop().catch(() => undefined)
        return
      }
      setInputLevel({
        level_pct: status.level_pct ?? 0,
        rms: status.rms ?? 0,
        peak: status.peak ?? 0,
        has_signal: Boolean(status.has_signal),
        error: status.error,
      })
      setInputMeterOpen(true)
    } catch (e: unknown) {
      if (isCurrentStart()) {
        setError(getErrorMessage(e, '测试麦克风输入失败'))
      }
    } finally {
      if (inputMonitorStartSeqRef.current === startSeq) {
        testingInputRef.current = false
        setTestingInput(false)
      }
    }
  }, [selectedCandidateMic, isRecording, isPaused])

  const handleCloseInputMeter = useCallback(() => {
    setInputMeterOpen(false)
  }, [])

  // 模态对话框：Esc 关闭（可访问性）
  useEffect(() => {
    if (!inputMeterOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') handleCloseInputMeter()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [inputMeterOpen, handleCloseInputMeter])

  // 「更多」弹层：点击外部 / Esc 关闭
  useEffect(() => {
    if (!moreOpen) return
    const onDown = (e: MouseEvent) => {
      if (!moreRef.current?.contains(e.target as Node)) setMoreOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMoreOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [moreOpen])

  const inputLevelPct = inputLevel ? Math.max(0, Math.min(100, Math.round(inputLevel.level_pct ?? 0))) : 0

  return (
    <div className="control-bar px-3 md:px-5 py-2.5 flex-shrink-0 space-y-1.5">
      {showColdStartHint && (
        <div className="flex items-center gap-2 text-xs text-accent-amber bg-accent-amber/10 px-3 py-1.5 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>
            {devices.length === 0
              ? '正在检测音频设备…如长时间未出现，请检查麦克风/系统音频权限'
              : '请先选择音频设备，再点击「开始」开始面试。'}
          </span>
        </div>
      )}
      {showExamStartHint && (
        <div className="flex items-center gap-2 text-xs text-accent-blue bg-accent-blue/10 px-3 py-1.5 rounded-lg">
          <BookOpen className="w-3.5 h-3.5 flex-shrink-0" />
          <span>点击「开始笔试」进入答题模式，可通过截图或手动输入提问</span>
        </div>
      )}
      {isRecording && !isExamMode && (
        <div className="flex items-center gap-3 rounded-lg border border-bg-hover/40 bg-bg-tertiary/40 px-3 py-1.5" role="meter" aria-label="实时输入电平">
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <span className="w-9 shrink-0 text-[10px] text-text-muted">面试官</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-hover">
              <div className="h-full rounded-full bg-accent-blue transition-all duration-150" style={{ width: `${Math.min(100, Math.max(2, Math.round(audioLevel * 2500)))}%` }} />
            </div>
          </div>
          <div className="flex items-center gap-1.5 flex-1 min-w-0">
            <span className="w-9 shrink-0 text-[10px] text-text-muted">我</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-hover">
              <div className="h-full rounded-full bg-accent-green transition-all duration-150" style={{ width: `${Math.min(100, Math.max(2, Math.round(candidateAudioLevel * 2500)))}%` }} />
            </div>
          </div>
        </div>
      )}
      {!wsConnected && <WsReconnectingBanner />}
      {allModelsUnavailable && (
        <div className="flex items-center gap-2 text-xs text-accent-red bg-accent-red/10 px-3 py-1.5 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>所有启用模型不可用，请检查 API 与网络。</span>
        </div>
      )}
      {noEnabledModels && (
        <div className="flex items-center gap-2 text-xs text-accent-red bg-accent-red/10 px-3 py-1.5 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>未启用任何模型，请在设置中开启至少一个模型。</span>
        </div>
      )}
      {!isExamMode && !hasLoopback && platformInfo?.needs_virtual_device && (
        <div className="flex items-start gap-2 text-xs text-accent-amber bg-accent-amber/10 px-3 py-2 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <div>
            <span className="font-medium">未检测到系统音频设备。</span>
            <span className="text-text-muted"> 当前只有麦克风，无法录制面试官的声音。</span>
            <span className="text-accent-blue cursor-pointer" onClick={() => useInterviewStore.getState().toggleSettings()}> 查看配置说明</span>
          </div>
        </div>
      )}
      {!isExamMode && selectedDevice !== null && !selectedIsLoopback && hasLoopback && (
        <div className="flex items-center gap-2 text-xs text-accent-amber bg-accent-amber/10 px-3 py-1.5 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>你选择的是麦克风，建议选择带 ⟳ 标记的系统音频设备</span>
        </div>
      )}
      {!isExamMode && candidateCaptureEnabled && selectedCandidateMic === null && (
        <div className="flex items-center gap-2 text-xs text-accent-amber bg-accent-amber/10 px-3 py-1.5 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>未选择“我的麦克风”：不会把你的回答写入复盘，追问也只能参考助手建议答案</span>
        </div>
      )}
      {!isExamMode && candidateCaptureEnabled && selectedCandidateMic !== null && !selectedCandidateIsMic && (
        <div className="flex items-center gap-2 text-xs text-accent-amber bg-accent-amber/10 px-3 py-1.5 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>“我的麦克风”建议选择普通麦克风，不要选择系统音频设备</span>
        </div>
      )}
      {candidateMicMatchesMeetingAudio && (
        <div className="flex items-center gap-2 text-xs text-accent-amber bg-accent-amber/10 px-3 py-1.5 rounded-lg">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>“我的麦克风”和会议音频相同，本次不会单独记录你的回答；请选择系统音频/虚拟声卡作为会议音频。</span>
        </div>
      )}
      {lastWSError && (
        <div className="flex items-center gap-2 text-xs text-accent-red bg-accent-red/10 px-3 py-1.5 rounded-lg">
          <span>{lastWSError}</span>
          <button onClick={() => setLastWSError(null)} className="ml-auto" aria-label="关闭"><X className="w-3 h-3" /></button>
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 text-xs text-accent-red bg-accent-red/10 px-3 py-1.5 rounded-lg">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto" aria-label="关闭错误"><X className="w-3 h-3" /></button>
        </div>
      )}

      {/* Image preview */}
      {pastedImage && (() => {
        return (
          <div className="flex items-center gap-2 px-3 py-1.5 bg-bg-tertiary/50 rounded-lg">
            <img src={pastedImage} alt="screenshot" className="h-12 max-w-[200px] rounded object-contain border border-bg-hover" />
            <div className="flex flex-col gap-0.5">
              <span className="text-xs text-text-muted">已粘贴截图</span>
              {pastedImageVisionHint && (
                <span className={`text-[10px] ${hasEnabledVisionModel ? 'text-accent-amber' : 'text-accent-red'}`}>
                  {pastedImageVisionHint}
                </span>
              )}
            </div>
            <button onClick={() => setPastedImage(null)} aria-label="移除已粘贴截图" className="text-text-muted hover:text-accent-red ml-auto">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )
      })()}

      {/* 移动端：录制中时显示状态指示条 */}
      {isRecording && (
        <div className={`flex md:hidden items-center justify-between px-3 py-1.5 rounded-lg text-xs font-medium ${isPaused ? 'bg-accent-amber/15 text-accent-amber' : 'bg-accent-green/15 text-accent-green'}`}>
          <div className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${isPaused ? 'bg-accent-amber' : 'bg-accent-green animate-pulse'}`} />
            <span>{isPaused ? '已暂停' : isExamMode ? '答题中' : '录制中'}</span>
          </div>
        </div>
      )}
      {!isExamMode && candidatePartial && (
        <div className="flex items-start gap-2 text-xs text-accent-blue bg-accent-blue/10 px-3 py-1.5 rounded-lg">
          <Mic className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 animate-pulse" />
          <span className="min-w-0 break-all">正在识别我的回答：{candidatePartial}</span>
        </div>
      )}

      {!isExamMode && candidateTranscriptions.length > 0 && (
        <div className="flex items-start gap-2 text-xs text-accent-green bg-accent-green/10 px-3 py-1.5 rounded-lg">
          <Mic className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
          <span className="min-w-0 break-all">我的回答记录：{candidateTranscriptions[candidateTranscriptions.length - 1]}</span>
        </div>
      )}

      {/* 主控制行 */}
      <div className="grid gap-2 rounded-xl bg-bg-secondary p-2.5 lg:grid-cols-[minmax(0,38rem)_auto] lg:items-stretch">
        {!isExamMode && (
          <div className="grid w-full min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 lg:max-w-[38rem]">
            <div className="flex min-w-0 flex-col gap-1 lg:max-w-[19rem]">
              <span className="text-[10px] font-medium text-text-muted leading-none">会议音频 · 听面试官</span>
              <p className="text-[10px] text-text-muted/80 leading-snug truncate">电脑会议选 ★系统音频；电话会议选麦克风（手机开免提放电脑旁）</p>
              <AudioDevicePicker
                devices={devices}
                selectedDevice={selectedDevice}
                onSelect={setSelectedDevice}
                onRefresh={handleRefreshDevices}
                refreshing={refreshingDevices}
                selectionDisabled={isRecording && !isPaused}
                ariaLabel="选择会议音频设备"
                placeholder="选择会议音频"
                action={{
                  ariaLabel: '测试音频输出',
                  title: isRecording && !isPaused ? '录制中请先暂停' : '播放一段测试音频',
                  icon: <Volume2 className="w-3.5 h-3.5" />,
                  loading: testingOutput,
                  disabled: isRecording && !isPaused,
                  onClick: handleOutputTest,
                }}
              />
            </div>
            {candidateCaptureEnabled ? (
              <div className="flex min-w-0 flex-col gap-1 lg:max-w-[19rem]">
                <span className="text-[10px] font-medium text-text-muted leading-none">
                  我的麦克风 · 记录我的回答
                  {candidateSttLoading && <Loader2 className="w-3 h-3 animate-spin inline ml-1 text-accent-blue" />}
                  {!candidateSttLoading && candidateSttLoaded && <span className="text-accent-green ml-1">✓</span>}
                </span>
                <p className="text-[10px] text-text-muted/80 leading-snug truncate">用你的麦克风记录口述，便于复盘与追问</p>
                <AudioDevicePicker
                  devices={candidateMicDevices}
                  selectedDevice={selectedCandidateMic}
                  onSelect={setSelectedCandidateMic}
                  onRefresh={handleRefreshDevices}
                  refreshing={refreshingDevices}
                  selectionDisabled={isRecording && !isPaused}
                  ariaLabel="选择我的麦克风"
                  placeholder="选择我的麦克风"
                  action={{
                    ariaLabel: '测试麦克风输入',
                    title: isRecording && !isPaused ? '录制中请先暂停' : '打开实时输入音量测试',
                    icon: <Mic className="w-3.5 h-3.5" />,
                    loading: testingInput,
                    disabled: selectedCandidateMic === null || (isRecording && !isPaused),
                    onClick: handleOpenInputMeter,
                  }}
                />
              </div>
            ) : (
              <div className="flex min-w-0 flex-col gap-1 lg:max-w-[19rem]">
                <span className="text-[10px] font-medium text-text-muted leading-none">我的麦克风 · 记录我的回答</span>
                <p className="text-[10px] text-text-muted/80 leading-snug truncate">在设置中开启「我的回答记录」后可用麦克风记录口述</p>
                <div
                  role="status"
                  aria-label="我的回答记录状态"
                  className="flex h-10 min-w-0 items-center justify-between gap-2 rounded-lg border border-bg-hover bg-bg-tertiary px-3"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <Mic className="w-3.5 h-3.5 text-text-muted flex-shrink-0" />
                    <span className="min-w-0 truncate text-xs font-medium text-text-secondary">
                      我的回答记录已关闭
                      <span className="hidden lg:inline text-text-muted"> · 不影响会议音频</span>
                    </span>
                  </div>
                  <button
                    type="button"
                    aria-label="打开我的回答记录设置"
                    className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-accent-blue transition-colors hover:bg-accent-blue/10"
                    onClick={() => useInterviewStore.getState().toggleSettings()}
                  >
                    设置
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        <div className="flex h-full min-h-[56px] w-full min-w-0 flex-wrap items-center gap-1.5 lg:w-auto lg:max-w-[34rem] lg:border-l lg:border-bg-hover/40 lg:pl-2.5">
        {isRecording ? (
          <>
            {isPaused ? (
              <button onClick={handleResume} disabled={loading}
                className="flex min-h-[38px] items-center gap-1.5 rounded-lg px-3.5 py-2 btn-primary text-xs font-semibold disabled:opacity-50 flex-shrink-0" style={{ background: 'linear-gradient(135deg, rgb(var(--c-accent-green)), rgb(var(--c-accent-green) / 0.85))' }}>
                <PlayCircle className="w-3.5 h-3.5" />
                <span>继续</span>
              </button>
            ) : (
              <button onClick={handlePause} disabled={loading}
                className="flex min-h-[38px] items-center gap-1.5 rounded-lg px-3.5 py-2 text-white text-xs font-semibold transition-all duration-150 disabled:opacity-50 flex-shrink-0" style={{ background: 'linear-gradient(135deg, rgb(var(--c-accent-amber)), rgb(var(--c-accent-amber) / 0.85))' }}>
                <Pause className="w-3.5 h-3.5" />
                <span>暂停</span>
              </button>
            )}
            <button onClick={handleStop} disabled={loading}
              aria-label={isExamMode ? '结束' : '结束面试'}
              className="flex min-h-[38px] items-center gap-1.5 rounded-lg px-3.5 py-2 btn-danger text-xs font-semibold disabled:opacity-50 flex-shrink-0">
              <Square className="w-3.5 h-3.5" />
              <span className="sm:hidden">结束</span>
              <span className="hidden sm:inline">{isExamMode ? '结束' : '结束面试'}</span>
            </button>
          </>
        ) : !isExamMode && sttLoading ? (
          <button disabled
            className="flex min-h-[38px] items-center gap-1.5 rounded-lg px-4 py-2 bg-bg-tertiary text-text-muted text-xs font-semibold cursor-not-allowed flex-shrink-0">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            <span>{sttActiveProvider === 'whisper' ? '降级加载 Whisper…' : '语音加载中…'}</span>
          </button>
        ) : !isExamMode && !sttLoaded ? (
          <button onClick={handleStart} disabled={loading || selectedDevice === null}
            className="flex min-h-[38px] items-center gap-1.5 rounded-lg px-4 py-2 btn-primary text-xs font-semibold disabled:opacity-50 flex-shrink-0">
            <AlertTriangle className="w-3.5 h-3.5" />
            <span>语音未就绪，开始面试</span>
          </button>
        ) : (
          <button onClick={handleStart} disabled={loading || (!isExamMode && selectedDevice === null)}
            className="flex min-h-[38px] items-center gap-1.5 rounded-lg px-4 py-2 btn-primary text-xs font-semibold disabled:opacity-50 flex-shrink-0">
            <Play className="w-3.5 h-3.5" />
            <span>{isExamMode ? '开始笔试' : '开始面试'}</span>
          </button>
        )}

        {!isExamMode && <ResumeMountInline className="bg-bg-primary/45" />}

        {streamingIds.length > 0 && (
          <button onClick={handleCancelAsk} disabled={cancellingAsk}
            className="flex items-center gap-1 min-h-[36px] min-w-[36px] justify-center px-2 py-2 bg-accent-amber/20 hover:bg-accent-amber/30 text-accent-amber text-xs rounded-lg transition-colors flex-shrink-0 disabled:opacity-50"
            aria-label={cancellingAsk ? '正在取消生成' : '取消正在生成的回答'}
            title="取消全部正在生成的回答">
            {cancellingAsk ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <X className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">
              {cancellingAsk ? '取消中' : streamingIds.length > 1 ? `取消生成 (${streamingIds.length})` : '取消生成'}
            </span>
          </button>
        )}
        </div>
      </div>

      {/* 快捷提示词 */}
      {quickPrompts.length > 0 && (
        <QuickPromptsRow
          prompts={orderedQuickPrompts}
          recentSet={recentSet}
          onPick={handleQuickPromptPick}
        />
      )}

      {/* 手动提问输入行 */}
      <div className="flex items-center gap-1.5">
        <div className="relative flex-1">
          <input ref={inputRef} type="text" value={manualQuestion}
            onChange={(e) => setManualQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            onCompositionStart={() => { isComposingRef.current = true }}
            onCompositionEnd={() => { setTimeout(() => { isComposingRef.current = false }, 0) }}
            onPaste={handlePaste}
            placeholder={pastedImage ? "可添加文字说明（可选），Enter 发送" : "输入问题，Enter 发送…"}
            className="w-full bg-bg-tertiary/60 text-text-primary text-xs rounded-xl px-3.5 py-2.5 border border-bg-hover/50 focus:outline-none focus:border-accent-blue/50 focus:ring-1 focus:ring-accent-blue/20 placeholder:text-text-muted/60 pr-8 transition-all duration-200" />
          {pastedImage && (
            <ImageIcon className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-accent-green" />
          )}
        </div>
        {!isExamMode && latestAskText.trim() && (
          <button
            type="button"
            onClick={handleAskLatest}
            disabled={asking}
            title="用最新转录的问题直接提问（把刚听到的问题发给 AI，不用手动打字）"
            aria-label="用最新转录提问"
            className="inline-flex items-center justify-center h-10 w-10 rounded-xl border border-bg-hover/50 bg-bg-tertiary/40 text-text-muted hover:bg-accent-blue/10 hover:text-accent-blue transition-colors flex-shrink-0"
          >
            <MessageSquarePlus className="w-4 h-4" />
          </button>
        )}
        <button
          onClick={handleAsk}
          disabled={asking || answerModelUnavailable || (pastedImage && !hasEnabledVisionModel) || (!manualQuestion.trim() && !pastedImage)}
          title={
            asking
              ? '正在提交问题'
              : noEnabledModels
              ? '请先在设置中启用至少一个模型'
              : allModelsUnavailable
              ? '所有启用模型不可用，请先检查模型连接'
              : pastedImage && !hasEnabledVisionModel
              ? '请先在设置中启用至少一个带 👁 的识图模型'
              : manualQuestion.trim() || pastedImage
              ? '发送问题 (Enter)'
              : '请先输入问题或粘贴截图'
          }
          aria-label="发送问题"
          className="px-3 py-2.5 btn-primary text-xs rounded-xl disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
        >
          {asking ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
        </button>
        {/* 更多操作：自动回答 / 答前纠错 / 清空内容 */}
        <div className="relative flex-shrink-0" ref={moreRef}>
          <button
            type="button"
            onClick={() => setMoreOpen((v) => !v)}
            aria-haspopup="menu"
            aria-expanded={moreOpen}
            aria-label="更多操作"
            title="更多操作：自动回答 / 答前纠错 / 清空内容"
            className={`inline-flex items-center justify-center h-10 w-10 rounded-xl border transition-colors ${
              moreOpen
                ? 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue'
                : 'border-bg-hover/50 bg-bg-tertiary/40 text-text-muted hover:bg-bg-tertiary/70 hover:text-text-primary'
            }`}
          >
            <Ellipsis className="w-4 h-4" />
          </button>
          {moreOpen && (
            <div
              role="menu"
              aria-label="更多操作"
              className="absolute right-0 bottom-full mb-2 z-50 w-64 glass-popover rounded-xl p-1.5 animate-fade-up"
            >
              <div className="px-2.5 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">面试模式</div>
              <div className="rounded-lg px-2.5 py-2" role="group" aria-label="自动回答模式">
                <div className="mb-2 flex items-center gap-2 text-xs text-text-secondary">
                  <Zap className={`h-3.5 w-3.5 ${autoAnswerMode === 'off' ? 'text-text-muted' : 'text-accent-green'}`} />
                  <span>自动回答模式</span>
                  <span className="ml-auto text-[10px] text-text-muted">
                    {autoAnswerMode === 'off' ? '仅转录' : autoAnswerMode === 'smart' ? '智能判断' : '有效问句直答'}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1 rounded-lg bg-bg-tertiary/45 p-1">
                  {([
                    { value: 'off' as const, label: '关闭' },
                    { value: 'smart' as const, label: '智能' },
                    { value: 'always' as const, label: '全自动' },
                  ]).map((item) => (
                    <button
                      key={item.value}
                      type="button"
                      role="menuitemradio"
                      aria-checked={autoAnswerMode === item.value}
                      onClick={() => void handleSetAutoAnswerMode(item.value)}
                      className={`rounded-md px-1.5 py-1.5 text-[10px] font-medium transition-colors ${
                        autoAnswerMode === item.value
                          ? 'bg-bg-primary text-accent-blue shadow-sm'
                          : 'text-text-muted hover:text-text-primary'
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  void handleToggleCorrection()
                  setMoreOpen(false)
                }}
                title={config?.assist_answer_correction_enabled ? '答前纠错已开启：回答前用 LLM 修正转写错字/缺字（略慢）' : '答前纠错已关闭（更快）；开启后用 LLM 修正转写错字/缺字'}
                className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors ${
                  config?.assist_answer_correction_enabled ? 'text-accent-green' : 'text-text-secondary hover:bg-bg-tertiary/60 hover:text-text-primary'
                }`}
              >
                <span className="flex items-center gap-2">
                  <SpellCheck className={`w-3.5 h-3.5 ${config?.assist_answer_correction_enabled ? 'text-accent-green' : 'text-text-muted'}`} />
                  答前纠错
                </span>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    config?.assist_answer_correction_enabled ? 'bg-accent-green/15 text-accent-green' : 'bg-bg-tertiary text-text-muted'
                  }`}
                >
                  {config?.assist_answer_correction_enabled ? '开' : '关'}
                </span>
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  void handleToggleConcise()
                  setMoreOpen(false)
                }}
                title={config?.assist_realtime_concise_answer ? '当前为默认短答；开放观点、设计和追问会自动展开' : '当前回答长度为详细：适合完整解释和复盘'}
                className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors ${
                  config?.assist_realtime_concise_answer ? 'text-accent-green' : 'text-text-secondary hover:bg-bg-tertiary/60 hover:text-text-primary'
                }`}
              >
                <span className="flex items-center gap-2">
                  <MessageSquarePlus className={`w-3.5 h-3.5 ${config?.assist_realtime_concise_answer ? 'text-accent-green' : 'text-text-muted'}`} />
                  回答长度：简短
                </span>
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                    config?.assist_realtime_concise_answer ? 'bg-accent-green/15 text-accent-green' : 'bg-bg-tertiary text-text-muted'
                  }`}
                >
                  {config?.assist_realtime_concise_answer ? '开' : '关'}
                </span>
              </button>
              <div className="my-1 h-px bg-bg-hover/50" />
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  void handleClear()
                  setMoreOpen(false)
                }}
                disabled={clearing}
                title={qaPairs.length > 30 ? `当前会话较长 (${qaPairs.length} 条), 建议清空以保持流畅` : isExamMode ? '清空当前页的 AI 答案 (不影响历史)' : '清空当前页的实时转录与 AI 答案 (不影响历史)'}
                className={`flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors disabled:opacity-50 ${
                  qaPairs.length > 30 ? 'text-accent-amber' : 'text-text-secondary hover:bg-bg-tertiary/60 hover:text-accent-red'
                }`}
              >
                <span className="flex items-center gap-2">
                  <Trash2 className={`w-3.5 h-3.5 ${qaPairs.length > 30 ? 'text-accent-amber' : 'text-text-muted'}`} />
                  {clearing ? '清空中…' : '清空内容'}
                </span>
                {qaPairs.length > 30 && !clearing && (
                  <span className="text-[10px] tabular-nums text-accent-amber">({qaPairs.length})</span>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {inputMeterOpen && (
        <div className="fixed inset-0 z-[100] flex items-end justify-center bg-black/45 px-3 py-4 sm:items-center" onClick={(e) => { if (e.target === e.currentTarget) handleCloseInputMeter() }}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label="麦克风输入测试"
            className="w-full max-w-sm rounded-xl border border-bg-hover bg-bg-primary p-4 shadow-2xl shadow-black/30"
          >
            <div className="flex items-start gap-3">
              <div className="inline-flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-accent-green/15 text-accent-green">
                <Mic className="w-4 h-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold text-text-primary">麦克风输入测试</div>
                <div className="mt-0.5 truncate text-xs text-text-muted">
                  {selectedCandidateDevice?.name ?? '当前麦克风'}
                </div>
              </div>
              <button
                type="button"
                onClick={handleCloseInputMeter}
                aria-label="关闭麦克风输入测试"
                className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-text-muted hover:bg-bg-hover hover:text-text-primary"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-5">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className={inputLevel?.has_signal ? 'text-accent-green' : 'text-text-muted'}>
                  {inputLevel?.error ? '监听异常' : inputLevel?.has_signal ? '检测到输入' : '请对着麦克风说话'}
                </span>
                <span className="font-mono text-text-secondary">{inputLevelPct}%</span>
              </div>
              <div className="h-4 overflow-hidden rounded-full bg-bg-hover">
                <div
                  className={`h-full rounded-full transition-[width] duration-100 ${inputLevel?.has_signal ? 'bg-accent-green' : 'bg-accent-amber'}`}
                  style={{ width: `${Math.max(3, inputLevelPct)}%` }}
                />
              </div>
              <div className="mt-2 flex justify-between text-[10px] text-text-muted">
                <span>安静</span>
                <span>正常说话</span>
                <span>偏大</span>
              </div>
            </div>

            {inputLevel?.error && (
              <div className="mt-3 rounded-lg bg-accent-red/10 px-3 py-2 text-xs text-accent-red">
                {inputLevel.error}
              </div>
            )}

            <div className="mt-4 flex justify-end">
              <button
                type="button"
                onClick={handleCloseInputMeter}
                className="rounded-lg bg-bg-tertiary px-3 py-2 text-xs font-medium text-text-secondary hover:bg-bg-hover hover:text-text-primary"
              >
                完成
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
