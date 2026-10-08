import { beforeEach, describe, expect, it, vi } from 'vitest'
import { parsePath, useRouter } from '@/lib/router'
import { useOsStore } from '@/stores/osStore'
import { useOverlayLayout } from '@/stores/overlayLayoutStore'
import { buildCommands, contextOf, executeCommand, rankCommands } from './commands'

vi.mock('@/lib/productApi', () => ({
  productApi: { home: vi.fn(async () => ({ next_interview: { goal_id: 'g_next' }, focus_goal: null })) },
  track: vi.fn(),
}))

vi.mock('@/lib/conversationApi', () => ({
  conversationApi: {
    home: vi.fn(async () => ({ next_session: { space_id: 'cs-next' }, next_focus: null })),
    adhoc: vi.fn(async () => ({ session: { id: 'cv-adhoc' } })),
    patchSession: vi.fn(async () => ({})),
    exportSession: vi.fn(async () => ({ session: { id: 'cv-1', title: 'Architecture Review' } })),
  },
}))

vi.mock('@/lib/api', () => ({
  api: { askFromServerScreen: vi.fn(async () => ({})), ask: vi.fn(async () => ({})), stop: vi.fn(async () => ({})), intelSessionClaims: vi.fn(async () => []), intelResolveSessionClaim: vi.fn() },
}))

describe('Command Palette', () => {
  beforeEach(() => {
    useRouter.setState({ route: parsePath('#/home') })
    useOsStore.setState({ createGoalOpen: false, quickNotesOpen: false, pinDialogOpen: false })
  })

  it('ranks the current context first', () => {
    const cmds = buildCommands('g1')
    const home = rankCommands(cmds, '', 'home').slice(0, 4).map((c) => c.id)
    expect(home).toEqual(['create-goal', 'open-next', 'start-practice', 'go-live'])
    const live = rankCommands(cmds, '', 'live').slice(0, 3).map((c) => c.id)
    expect(live).toContain('toggle-overlay')
    expect(rankCommands(cmds, '', 'me')[0].id).toBe('confirm-facts')
    expect(rankCommands(cmds, 'pin', 'goal').map((c) => c.id)).toContain('pin')
    expect(contextOf(parsePath('#/goals/g1/prepare'))).toBe('goal')
    expect(contextOf(parsePath('#/conversation'))).toBe('conversation-home')
    expect(contextOf(parsePath('#/conversation/spaces/cs-1'))).toBe('conversation-space')
    expect(contextOf(parsePath('#/conversation/live/cv-1'))).toBe('conversation-live')
  })

  it('ranks Conversation commands in Conversation contexts', () => {
    const route = parsePath('#/conversation/live/cv-1')
    const cmds = buildCommands(null, route)
    const live = rankCommands(cmds, '', 'conversation-live').slice(0, 4).map((c) => c.id)
    expect(live).toContain('conversation-quiet')
    expect(live).toContain('conversation-balanced')
    expect(live).toContain('conversation-quick-note')
    expect(live).toContain('conversation-export-session')
    expect(rankCommands(cmds, 'Decision', 'conversation-live').map((c) => c.id)).toContain('conversation-find-decision')
  })

  it('executes real actions, not a search demo', async () => {
    const cmds = buildCommands('g1')
    await executeCommand(cmds.find((c) => c.id === 'create-goal')!, 'home')
    expect(useOsStore.getState().createGoalOpen).toBe(true)
    await executeCommand(cmds.find((c) => c.id === 'open-next')!, 'home')
    expect(useRouter.getState().route).toMatchObject({ name: 'goal', params: { goalId: 'g_next' } })
    await executeCommand(cmds.find((c) => c.id === 'continue-prepare')!, 'goal')
    expect(useRouter.getState().route.params.tab).toBe('prepare')
    await executeCommand(cmds.find((c) => c.id === 'overlay-compact')!, 'live')
    expect(useOverlayLayout.getState().size).toBe('COMPACT')
    await executeCommand(cmds.find((c) => c.id === 'pin')!, 'live')
    expect(useOsStore.getState().pinDialogOpen).toBe(true)
    await executeCommand(cmds.find((c) => c.id === 'nav-settings')!, 'global')
    expect(useRouter.getState().route.name).toBe('settings')

    const conversationRoute = parsePath('#/conversation')
    const conversationCommands = buildCommands(null, conversationRoute)
    await executeCommand(conversationCommands.find((c) => c.id === 'conversation-adhoc')!, 'conversation-home')
    expect(useRouter.getState().route).toMatchObject({ name: 'conversation-live', params: { sessionId: 'cv-adhoc' } })
    useRouter.setState({ route: parsePath('#/conversation') })
    await executeCommand(conversationCommands.find((c) => c.id === 'conversation-prepare-next')!, 'conversation-home')
    expect(useRouter.getState().route).toMatchObject({ name: 'conversation', params: { spaceId: 'cs-next', tab: 'prepare' } })

    useRouter.setState({ route: parsePath('#/conversation') })
    await executeCommand(conversationCommands.find((c) => c.id === 'conversation-find-decision')!, 'conversation-home')
    expect(useRouter.getState().route).toMatchObject({ name: 'conversations', query: { find: 'Decision' } })
  })
})
