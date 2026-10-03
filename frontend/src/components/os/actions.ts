/** One place that turns product action keys into navigation / flows. */
import { navigate, paths, type GoalTab } from '@/lib/router'
import type { PracticeDefaults } from '@/lib/productApi'
import { track } from '@/lib/productApi'
import { useOsStore } from '@/stores/osStore'

export function openGoal(goalId: string, tab: GoalTab = 'overview'): void {
  navigate(paths.goal(goalId, tab))
}

export function startPractice(goalId?: string | null, defaults?: Partial<PracticeDefaults> | null): void {
  const query: Record<string, string> = {}
  if (goalId) query.goal = goalId
  if (defaults?.round) query.round = defaults.round
  if (defaults?.focus?.id) query.focus = defaults.focus.id
  navigate(paths.practice(undefined, query))
}

export function goLive(goalId?: string | null): void {
  useOsStore.getState().openGoLive(goalId ?? null)
}

/** Dispatch a server-provided action key (Home attention items, Next Focus actions …). */
export function runActionKey(key: string, ctx: { goalId?: string | null; target?: string; focusTitle?: string } = {}): void {
  track('command_executed', { key, source: 'action' }, { goal_id: ctx.goalId ?? '' })
  switch (key) {
    case 'create_goal':
      useOsStore.getState().openCreateGoal()
      return
    case 'continue_prepare':
      if (ctx.goalId) openGoal(ctx.goalId, 'prepare')
      else navigate(paths.goals())
      return
    case 'open_goal':
      if (ctx.goalId) openGoal(ctx.goalId)
      return
    case 'start_practice':
    case 'practice':
      startPractice(ctx.goalId)
      return
    case 'preflight':
      goLive(ctx.goalId)
      return
    case 'open_fact_inbox':
    case 'confirm_fact':
      navigate(paths.me('inbox'))
      return
    case 'open_stories':
    case 'create_story':
    case 'story_builder':
      navigate(paths.me('stories'))
      return
    case 'open_library':
      navigate(paths.library('materials'))
      return
    case 'add_source':
      navigate(paths.me('inbox'))
      return
    case 'learn':
      navigate(paths.library('knowledge'))
      return
    case 'add_quick_note':
      useOsStore.getState().setQuickNotes(true)
      return
    case 'open_settings':
      navigate(paths.settings(ctx.target || 'general'))
      return
    default:
      return
  }
}
