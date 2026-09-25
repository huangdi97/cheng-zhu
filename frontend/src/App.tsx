import { useCallback, useEffect, useState, useRef, lazy, Suspense } from 'react'
import { Settings, SlidersHorizontal, MonitorSmartphone, PanelLeftClose, PanelLeftOpen, Minus, X, ChevronDown, Mic, Camera, Home, Radio, ClipboardList, BrainCircuit, FileText, Kanban, BookOpenCheck } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore, type AppMode } from '@/stores/uiPrefsStore'
import { useShortcutsStore } from '@/stores/shortcutsStore'
import { useInterviewWS } from '@/hooks/useInterviewWS'
import { useAppBootstrap } from '@/hooks/useAppBootstrap'
import { useOverlayWindowSync } from '@/hooks/useOverlayWindowSync'
import { useAssistSplit } from '@/hooks/useAssistSplit'
import { api } from '@/lib/api'
import { updateConfigAndRefresh } from '@/lib/configSync'
import TranscriptionPanel from '@/components/TranscriptionPanel'
import MemoPanel from '@/components/MemoPanel'
import WorkbenchPopover from '@/components/WorkbenchPopover'
import AnswerPanel from '@/components/AnswerPanel'
import ControlBar from '@/components/ControlBar'
import CopilotHintPanel from '@/components/CopilotHintPanel'
import QuestionBoundaryPanel from '@/components/QuestionBoundaryPanel'
import ScreenshotModePanel from '@/components/ScreenshotModePanel'
import SettingsDrawer from '@/components/SettingsDrawer'
import SessionSettingsPopover from '@/components/SessionSettingsPopover'
import KnowledgeButton from '@/components/kb/KnowledgeButton'
import KnowledgeDrawer from '@/components/kb/KnowledgeDrawer'
import { AppToastStack } from '@/components/app/AppToastStack'
import { InitErrorScreen } from '@/components/app/InitErrorScreen'
import { ModelPriorityDropdown } from '@/components/app/ModelPriorityDropdown'
const ReviewMode = lazy(() => import('@/components/ReviewMode'))
const KnowledgeMap = lazy(() => import('@/components/KnowledgeMap'))
const ResumeOptimizer = lazy(() => import('@/components/ResumeOptimizer'))
const JobTracker = lazy(() => import('@/components/JobTracker'))
const PrepSpace = lazy(() => import('@/components/PrepSpace'))
const HomeScreen = lazy(() => import('@/components/HomeScreen'))

const APP_MODE_TABS = [
  ['home', '首页'],
  ['assist', '实时辅助'],
  ['review', '面试复盘'],
  ['knowledge', '能力分析'],
  ['resume-opt', '简历优化'],
  ['job-tracker', '求职看板'],
  ['prep', '面试准备'],
] as const

const HEADER_ICON_BTN =
  'inline-flex items-center justify-center min-h-[32px] min-w-[32px] p-1.5 rounded-xl text-text-muted hover:text-text-primary hover:bg-bg-tertiary/60 transition-all duration-200 border border-transparent hover:border-bg-hover/40 flex-shrink-0'

/* 面试工作台视觉符号：对话气泡 + 文本行，替代通用麦克风作为品牌标识 */
function WorkbenchMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path
        d="M5.5 5.2A1.7 1.7 0 0 1 7.2 3.5h9.6a1.7 1.7 0 0 1 1.7 1.7v8.6a1.7 1.7 0 0 1-1.7 1.7h-4.9l-3.5 2.9a.65.65 0 0 1-1.08-.5V15.5H7.2a1.7 1.7 0 0 1-1.7-1.7V5.2Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M8.6 8h6.8M8.6 11.2h4.2" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

/* MD3 导航栏（Navigation Rail）：桌面端左侧功能切换 */
const NAV_ITEMS: Array<[AppMode, string, typeof Home]> = [
  ['home', '首页', Home],
  ['assist', '实时辅助', Radio],
  ['review', '面试复盘', ClipboardList],
  ['knowledge', '能力分析', BrainCircuit],
  ['resume-opt', '简历优化', FileText],
  ['job-tracker', '求职看板', Kanban],
  ['prep', '面试准备', BookOpenCheck],
]

