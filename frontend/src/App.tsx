/**
 * App shell (v1.3 Goal-centered IA, canonical §3).
 * Navigation: 首页 · 求职目标 · 我的成竹 · 练习 · 资料库 · 历史 · 设置.
 * [上场] is a global action (Go Live → Preflight → Live Cockpit), not a nav item.
 * Routes are object-centric hash routes; the v1.2 `appMode` is kept in sync
 * through the route adapter in lib/router.
 */
import { useCallback, useEffect, useRef, useState, lazy, Suspense } from 'react'
import { Settings, PanelLeftClose, PanelLeftOpen, Minus, X, ChevronDown, Home, Radio, ClipboardList, FileText, Flag, BookOpenCheck, Library, Command as CommandIcon, SlidersHorizontal, MonitorSmartphone, MessageSquareText } from 'lucide-react'
import { useShallow } from 'zustand/react/shallow'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'
import { useShortcutsStore } from '@/stores/shortcutsStore'
import { useOsStore } from '@/stores/osStore'
import { useInterviewWS } from '@/hooks/useInterviewWS'
import { useAppBootstrap } from '@/hooks/useAppBootstrap'
import { useOverlayWindowSync } from '@/hooks/useOverlayWindowSync'
import { updateConfigAndRefresh } from '@/lib/configSync'
import { conversationApi } from '@/lib/conversationApi'
import { hasExplicitRoute, legacyModeForRoute, navigate, paths, routeForLegacyMode, startRouterListener, useRouter, type RouteName, type ConversationTab } from '@/lib/router'
import { useT, useUiLanguage, type StringKey } from '@/lib/i18n'
import WorkbenchPopover from '@/components/WorkbenchPopover'
import OnboardingWizard from '@/components/onboarding/OnboardingWizard'
import SettingsDrawer from '@/components/SettingsDrawer'
import { shouldPromptForInterviewModel } from '@/lib/modelSetupNudge'
import SessionSettingsPopover from '@/components/SessionSettingsPopover'
import KnowledgeButton from '@/components/kb/KnowledgeButton'
import KnowledgeDrawer from '@/components/kb/KnowledgeDrawer'
import { AppToastStack } from '@/components/app/AppToastStack'
import { InitErrorScreen } from '@/components/app/InitErrorScreen'
import { ModelPriorityDropdown } from '@/components/app/ModelPriorityDropdown'
import PageErrorBoundary from '@/components/app/PageErrorBoundary'
import LiveCockpit from '@/components/live/LiveCockpit'
import CreateGoalDialog from '@/components/os/CreateGoalDialog'
import GoLiveDialog from '@/components/os/GoLiveDialog'
import CommandPalette from '@/components/os/CommandPalette'
import PinDialog from '@/components/os/PinDialog'
import QuickNotesDrawer from '@/components/os/QuickNotesDrawer'

const HomePage = lazy(() => import('@/components/os/HomePage'))
const GoalsPage = lazy(() => import('@/components/os/GoalsPage'))
const GoalRoom = lazy(() => import('@/components/os/GoalRoom'))
const MePage = lazy(() => import('@/components/os/MePage'))
const PracticePage = lazy(() => import('@/components/os/PracticePage'))
const LibraryPage = lazy(() => import('@/components/os/LibraryPage'))
const HistoryPage = lazy(() => import('@/components/os/HistoryPage'))
const ReflectionPage = lazy(() => import('@/components/os/ReflectionPage'))
const SettingsPage = lazy(() => import('@/components/os/SettingsPage'))
const ConversationHome = lazy(() => import('@/components/conversation/ConversationHome'))
const ConversationOnboardingPage = lazy(() => import('@/components/conversation/ConversationOnboardingPage'))
const ConversationSpacesPage = lazy(() => import('@/components/conversation/ConversationSpacesPage'))
const ConversationSpacePage = lazy(() => import('@/components/conversation/ConversationSpacePage'))
const ConversationLivePage = lazy(() => import('@/components/conversation/ConversationLivePage'))
const ConversationHistoryPage = lazy(() => import('@/components/conversation/ConversationHistoryPage'))

