/**
 * Command Palette registry (canonical §19). Every command executes a real
 * action — navigation, a backend call or a live control — never a demo.
 * Ranking: commands of the current context first, then global ones.
 */
import { api } from '@/lib/api'
import { conversationApi } from '@/lib/conversationApi'
import { navigate, paths, useRouter, type Route } from '@/lib/router'
import { productApi, track } from '@/lib/productApi'
import { useInterviewStore } from '@/stores/configStore'
import { useOsStore } from '@/stores/osStore'
import { useOverlayLayout } from '@/stores/overlayLayoutStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'
import { goLive, openGoal, startPractice } from './actions'

export type CommandContext =
  | 'home'
  | 'goal'
  | 'live'
  | 'me'
  | 'practice'
  | 'conversation-home'
  | 'conversation-space'
  | 'conversation-live'
  | 'global'

export interface Command {
  id: string
  label: string
  contexts: CommandContext[]
  keywords?: string
  run: () => void | Promise<unknown>
}

export function contextOf(route: Route): CommandContext {
  switch (route.name) {
    case 'home':
      return 'home'
    case 'goal':
    case 'goals':
      return 'goal'
    case 'live':
      return 'live'
    case 'me':
      return 'me'
    case 'practice':
      return 'practice'
    case 'conversation-home':
    case 'conversations':
      return 'conversation-home'
    case 'conversation':
      return 'conversation-space'
    case 'conversation-live':
      return 'conversation-live'
    default:
      return 'global'
  }
}

function currentRoute(): Route {
  return useRouter.getState().route
}

function toast(message: string): void {
  useInterviewStore.getState().setToastMessage?.(message)
}

function latestQuestion(): string {
  const qa = useInterviewStore.getState().qaPairs
  return qa.length ? qa[qa.length - 1].question : ''
}