function AppNavRail({ appMode, onSelect }: { appMode: AppMode; onSelect: (mode: AppMode) => void }) {
  return (
    <nav
      role="tablist"
      aria-label="功能模块"
      className="hidden md:flex flex-col items-center gap-1 w-[76px] flex-shrink-0 border-r border-bg-tertiary/70 bg-bg-secondary/40 py-3 px-1.5 overflow-y-auto scrollbar-none"
    >
      {NAV_ITEMS.map(([mode, label, Icon]) => (
        <button
          key={mode}
          type="button"
          role="tab"
          aria-selected={appMode === mode}
          onClick={() => onSelect(mode)}
          title={label}
          className={`flex flex-col items-center justify-center gap-1.5 w-full py-2.5 rounded-2xl transition-colors ${
            appMode === mode
              ? 'bg-container-primary text-container-on-primary font-semibold'
              : 'text-text-muted hover:bg-bg-hover/60 hover:text-text-primary'
          }`}
        >
          <Icon className="w-5 h-5" aria-hidden />
          <span className="text-[10px] leading-none">{label}</span>
        </button>
      ))}
    </nav>
  )
}

export default function App() {
  useInterviewWS()
  // 精确订阅, 避免 store 任意字段变化(LLM token 流式 / toast 等)触发 App 重渲染
  const { config, toggleSettings, openModelsDrawer } = useInterviewStore(
    useShallow((s) => ({
      config: s.config,
      toggleSettings: s.toggleSettings,
      openModelsDrawer: s.openModelsDrawer,
    })),
  )
  const sttLoaded = useInterviewStore((s) => s.sttLoaded)
  const sttLoading = useInterviewStore((s) => s.sttLoading)
  const sttActiveProvider = useInterviewStore((s) => s.sttActiveProvider)
  const sttFallbackLoaded = useInterviewStore((s) => s.sttFallbackLoaded)
  const isRecording = useInterviewStore((s) => s.isRecording)
  const isPaused = useInterviewStore((s) => s.isPaused)
  const currentStreamingId = useInterviewStore((s) => s.currentStreamingId)
  const isExamMode = config?.written_exam_mode === true
  const [mobileTab, setMobileTab] = useState<'transcript' | 'answer'>('transcript')
  const lastMobileStreamingIdRef = useRef<string | null>(null)
  const appMode = useUiPrefsStore((s) => s.appMode)
  const assistMode = useUiPrefsStore((s) => s.assistMode)
  const setAssistMode = useUiPrefsStore((s) => s.setAssistMode)
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)
  const assistTranscriptCollapsed = useUiPrefsStore((s) => s.assistTranscriptCollapsed)
  const toggleAssistTranscriptCollapsed = useUiPrefsStore((s) => s.toggleAssistTranscriptCollapsed)
  useOverlayWindowSync(isRecording, appMode)

  const [memoVisible, setMemoVisible] = useState(() => {
    try { return localStorage.getItem('ia-memo-visible') === '1' } catch { return false }
  })
  const toggleMemoVisible = useCallback(() => {
    setMemoVisible((v) => {
      const next = !v
      try { localStorage.setItem('ia-memo-visible', next ? '1' : '0') } catch { /* ignore */ }
      return next
    })
  }, [])
  const [serverScreenLoading, setServerScreenLoading] = useState(false)
  const [sessionPopoverOpen, setSessionPopoverOpen] = useState(false)
  const [moduleMenuOpen, setModuleMenuOpen] = useState(false)
  const serverScreenAskRef = useRef(false)
  const modelChangeSavingRef = useRef(false)
  const pendingModelChangeRef = useRef<number | null>(null)
  const sessionAnchorRef = useRef<HTMLButtonElement | null>(null)
  const moduleMenuRef = useRef<HTMLDivElement | null>(null)

  const {
    assistSplitContainerRef,
    assistSplitDragging,
    assistSplitPct,
    assistSplitPctRef,
    persistAssistSplitPct,
  } = useAssistSplit()

  const { initError } = useAppBootstrap()

  useEffect(() => {
    if (!moduleMenuOpen) return
    const onPointerDown = (event: MouseEvent) => {
      if (!moduleMenuRef.current?.contains(event.target as Node)) {
        setModuleMenuOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setModuleMenuOpen(false)
    }
    window.addEventListener('mousedown', onPointerDown)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('mousedown', onPointerDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [moduleMenuOpen])

  useEffect(() => {
    setModuleMenuOpen(false)
  }, [appMode])

  // 笔试题提交后优先展示答案流，避免手机端仍停留在「答题记录」而看不到
  // 正在生成的结果。用户仍可手动切回记录页；同一题的后续 token 不会强制抢回焦点。
  useEffect(() => {
    if (!isExamMode) {
      lastMobileStreamingIdRef.current = currentStreamingId
      return
    }
    // During the very first layout pass some embedded/browser surfaces briefly
    // report width 0. Treat that as unknown rather than mobile; otherwise a
    // desktop answer panel can be mounted twice and duplicate its cards.
    const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 0
    const isMobileViewport = viewportWidth > 0 && viewportWidth < 768
    if (
      isMobileViewport
      && currentStreamingId
      && currentStreamingId !== lastMobileStreamingIdRef.current
    ) {
      setMobileTab('answer')
    }
    lastMobileStreamingIdRef.current = currentStreamingId
  }, [currentStreamingId, isExamMode])

  useEffect(() => {
    if (!window.electronAPI?.getShortcuts) return
    window.electronAPI.getShortcuts()
      .then((shortcuts) => useShortcutsStore.getState().setShortcuts(shortcuts))
      .catch(() => {})
  }, [])

  const hasGuided = useRef(false)
  useEffect(() => {
    if (!config || hasGuided.current) return
    if (!config.api_key_set) {
      hasGuided.current = true
      openModelsDrawer()
    }
  }, [config, openModelsDrawer])

  // Cmd+Shift+J / Ctrl+Shift+J: 切换实时转录面板显隐
  // 注: Chrome 等浏览器把 Cmd+J / Ctrl+J 保留给「下载」, 故叠加 Shift 降低冲突.
  // 仅桌面端 assist 模式下生效; 输入框/contenteditable 内按键忽略.
  useEffect(() => {
    if (appMode !== 'assist') return
    const onKeyDown = (e: KeyboardEvent) => {
      const isToggle =
        (e.metaKey || e.ctrlKey) &&
        e.shiftKey &&
        !e.altKey &&
        (e.key === 'j' || e.key === 'J')
      if (!isToggle) return
      const target = e.target as HTMLElement | null
      const tag = target?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return
      e.preventDefault()
      toggleAssistTranscriptCollapsed()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [appMode, toggleAssistTranscriptCollapsed])

  const handleModelChange = useCallback(async (active_model: number) => {
    pendingModelChangeRef.current = active_model
    if (modelChangeSavingRef.current) return

    modelChangeSavingRef.current = true
    try {
      while (pendingModelChangeRef.current !== null) {
        const nextActiveModel = pendingModelChangeRef.current
        pendingModelChangeRef.current = null
        const targetModel = useInterviewStore.getState().config?.models?.[nextActiveModel]
        if (!targetModel) {
          useInterviewStore.getState().setToastMessage('未找到该模型，请刷新配置后重试')
          continue
        }
        if (targetModel.enabled === false) {
          useInterviewStore.getState().setToastMessage('该模型已停用，请先在设置中启用后再设为优先')
          continue
        }
        try {
          await updateConfigAndRefresh({ active_model: nextActiveModel })
          useInterviewStore.getState().setToastMessage(`已设为优先答题模型：${targetModel.name}`)
        } catch (error) {
          useInterviewStore.getState().setToastMessage(error instanceof Error ? error.message : '设置优先模型失败')
        }
      }
    } finally {
      modelChangeSavingRef.current = false
    }
  }, [])

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

  const modelHealth = useInterviewStore((s) => s.modelHealth)
  const modelHealthDetail = useInterviewStore((s) => s.modelHealthDetail)
  const modelHealthLatency = useInterviewStore((s) => s.modelHealthLatency)
  const fallbackToast = useInterviewStore((s) => s.fallbackToast)
  const toastMessage = useInterviewStore((s) => s.toastMessage)
  const toasts = useInterviewStore((s) => s.toasts)
  const dismissToast = useInterviewStore((s) => s.dismissToast)
  const wsIsLeader = useInterviewStore((s) => s.wsIsLeader)
  const currentAppModeLabel = APP_MODE_TABS.find(([key]) => key === appMode)?.[1] ?? '模块'

  useEffect(() => {
    if (!fallbackToast) return
    const timer = setTimeout(() => useInterviewStore.getState().setFallbackToast(null), 4000)
    return () => clearTimeout(timer)
  }, [fallbackToast])
  useEffect(() => {
    if (!toastMessage) return
    const timer = setTimeout(() => useInterviewStore.getState().setToastMessage(null), 2000)
    return () => clearTimeout(timer)
  }, [toastMessage])

  const toastTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())
  useEffect(() => {
    const timers = toastTimersRef.current
    const currentIds = new Set(toasts.map((t) => t.id))
    for (const [id, timer] of timers) {
      if (!currentIds.has(id)) { clearTimeout(timer); timers.delete(id) }
    }
    for (const t of toasts) {
      if (!timers.has(t.id)) {
        const timer = setTimeout(() => useInterviewStore.getState().dismissToast(t.id), t.ttlMs)
        timers.set(t.id, timer)
      }
    }
  }, [toasts])
  useEffect(() => () => {
    for (const timer of toastTimersRef.current.values()) clearTimeout(timer)
    toastTimersRef.current.clear()
  }, [])
  if (initError) {
    return <InitErrorScreen initError={initError} />
  }

  return (
    <div className="h-screen flex flex-col app-shell overflow-hidden noise-bg">
      {/* Header — 强制单行不换行, 各按钮文字按宽度阶梯隐藏, 实在不够再让左区横向滚动 */}
      <header className="app-drag-region header-gradient flex flex-row items-center justify-between gap-2 px-3 md:px-5 py-3 flex-shrink-0 min-w-0">
        <div className="flex items-center gap-2 md:gap-2.5 flex-shrink min-w-0 overflow-hidden">
          <div className="flex items-center gap-2.5">
            <div className="sig-tile w-8 h-8 rounded-xl">
              <WorkbenchMark className="w-4 h-4" />
            </div>
            <h1 className="text-sm font-bold hidden lg:block flex-shrink-0 tracking-tight">成竹</h1>
          </div>

          <div className="relative ml-1 md:hidden" ref={moduleMenuRef}>
            <button
              type="button"
              onClick={() => setModuleMenuOpen((prev) => !prev)}
              aria-haspopup="menu"
              aria-expanded={moduleMenuOpen}
              aria-label="切换功能模块"
              className={`inline-flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-xs font-medium transition-colors ${
                moduleMenuOpen
                  ? 'border-accent-blue/40 bg-accent-blue/10 text-accent-blue'
                  : 'border-bg-hover/30 bg-bg-tertiary/60 text-text-primary'
              }`}
            >
              <MonitorSmartphone className="h-3.5 w-3.5" />
              <span className="max-w-[88px] truncate">{currentAppModeLabel}</span>
              <ChevronDown className={`h-3.5 w-3.5 transition-transform ${moduleMenuOpen ? 'rotate-180' : ''}`} />
            </button>
            {moduleMenuOpen ? (
              <div
                role="menu"
                aria-label="功能模块"
                className="absolute left-0 top-[calc(100%+0.5rem)] z-40 min-w-[180px] glass-popover rounded-2xl p-2 animate-fade-up"
              >
                <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-text-muted">模块</div>
                <div className="mt-1 space-y-1">
                  {APP_MODE_TABS.map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      role="menuitem"
                      onClick={() => {
                        setAppMode(key)
                        setModuleMenuOpen(false)
                      }}
                      className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition-colors ${
                        appMode === key
                          ? 'bg-container-primary text-container-on-primary'
                          : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'
                      }`}
                    >
                      <span>{label}</span>
                      {appMode === key ? <span className="text-[11px] font-semibold">当前</span> : null}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          {/* 状态 chip:合并 STT + REC,录音中优先显示 REC,平时显示 STT 状态 */}
          {isRecording ? (
            <div
              className={`flex items-center gap-1.5 ml-1.5 flex-shrink-0 rounded-lg px-2 py-1 border animate-fade-up ${
                isPaused
                  ? 'bg-accent-amber/10 border-accent-amber/30'
                  : 'bg-accent-red/10 border-accent-red/30'
              }`}
              role="status"
              aria-live="polite"
              title={
                isPaused
                  ? isExamMode ? '笔试已暂停' : `录音已暂停 · STT ${sttLoaded ? (sttActiveProvider === 'whisper' ? 'Whisper' : '就绪') : sttLoading ? '加载中' : '未加载'}`
                  : isExamMode ? '笔试进行中' : `正在录音中 · STT ${sttLoaded ? (sttActiveProvider === 'whisper' ? 'Whisper' : '就绪') : sttLoading ? '加载中' : '未加载'}`
              }
            >
              <span className="relative inline-flex w-1.5 h-1.5 flex-shrink-0">
                {!isPaused && (
                  <span className="absolute inset-0 rounded-full bg-accent-red opacity-75 motion-safe:animate-ping" aria-hidden />
                )}
                <span
                  className={`relative inline-flex w-1.5 h-1.5 rounded-full ${isPaused ? 'bg-accent-amber' : 'bg-accent-red'}`}
                  aria-hidden
                />
              </span>
              <span
                className={`text-[10px] font-semibold leading-none hidden sm:inline ${isPaused ? 'text-accent-amber' : 'text-accent-red'}`}
              >
                {isPaused ? 'PAUSED' : isExamMode ? 'EXAM' : 'REC'}
              </span>
            </div>
          ) : (
            <div
              className="flex items-center gap-1.5 ml-1.5 flex-shrink-0 bg-bg-tertiary/30 rounded-lg px-2 py-1 border border-bg-hover/20"
              title={
                isExamMode
                  ? '笔试模式 · 等待提问'
                  : sttLoaded
                  ? sttActiveProvider === 'whisper' ? 'STT 已降级至 Whisper · 等待录音' : sttFallbackLoaded ? 'STT 就绪 · Whisper 降级已预加载' : 'STT 就绪 · 等待录音'
                  : sttLoading
                  ? sttActiveProvider === 'whisper' ? 'Whisper 降级加载中…' : 'STT 模型加载中…'
                  : 'STT 模型尚未加载,首次录音时会自动加载'
              }
            >
              <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${sttLoaded ? (sttActiveProvider === 'whisper' ? 'bg-accent-amber' : 'bg-accent-green') : sttLoading ? 'bg-accent-amber animate-pulse' : 'bg-accent-red'}`} />
              <span className="text-[10px] text-text-muted hidden md:inline font-medium">
                {sttLoaded ? (sttActiveProvider === 'whisper' ? 'Whisper' : sttFallbackLoaded ? 'STT ✓' : 'STT 就绪') : sttLoading ? '加载中' : '未加载'}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-1.5 md:gap-2 flex-shrink-0 flex-nowrap justify-end">
          {config?.models && config.models.length > 0 && (
            <ModelPriorityDropdown
              config={config}
              modelHealth={modelHealth}
              modelHealthDetail={modelHealthDetail}
              modelHealthLatency={modelHealthLatency}
              onModelChange={handleModelChange}
            />
          )}

          <WorkbenchPopover memoPinned={memoVisible} onToggleMemoPin={toggleMemoVisible} />

          {/* 会场设置:聚合 Think + 岗位 + 语言 + Token */}
          <div className="relative">
            <button
              ref={sessionAnchorRef}
              type="button"
              onClick={() => setSessionPopoverOpen((v) => !v)}
              title="会场设置:Think 思考模式 / 岗位 / 语言 / Token 用量"
              aria-haspopup="dialog"
              aria-expanded={sessionPopoverOpen}
              aria-label="打开会场设置"
              className={`relative inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-xs border transition-all duration-200 flex-shrink-0
                ${sessionPopoverOpen
                  ? 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue shadow-sm shadow-accent-blue/10'
                  : 'border-bg-hover/50 bg-bg-tertiary/50 text-text-secondary hover:border-accent-blue/40 hover:text-text-primary'}`}
            >
              <SlidersHorizontal className="w-3.5 h-3.5" />
              <span className="font-medium hidden sm:inline">会场</span>
              {config?.think_mode && (
                <span
                  className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-accent-green ring-2 ring-bg-primary shadow-[0_0_6px] shadow-accent-green/60"
                  aria-hidden
                  title="Think 已开启"
                />
              )}
            </button>
            <SessionSettingsPopover
              open={sessionPopoverOpen}
              onClose={() => setSessionPopoverOpen(false)}
              anchorRef={sessionAnchorRef}
            />
          </div>

          {appMode === 'assist' && (
            <button
              type="button"
              onClick={toggleAssistTranscriptCollapsed}
              className={`hidden md:inline-flex ${HEADER_ICON_BTN}`}
              title={assistTranscriptCollapsed ? '显示实时转录面板 (⌘⇧J / Ctrl+⇧+J)' : '隐藏实时转录面板 (⌘⇧J / Ctrl+⇧+J)'}
              aria-label={assistTranscriptCollapsed ? '显示实时转录面板' : '隐藏实时转录面板'}
              aria-expanded={!assistTranscriptCollapsed}
            >
              {assistTranscriptCollapsed ? (
                <PanelLeftOpen className="w-4 h-4" />
              ) : (
                <PanelLeftClose className="w-4 h-4" />
              )}
            </button>
          )}
          <KnowledgeButton />
        <button
          type="button"
          onClick={toggleSettings}
          className={`inline-flex ${HEADER_ICON_BTN}`}
          title="设置中心 (外观 / 偏好 / 模型 / 隐私 / 快捷键)"
          aria-label="打开设置"
        >
          <Settings className="w-4 h-4" />
        </button>
        {window.electronAPI && (
          <>
            <button
              type="button"
              onClick={() => window.electronAPI?.minimizeWindow()}
              className={`inline-flex ${HEADER_ICON_BTN}`}
              title="最小化"
              aria-label="最小化窗口"
            >
              <Minus className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => window.electronAPI?.quitApp()}
              className={`inline-flex ${HEADER_ICON_BTN} hover:border-accent-red/40 hover:text-accent-red`}
              title="退出"
              aria-label="退出应用"
            >
              <X className="w-4 h-4" />
            </button>
          </>
        )}
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <AppNavRail appMode={appMode} onSelect={setAppMode} />
        <div className="flex flex-col flex-1 min-w-0 min-h-0">

      {/* ── Assist Mode ── */}
      {/* Home (two entry cards) */}
      {appMode === 'home' && (
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-sm text-text-muted">加载中…</div>}>
          <HomeScreen />
        </Suspense>
      )}

      {appMode === 'assist' && (
        <>
          {/* Assist sub-mode: voice / screenshot */}
          <div className="flex items-center gap-1.5 px-3 md:px-5 py-2.5 border-b border-bg-tertiary/70 bg-bg-secondary/40 flex-shrink-0">
            <button
              type="button"
              onClick={() => setAssistMode('voice')}
              aria-pressed={assistMode === 'voice'}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${assistMode === 'voice' ? 'bg-container-primary text-container-on-primary font-semibold' : 'text-text-muted hover:text-text-primary'}`}
            >
              <Mic className="w-3.5 h-3.5" aria-hidden />
              语音模式
            </button>
            <button
              type="button"
              onClick={() => setAssistMode('screenshot')}
              aria-pressed={assistMode === 'screenshot'}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${assistMode === 'screenshot' ? 'bg-container-primary text-container-on-primary font-semibold' : 'text-text-muted hover:text-text-primary'}`}
            >
              <Camera className="w-3.5 h-3.5" aria-hidden />
              截图模式
            </button>
          </div>
          {assistMode === 'voice' ? (
            <>
          {/* Mobile tab switcher */}
          <div className="flex md:hidden border-b border-bg-tertiary flex-shrink-0" role="tablist" aria-label="实时辅助面板">
            <button role="tab" aria-selected={mobileTab === 'transcript'} onClick={() => setMobileTab('transcript')}
              className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${mobileTab === 'transcript' ? 'text-accent-blue border-b-2 border-accent-blue' : 'text-text-muted'}`}>
              {isExamMode ? '答题记录' : '实时转录'}
            </button>
            <button role="tab" aria-selected={mobileTab === 'answer'} onClick={() => setMobileTab('answer')}
              className={`flex-1 py-2 text-xs font-medium text-center transition-colors ${mobileTab === 'answer' ? 'text-accent-blue border-b-2 border-accent-blue' : 'text-text-muted'}`}>
              AI 答案
            </button>
          </div>

          <div
            ref={assistSplitContainerRef}
            className="flex-1 hidden md:flex overflow-hidden min-h-0"
          >
            {!assistTranscriptCollapsed && (
              <>
            <div
              className="flex flex-col min-w-0 flex-shrink-0 border-r border-bg-tertiary animate-slide-left"
              style={{
                width: `${assistSplitPct}%`,
                minWidth: '220px',
                maxWidth: '62%',
              }}
            >
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
                const c = 32
                assistSplitPctRef.current = c
                persistAssistSplitPct(c)
              }}
              onKeyDown={(e) => {
                if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
                  e.preventDefault()
                  const delta = e.key === 'ArrowLeft' ? -2 : 2
                  const c = Math.min(62, Math.max(24, assistSplitPctRef.current + delta))
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
              <span
                className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-bg-hover group-hover:bg-accent-blue/50 pointer-events-none"
                aria-hidden
              />
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
              <button
                type="button"
                disabled={serverScreenLoading}
                onClick={handleServerScreenAsk}
                className="w-full flex items-center justify-center gap-3 min-h-[52px] py-3.5 rounded-xl bg-accent-blue text-white text-base font-semibold shadow-sm disabled:opacity-60 active:scale-[0.99] transition-transform"
              >
                <MonitorSmartphone className="w-5 h-5 flex-shrink-0" />
                {serverScreenLoading ? '截图审题提交中…' : '服务端截图审题'}
              </button>
              <p className="text-[10px] text-text-muted text-center mt-1.5 leading-snug px-0.5">
                在后台子进程截主屏左半幅，该请求不写访问日志以减少终端抢焦点。若仍被终端打断，可用 <code className="text-[10px] bg-bg-tertiary px-0.5 rounded">IA_ACCESS_LOG=0</code> 启动后端关闭全部 HTTP 访问日志。须配置识图模型与屏幕录制权限。
              </p>
            </div>
          )}

            <QuestionBoundaryPanel />
            <CopilotHintPanel />
            <ControlBar />
            </>
          ) : (
            <ScreenshotModePanel
              serverScreenLoading={serverScreenLoading}
              onAsk={handleServerScreenAsk}
            />
          )}
      </>
      )}

      {/* ── Review Mode ── */}
      {appMode === 'review' && (
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-sm text-text-muted">加载面试复盘中…</div>}>
          <ReviewMode />
        </Suspense>
      )}

      {/* ── Knowledge Map ── */}
      {appMode === 'knowledge' && (
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-sm text-text-muted">加载能力分析中…</div>}>
          <KnowledgeMap />
        </Suspense>
      )}

      {/* ── Resume Optimizer ── */}
      {appMode === 'resume-opt' && (
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-sm text-text-muted">加载简历优化中…</div>}>
          <ResumeOptimizer />
        </Suspense>
      )}

      {/* ── Job tracker ── */}
      {appMode === 'job-tracker' && (
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-sm text-text-muted">加载求职看板中…</div>}>
          <JobTracker />
        </Suspense>
      )}

      {/* Prep space */}
      {appMode === 'prep' && (
        <Suspense fallback={<div className="flex-1 flex items-center justify-center text-sm text-text-muted">加载面试准备中…</div>}>
          <PrepSpace />
        </Suspense>
      )}

      <AppToastStack
        wsIsLeader={wsIsLeader}
        fallbackToast={fallbackToast}
        toasts={toasts}
        dismissToast={dismissToast}
      />

      <SettingsDrawer />
      <KnowledgeDrawer />
        </div>
      </div>
    </div>
  )
}