const HEADER_ICON_BTN =
  'inline-flex items-center justify-center min-h-[32px] min-w-[32px] p-1.5 rounded-xl text-text-muted hover:text-text-primary hover:bg-bg-tertiary/60 transition-all duration-200 border border-transparent hover:border-bg-hover/40 flex-shrink-0'

/* 面试工作台视觉符号：对话气泡 + 文本行 */
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

type NavItem = { key: string; label: StringKey; Icon: typeof Home; path: string; match: RouteName[] }

const INTERVIEW_NAV_ITEMS: NavItem[] = [
  { key: 'home', label: 'nav.home', Icon: Home, path: paths.home(), match: ['home'] },
  { key: 'goals', label: 'nav.goals', Icon: Flag, path: paths.goals(), match: ['goals', 'goal'] },
  { key: 'me', label: 'nav.me', Icon: FileText, path: paths.me(), match: ['me'] },
  { key: 'practice', label: 'nav.practice', Icon: BookOpenCheck, path: paths.practice(), match: ['practice'] },
  { key: 'library', label: 'nav.library', Icon: Library, path: paths.library(), match: ['library'] },
  { key: 'history', label: 'nav.history', Icon: ClipboardList, path: paths.history(), match: ['history', 'reflection'] },
]

const CONVERSATION_NAV_ITEMS: NavItem[] = [
  { key: 'conversation-home', label: 'nav.conversationHome', Icon: Home, path: paths.conversationHome(), match: ['conversation-home', 'conversation-onboarding'] },
  { key: 'spaces', label: 'nav.spaces', Icon: MessageSquareText, path: paths.conversationSpaces(), match: ['conversations', 'conversation', 'conversation-live'] },
  { key: 'me', label: 'nav.me', Icon: FileText, path: paths.me(), match: ['me'] },
  { key: 'library', label: 'nav.library', Icon: Library, path: paths.library(), match: ['library'] },
  { key: 'history', label: 'nav.history', Icon: ClipboardList, path: paths.history(), match: ['history'] },
]

type ProductProfile = 'interview' | 'conversation'

function AppNavRail({ current, profile }: { current: RouteName; profile: ProductProfile }) {
  const t = useT()
  const items = profile === 'conversation' ? CONVERSATION_NAV_ITEMS : INTERVIEW_NAV_ITEMS
  return (
    <nav aria-label={t('nav.label')} className="hidden md:flex flex-col items-center gap-1 w-[76px] flex-shrink-0 border-r border-bg-tertiary/70 bg-bg-secondary/40 py-3 px-1.5 overflow-y-auto scrollbar-none">
      <ul className="flex flex-col items-center gap-1 w-full">
        {items.map(({ key, label, Icon, path, match }) => {
          const active = match.includes(current)
          return (
            <li key={key} className="w-full">
              <button type="button" aria-current={active ? 'page' : undefined} onClick={() => navigate(path)} title={t(label)}
                className={`flex flex-col items-center justify-center gap-1.5 w-full py-2.5 rounded-2xl transition-colors ${active ? 'bg-container-primary text-container-on-primary font-semibold' : 'text-text-muted hover:bg-bg-hover/60 hover:text-text-primary'}`}>
                <Icon className="w-5 h-5" aria-hidden />
                <span className="text-[10px] leading-none">{t(label)}</span>
              </button>
            </li>
          )
        })}
      </ul>
      <button type="button" aria-current={current === 'settings' ? 'page' : undefined} onClick={() => navigate(paths.settings())} title={t('nav.settings')}
        className={`mt-auto flex flex-col items-center justify-center gap-1.5 w-full py-2.5 rounded-2xl ${current === 'settings' ? 'bg-container-primary text-container-on-primary font-semibold' : 'text-text-muted hover:bg-bg-hover/60 hover:text-text-primary'}`}>
        <Settings className="w-5 h-5" aria-hidden />
        <span className="text-[10px] leading-none">{t('nav.settings')}</span>
      </button>
    </nav>
  )
}

function PageFallback() {
  const t = useT()
  return <div className="flex-1 flex items-center justify-center text-sm text-text-muted">{t('loading')}</div>
}