export function buildCommands(goalId: string | null, route: Route = currentRoute()): Command[] {
  const os = useOsStore.getState()
  const overlay = useOverlayLayout.getState()
  return [
    // --- Home ---
    { id: 'create-goal', label: '创建求职目标', contexts: ['home', 'goal'], keywords: 'goal new 新建 目标', run: () => os.openCreateGoal() },
    {
      id: 'open-next', label: '打开下一场', contexts: ['home'], keywords: 'next interview 下一轮',
      run: async () => {
        const home = await productApi.home()
        if (home.next_interview) openGoal(home.next_interview.goal_id)
        else if (home.focus_goal) openGoal(home.focus_goal.id)
        else toast('还没有安排下一场')
      },
    },
    { id: 'start-practice', label: '开始练习', contexts: ['home', 'goal', 'practice'], keywords: 'practice mock 演练', run: () => startPractice(goalId) },
    { id: 'go-live', label: '上场', contexts: ['home', 'goal'], keywords: 'live interview 面试 开始', run: () => goLive(goalId) },
    // --- Goal ---
    { id: 'continue-prepare', label: '继续准备', contexts: ['goal'], keywords: 'prepare 准备', run: () => (goalId ? openGoal(goalId, 'prepare') : navigate(paths.goals())) },
    { id: 'quick-note', label: '创建速记 / 打开速记', contexts: ['goal', 'live', 'practice'], keywords: 'quick note 速记 笔记', run: () => os.setQuickNotes(true) },
    { id: 'add-material', label: '添加资料', contexts: ['goal'], keywords: 'material upload 资料 上传', run: () => navigate(paths.library('materials')) },
    { id: 'preflight', label: 'Preflight（上场前检查）', contexts: ['goal'], keywords: 'preflight 检查', run: () => goLive(goalId) },
    // --- Live ---
    {
      id: 'toggle-overlay', label: '打开 / 关闭浮窗', contexts: ['live'], keywords: 'overlay 浮窗',
      run: () => {
        const visible = !useUiPrefsStore.getState().interviewOverlayVisible
        void window.electronAPI?.syncOverlayWindow?.({ visible })
        useUiPrefsStore.setState({ interviewOverlayVisible: visible })
      },
    },
    { id: 'screenshot', label: '截图审题', contexts: ['live'], keywords: 'screenshot 截图 屏幕', run: () => api.askFromServerScreen().then(() => toast('已提交截图审题')) },
    { id: 'pin', label: '标记这一刻（Pin）', contexts: ['live', 'practice'], keywords: 'pin 标记 ctrl+p', run: () => os.setPinDialog(true) },
    {
      id: 'mark-slip', label: '标记口误（最近一条说法）', contexts: ['live'], keywords: 'slip 口误 纠正',
      run: async () => {
        const claims = await api.intelSessionClaims().catch(() => [])
        const last = Array.isArray(claims) ? claims[claims.length - 1] : null
        if (!last) { toast('本场没有需要纠正的说法'); return }
        await api.intelResolveSessionClaim(String(last.id), 'slip')
        toast('已标记为口误')
      },
    },
    {
      id: 'reanswer', label: '重答最新问题', contexts: ['live'], keywords: 'regenerate retry 重答',
      run: () => {
        const q = latestQuestion()
        if (!q) { toast('还没有问题'); return }
        return api.ask(q)
      },
    },
    { id: 'overlay-compact', label: '浮窗：紧凑', contexts: ['live'], keywords: 'compact 紧凑', run: () => overlay.setLayout({ size: 'COMPACT' }) },
    { id: 'overlay-standard', label: '浮窗：标准', contexts: ['live'], keywords: 'standard 标准', run: () => overlay.setLayout({ size: 'STANDARD' }) },
    { id: 'overlay-focus', label: '浮窗：专注', contexts: ['live'], keywords: 'focus 专注', run: () => overlay.setLayout({ size: 'FOCUS' }) },
    {
      id: 'end-session', label: '结束本场', contexts: ['live'], keywords: 'stop end 结束 停止',
      run: async () => {
        if (!window.confirm('结束本场？将停止录音并进入复盘。')) return
        await api.stop()
      },
    },
    // --- Conversation Profile ---
    {
      id: 'conversation-new-space', label: '创建对话空间', contexts: ['conversation-home', 'conversation-space'],
      keywords: 'conversation space 新建 对话 空间',
      run: () => navigate(paths.conversationSpaces(undefined, { new: '1' })),
    },
    {
      id: 'conversation-adhoc', label: '开始临时会话', contexts: ['conversation-home', 'conversation-space'],
      keywords: 'adhoc 临时 会话 开始',
      run: async () => {
        const result = await conversationApi.adhoc({ title: '临时对话', profile: 'PROJECT_SYNC', assistance_mode: 'BALANCED' })
        navigate(paths.conversationLive(result.session.id))
      },
    },
    {
      id: 'conversation-prepare-next', label: '准备下一场', contexts: ['conversation-home'],
      keywords: 'prepare next 下一场 准备',
      run: async () => {
        const home = await conversationApi.home()
        if (home.next_session) navigate(paths.conversationSpace(home.next_session.space_id, 'prepare'))
        else if (home.next_focus?.space_id) navigate(paths.conversationSpace(home.next_focus.space_id, 'prepare'))
        else toast('还没有可以准备的对话空间')
      },
    },
    {
      id: 'conversation-decisions', label: '打开当前空间的决策', contexts: ['conversation-space'],
      keywords: 'decision 决策 agreed',
      run: () => {
        const spaceId = route.name === 'conversation' ? route.params.spaceId : ''
        if (spaceId) navigate(paths.conversationSpace(spaceId, 'decisions'))
        else navigate(paths.conversationSpaces())
      },
    },
    {
      id: 'conversation-quick-note', label: '创建速记 / 打开速记', contexts: ['conversation-space', 'conversation-live'],
      keywords: 'quick note 速记 笔记',
      run: () => os.setQuickNotes(true),
    },
    {
      id: 'conversation-quiet', label: '暂停主动建议（Quiet）', contexts: ['conversation-live'],
      keywords: 'pause quiet suggestions 暂停 建议 安静',
      run: async () => {
        const sessionId = route.name === 'conversation-live' ? route.params.sessionId : ''
        if (!sessionId) { toast('当前不在 Conversation Live'); return }
        await conversationApi.patchSession(sessionId, { assistance_mode: 'QUIET' })
        toast('已切换为 Quiet；直接 Ask 仍可使用')
      },
    },
    {
      id: 'conversation-balanced', label: '恢复主动建议（Balanced）', contexts: ['conversation-live'],
      keywords: 'resume balanced suggestions 恢复 建议',
      run: async () => {
        const sessionId = route.name === 'conversation-live' ? route.params.sessionId : ''
        if (!sessionId) { toast('当前不在 Conversation Live'); return }
        await conversationApi.patchSession(sessionId, { assistance_mode: 'BALANCED' })
        toast('已恢复 Balanced')
      },
    },
    // --- Me ---
    { id: 'confirm-facts', label: '确认事实（待确认）', contexts: ['me', 'home'], keywords: 'fact inbox 事实 确认', run: () => navigate(paths.me('inbox')) },
    { id: 'create-story', label: '创建 Story', contexts: ['me'], keywords: 'story 故事', run: () => navigate(paths.me('stories')) },
    { id: 'practice-skill', label: '练这个 Skill', contexts: ['me'], keywords: 'skill 技能 练习', run: () => navigate(paths.practice(undefined, { round: 'PROJECT_DEEP_DIVE', ...(goalId ? { goal: goalId } : {}) })) },
    // --- Global navigation ---
    { id: 'nav-home', label: '去首页', contexts: ['global'], keywords: 'home 首页', run: () => navigate(paths.home()) },
    { id: 'nav-goals', label: '去求职目标', contexts: ['global'], keywords: 'goals 目标', run: () => navigate(paths.goals()) },
    { id: 'nav-me', label: '去我的成竹', contexts: ['global'], keywords: 'me resume 简历 我的', run: () => navigate(paths.me()) },
    { id: 'nav-practice', label: '去练习', contexts: ['global'], keywords: 'practice 练习', run: () => navigate(paths.practice()) },
    { id: 'nav-library', label: '去资料库', contexts: ['global'], keywords: 'library 资料 题库 知识库', run: () => navigate(paths.library()) },
    { id: 'nav-history', label: '去历史', contexts: ['global'], keywords: 'history 历史 复盘', run: () => navigate(paths.history()) },
    { id: 'nav-conversation', label: '去对话 Beta', contexts: ['global'], keywords: 'conversation 对话 beta', run: () => navigate(paths.conversationHome()) },
    { id: 'nav-settings', label: '打开设置', contexts: ['global'], keywords: 'settings 设置 ctrl+,', run: () => navigate(paths.settings()) },
  ]
}

export function rankCommands(commands: Command[], query: string, context: CommandContext): Command[] {
  const q = query.trim().toLowerCase()
  const scored = commands
    .map((c, index) => {
      const hay = `${c.label} ${c.keywords ?? ''}`.toLowerCase()
      if (q && !hay.includes(q)) return null
      const contextScore = c.contexts.includes(context) ? 0 : c.contexts.includes('global') ? 1 : 2
      const prefix = q && c.label.toLowerCase().startsWith(q) ? -0.5 : 0
      return { c, score: contextScore + prefix, index }
    })
    .filter((x): x is { c: Command; score: number; index: number } => x !== null)
  scored.sort((a, b) => a.score - b.score || a.index - b.index)
  return scored.map((x) => x.c)
}

export async function executeCommand(command: Command, context: CommandContext): Promise<void> {
  track('command_executed', { id: command.id, context })
  await command.run()
}