export default function App() {
  useInterviewWS()
  const { config, openModelsDrawer } = useInterviewStore(
    useShallow((s) => ({ config: s.config, openModelsDrawer: s.openModelsDrawer })),
  )
  const sttLoaded = useInterviewStore((s) => s.sttLoaded)
  const sttLoading = useInterviewStore((s) => s.sttLoading)
  const sttActiveProvider = useInterviewStore((s) => s.sttActiveProvider)
  const isRecording = useInterviewStore((s) => s.isRecording)
  const isPaused = useInterviewStore((s) => s.isPaused)
  const isExamMode = config?.written_exam_mode === true
  const route = useRouter((s) => s.route)
  const [productProfile, setProductProfile] = useState<ProductProfile>(() => {
    try { return window.localStorage.getItem('chengzhu-product-profile') === 'conversation' ? 'conversation' : 'interview' }
    catch { return 'interview' }
  })
  const t = useT()
  const uiLanguage = useUiLanguage()
  const appMode = useUiPrefsStore((s) => s.appMode)
  const assistTranscriptCollapsed = useUiPrefsStore((s) => s.assistTranscriptCollapsed)
  const toggleAssistTranscriptCollapsed = useUiPrefsStore((s) => s.toggleAssistTranscriptCollapsed)
  const memoVisible = useOsStore((s) => s.memoVisible)
  const toggleMemoVisible = useOsStore((s) => s.toggleMemoVisible)
  const openGoLive = useOsStore((s) => s.openGoLive)
  const setCommandPalette = useOsStore((s) => s.setCommandPalette)
  const setPinDialog = useOsStore((s) => s.setPinDialog)
  const inLive = route.name === 'live'
  const inConversationLive = route.name === 'conversation-live'
  useOverlayWindowSync(isRecording, appMode)

  const [sessionPopoverOpen, setSessionPopoverOpen] = useState(false)
  const [moduleMenuOpen, setModuleMenuOpen] = useState(false)
  const modelChangeSavingRef = useRef(false)
  const pendingModelChangeRef = useRef<number | null>(null)
  const sessionAnchorRef = useRef<HTMLButtonElement | null>(null)
  const moduleMenuRef = useRef<HTMLDivElement | null>(null)
  const { initError } = useAppBootstrap()

  // Router: listen to back/forward; migrate a v1.2 install (no hash) from its stored appMode.
  useEffect(() => {
    const stop = startRouterListener()
    if (!hasExplicitRoute()) navigate(routeForLegacyMode(useUiPrefsStore.getState().appMode), { replace: true })
    return stop
  }, [])
  // Route adapter: keep the legacy appMode in step for v1.2 hooks and components.
  useEffect(() => {
    const mode = legacyModeForRoute(route)
    if (useUiPrefsStore.getState().appMode !== mode) useUiPrefsStore.setState({ appMode: mode })
  }, [route])

  // A profile is a work surface, not a separate account. Shared Me/Library/Settings
  // preserve the user's last choice; profile-specific routes are authoritative.
  useEffect(() => {
    const conversationRoute = ['conversation-home', 'conversation-onboarding', 'conversations', 'conversation', 'conversation-live'].includes(route.name)
    const interviewRoute = ['home', 'goals', 'goal', 'practice', 'reflection', 'live'].includes(route.name)
    const next: ProductProfile | null = conversationRoute ? 'conversation' : interviewRoute ? 'interview' : null
    if (next && next !== productProfile) {
      setProductProfile(next)
      try { window.localStorage.setItem('chengzhu-product-profile', next) } catch { /* localStorage unavailable */ }
    }
  }, [route.name, productProfile])

  const switchProfile = useCallback((next: ProductProfile) => {
    setProductProfile(next)
    try { window.localStorage.setItem('chengzhu-product-profile', next) } catch { /* localStorage unavailable */ }
    if (next === 'conversation') {
      let optedIn = false
      try { optedIn = window.localStorage.getItem('chengzhu-conversation-optin') === '1' } catch { /* storage unavailable */ }
      navigate(optedIn ? paths.conversationHome() : paths.conversationOnboarding())
      return
    }
    navigate(paths.home())
  }, [])

  const startConversation = useCallback(() => {
    if (route.name === 'conversation' && route.params.spaceId) {
      navigate(paths.conversationSpace(route.params.spaceId, 'prepare'))
      return
    }
    navigate(paths.conversationSpaces(undefined, { new: '1' }))
  }, [route.name, route.params])

  useEffect(() => {
    document.documentElement.lang = uiLanguage
  }, [uiLanguage])

  useEffect(() => {
    if (!moduleMenuOpen) return
    const onPointerDown = (event: MouseEvent) => {
      if (!moduleMenuRef.current?.contains(event.target as Node)) setModuleMenuOpen(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setModuleMenuOpen(false) }
    window.addEventListener('mousedown', onPointerDown)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('mousedown', onPointerDown)
      window.removeEventListener('keydown', onKey)
    }
  }, [moduleMenuOpen])
  useEffect(() => { setModuleMenuOpen(false) }, [route.path])

  useEffect(() => {
    if (!window.electronAPI?.getShortcuts) return
    window.electronAPI.getShortcuts()
      .then((shortcuts) => useShortcutsStore.getState().setShortcuts(shortcuts))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const api = window.electronAPI
    if (!api?.onConversationReminderOpen) return
    return api.onConversationReminderOpen(({ spaceId }) => {
      setProductProfile('conversation')
      try { window.localStorage.setItem('chengzhu-product-profile', 'conversation') } catch { /* storage unavailable */ }
      navigate(paths.conversationSpace(spaceId, 'prepare'))
    })
  }, [])

  useEffect(() => {
    const api = window.electronAPI
    if (!api?.syncConversationReminders) return

    let disposed = false
    const sync = async () => {
      let enabled = false
      try { enabled = window.localStorage.getItem('chengzhu-conversation-reminders') === '1' } catch { /* storage unavailable */ }
      if (!enabled) {
        await api.syncConversationReminders?.({ enabled: false, items: [] }).catch(() => {})
        return
      }
      try {
        const result = await conversationApi.reminders(30, 100)
        if (disposed) return
        await api.syncConversationReminders?.({
          enabled: true,
          leadMinutes: 10,
          items: result.items.map((item) => ({
            session_id: item.session_id,
            space_id: item.space_id,
            scheduled_at: item.scheduled_at,
          })),
        })
      } catch {
        // Reminder discovery is optional product surface; never block the shell.
      }
    }

    void sync()
    const onChanged = () => { void sync() }
    window.addEventListener('chengzhu-conversation-reminders-changed', onChanged)
    const timer = window.setInterval(() => { void sync() }, 5 * 60 * 1000)
    return () => {
      disposed = true
      window.removeEventListener('chengzhu-conversation-reminders-changed', onChanged)
      window.clearInterval(timer)
    }
  }, [route.path])

  const hasGuided = useRef(false)
  useEffect(() => {
    if (hasGuided.current) return
    // Conversation Beta can run on local deterministic logic without any LLM
    // API key. Never block its deep-linked pages with the Interview model drawer.
    if (shouldPromptForInterviewModel(config, productProfile, route.name)) {
      hasGuided.current = true
      openModelsDrawer()
    }
  }, [config, productProfile, route.name, openModelsDrawer])

  // Global shortcuts: Ctrl+K command palette · Ctrl+, settings · Ctrl+P pin (practice/live) ·
  // Ctrl+Shift+J transcript panel (live).
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey
      if (!mod || e.altKey) return
      const key = e.key.toLowerCase()
      if (key === 'k' && !e.shiftKey) {
        e.preventDefault()
        setCommandPalette(true)
        return
      }
      if (key === ',' && !e.shiftKey) {
        e.preventDefault()
        navigate(paths.settings())
        return
      }
      if (key === 'p' && !e.shiftKey) {
        const os = useOsStore.getState()
        if (os.live || os.activePracticeId) {
          e.preventDefault()
          setPinDialog(true)
        }
        return
      }
      if (key === 'j' && e.shiftKey && inLive) {
        const target = e.target as HTMLElement | null
        const tag = target?.tagName?.toLowerCase()
        if (tag === 'input' || tag === 'textarea' || target?.isContentEditable) return
        e.preventDefault()
        toggleAssistTranscriptCollapsed()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [inLive, setCommandPalette, setPinDialog, toggleAssistTranscriptCollapsed])

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

  const modelHealth = useInterviewStore((s) => s.modelHealth)
  const modelHealthDetail = useInterviewStore((s) => s.modelHealthDetail)
  const modelHealthLatency = useInterviewStore((s) => s.modelHealthLatency)
  const fallbackToast = useInterviewStore((s) => s.fallbackToast)
  const toastMessage = useInterviewStore((s) => s.toastMessage)
  const toasts = useInterviewStore((s) => s.toasts)
  const dismissToast = useInterviewStore((s) => s.dismissToast)
  const wsIsLeader = useInterviewStore((s) => s.wsIsLeader)
  const activeNavItems = productProfile === 'conversation' ? CONVERSATION_NAV_ITEMS : INTERVIEW_NAV_ITEMS
  const currentNav = activeNavItems.find((n) => n.match.includes(route.name))
  const currentLabel = inLive
    ? t('action.goLive')
    : inConversationLive
      ? t('action.startConversation')
      : route.name === 'settings'
        ? t('nav.settings')
        : currentNav
          ? t(currentNav.label)
          : t(productProfile === 'conversation' ? 'nav.conversationHome' : 'nav.home')

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
    const currentIds = new Set(toasts.map((x) => x.id))
    for (const [id, timer] of timers) {
      if (!currentIds.has(id)) { clearTimeout(timer); timers.delete(id) }
    }
    for (const x of toasts) {
      if (!timers.has(x.id)) {
        const timer = setTimeout(() => useInterviewStore.getState().dismissToast(x.id), x.ttlMs)
        timers.set(x.id, timer)
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
      <header className="app-drag-region header-gradient flex flex-row items-center justify-between gap-2 px-3 md:px-5 py-3 flex-shrink-0 min-w-0">
        <div className="flex items-center gap-2 md:gap-2.5 flex-shrink min-w-0 overflow-hidden">
          <div className="flex items-center gap-2.5">
            <div className="sig-tile w-8 h-8 rounded-xl">
              <WorkbenchMark className="w-4 h-4" />
            </div>
            {/* SAFETY: keep the brand as the shell's only level-1 heading so the
                document keeps a landmark for screen readers. */}
            <h1 className="text-sm font-bold hidden lg:block flex-shrink-0 tracking-tight">成竹</h1>
          </div>

          <div className="app-no-drag relative ml-1 hidden sm:block">
            <label className="sr-only" htmlFor="product-profile">{t('action.profile')}</label>
            <select id="product-profile" value={productProfile} onChange={(e) => switchProfile(e.target.value as ProductProfile)}
              className="rounded-xl border border-bg-hover/40 bg-bg-tertiary/45 px-2.5 py-1.5 text-xs font-medium text-text-primary outline-none focus:border-accent-blue/60"
              aria-label={t('action.profile')}>
              <option value="interview">面试</option>
              <option value="conversation">对话 Beta</option>
            </select>
          </div>

          <div className="relative ml-1 md:hidden" ref={moduleMenuRef}>
            <button type="button" onClick={() => setModuleMenuOpen((prev) => !prev)} aria-haspopup="menu" aria-expanded={moduleMenuOpen} aria-label={t('action.modules')}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-xs font-medium transition-colors ${moduleMenuOpen ? 'border-accent-blue/40 bg-accent-blue/10 text-accent-blue' : 'border-bg-hover/30 bg-bg-tertiary/60 text-text-primary'}`}>
              <MonitorSmartphone className="h-3.5 w-3.5" aria-hidden />
              <span className="max-w-[88px] truncate">{currentLabel}</span>
              <ChevronDown className={`h-3.5 w-3.5 transition-transform ${moduleMenuOpen ? 'rotate-180' : ''}`} aria-hidden />
            </button>
            {moduleMenuOpen ? (
              <div role="menu" aria-label={t('nav.label')} className="absolute left-0 top-[calc(100%+0.5rem)] z-40 min-w-[180px] glass-popover rounded-2xl p-2 animate-fade-up">
                {[...activeNavItems, { key: 'settings', label: 'nav.settings' as StringKey, Icon: Settings, path: paths.settings(), match: ['settings'] as RouteName[] }].map((item) => (
                  <button key={item.key} type="button" role="menuitem" onClick={() => { navigate(item.path); setModuleMenuOpen(false) }}
                    className={`flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition-colors ${item.match.includes(route.name) ? 'bg-container-primary text-container-on-primary' : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary'}`}>
                    <span>{t(item.label)}</span>
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          {inLive ? (
            isRecording ? (
              <div className={`flex items-center gap-1.5 ml-1.5 flex-shrink-0 rounded-lg px-2 py-1 border animate-fade-up ${isPaused ? 'bg-accent-amber/10 border-accent-amber/30' : 'bg-accent-red/10 border-accent-red/30'}`}
                role="status" aria-live="polite" title={isPaused ? '录音已暂停' : isExamMode ? '笔试进行中' : '正在录音中'}>
                <span className={`relative inline-flex w-1.5 h-1.5 rounded-full ${isPaused ? 'bg-accent-amber' : 'bg-accent-red'}`} aria-hidden />
                <span className={`text-[10px] font-semibold leading-none hidden sm:inline ${isPaused ? 'text-accent-amber' : 'text-accent-red'}`}>{isPaused ? 'PAUSED' : isExamMode ? 'EXAM' : 'REC'}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 ml-1.5 flex-shrink-0 bg-bg-tertiary/30 rounded-lg px-2 py-1 border border-bg-hover/20"
                title={sttLoaded ? 'STT 就绪 · 等待录音' : sttLoading ? 'STT 模型加载中…' : 'STT 模型尚未加载，首次录音时会自动加载'}>
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${sttLoaded ? (sttActiveProvider === 'whisper' ? 'bg-accent-amber' : 'bg-accent-green') : sttLoading ? 'bg-accent-amber animate-pulse' : 'bg-accent-red'}`} aria-hidden />
                <span className="text-[10px] text-text-muted hidden md:inline font-medium">{sttLoaded ? 'STT 就绪' : sttLoading ? '加载中' : '未加载'}</span>
              </div>
            )
          ) : null}
        </div>

        <div className="flex items-center gap-1.5 md:gap-2 flex-shrink-0 flex-nowrap justify-end">
          {inLive && config?.models && config.models.length > 0 && (
            <ModelPriorityDropdown config={config} modelHealth={modelHealth} modelHealthDetail={modelHealthDetail} modelHealthLatency={modelHealthLatency} onModelChange={handleModelChange} />
          )}
          {inLive ? <WorkbenchPopover memoPinned={memoVisible} onToggleMemoPin={toggleMemoVisible} /> : null}
          {inLive ? (
            <div className="relative">
              <button ref={sessionAnchorRef} type="button" onClick={() => setSessionPopoverOpen((v) => !v)} title="会场设置：Think / 岗位 / 语言 / Token" aria-haspopup="dialog" aria-expanded={sessionPopoverOpen} aria-label="打开会场设置"
                className={`relative inline-flex items-center gap-1.5 rounded-xl px-2.5 py-1.5 text-xs border transition-all duration-200 flex-shrink-0 ${sessionPopoverOpen ? 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue' : 'border-bg-hover/50 bg-bg-tertiary/50 text-text-secondary hover:border-accent-blue/40 hover:text-text-primary'}`}>
                <SlidersHorizontal className="w-3.5 h-3.5" aria-hidden />
                <span className="font-medium hidden sm:inline">会场</span>
              </button>
              <SessionSettingsPopover open={sessionPopoverOpen} onClose={() => setSessionPopoverOpen(false)} anchorRef={sessionAnchorRef} />
            </div>
          ) : null}
          {inLive && (
            <button type="button" onClick={toggleAssistTranscriptCollapsed} className={`hidden md:inline-flex ${HEADER_ICON_BTN}`}
              title={assistTranscriptCollapsed ? '显示实时转录面板 (Ctrl+Shift+J)' : '隐藏实时转录面板 (Ctrl+Shift+J)'}
              aria-label={assistTranscriptCollapsed ? '显示实时转录面板' : '隐藏实时转录面板'} aria-expanded={!assistTranscriptCollapsed}>
              {assistTranscriptCollapsed ? <PanelLeftOpen className="w-4 h-4" /> : <PanelLeftClose className="w-4 h-4" />}
            </button>
          )}
          <KnowledgeButton />
          <button type="button" onClick={() => setCommandPalette(true)} className={`inline-flex ${HEADER_ICON_BTN}`} title={`${t('action.commands')} (Ctrl+K)`} aria-label={t('action.commands')}>
            <CommandIcon className="w-4 h-4" aria-hidden />
          </button>
          {!inLive && productProfile === 'interview' ? (
            <button type="button" onClick={() => openGoLive()} data-testid="go-live"
              className="btn-primary inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold min-h-[32px]">
              <Radio className="h-3.5 w-3.5" aria-hidden /> {t('action.goLive')}
            </button>
          ) : null}
          {!inConversationLive && productProfile === 'conversation' ? (
            <button type="button" onClick={startConversation} data-testid="start-conversation"
              className="btn-primary inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold min-h-[32px]">
              <Radio className="h-3.5 w-3.5" aria-hidden /> 开始
            </button>
          ) : null}
          {window.electronAPI && (
            <>
              <button type="button" onClick={() => window.electronAPI?.minimizeWindow()} className={`inline-flex ${HEADER_ICON_BTN}`} title="最小化" aria-label={t('action.minimize')}>
                <Minus className="w-4 h-4" />
              </button>
              <button type="button" onClick={() => window.electronAPI?.quitApp()} className={`inline-flex ${HEADER_ICON_BTN} hover:border-accent-red/40 hover:text-accent-red`} title="退出" aria-label={t('action.quit')}>
                <X className="w-4 h-4" />
              </button>
            </>
          )}
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <AppNavRail current={route.name} profile={productProfile} />
        <div className="flex flex-col flex-1 min-w-0 min-h-0">
          {inLive ? <LiveCockpit /> : (
            <PageErrorBoundary resetKey={route.path}>
              <Suspense fallback={<PageFallback />}>
                {route.name === 'home' ? <HomePage /> : null}
                {route.name === 'goals' ? <GoalsPage /> : null}
                {route.name === 'goal' ? <GoalRoom goalId={route.params.goalId} tab={route.params.tab as 'overview'} /> : null}
                {route.name === 'me' ? <MePage tab={route.params.tab} /> : null}
                {route.name === 'practice' ? <PracticePage practiceId={route.params.practiceId} query={route.query} /> : null}
                {route.name === 'library' ? <LibraryPage tab={route.params.tab} /> : null}
                {route.name === 'history' ? (productProfile === 'conversation' ? <ConversationHistoryPage /> : <HistoryPage initialGoalId={route.query.goal ?? ''} />) : null}
                {route.name === 'reflection' ? <ReflectionPage kind={route.params.kind} sessionRef={route.params.ref} /> : null}
                {route.name === 'settings' ? <SettingsPage group={route.params.group} query={route.query} /> : null}
                {route.name === 'conversation-home' ? <ConversationHome /> : null}
                {route.name === 'conversation-onboarding' ? <ConversationOnboardingPage /> : null}
                {route.name === 'conversations' ? <ConversationSpacesPage query={route.query} /> : null}
                {route.name === 'conversation' ? <ConversationSpacePage spaceId={route.params.spaceId} tab={route.params.tab as ConversationTab} /> : null}
                {route.name === 'conversation-live' ? <ConversationLivePage sessionId={route.params.sessionId} /> : null}
              </Suspense>
            </PageErrorBoundary>
          )}

          <AppToastStack wsIsLeader={wsIsLeader} fallbackToast={fallbackToast} toasts={toasts} dismissToast={dismissToast} />
          <SettingsDrawer />
          <KnowledgeDrawer />
          <OnboardingWizard />
          <CreateGoalDialog />
          <GoLiveDialog />
          <CommandPalette />
          <PinDialog />
          <QuickNotesDrawer />
        </div>
      </div>
    </div>
  )
}
