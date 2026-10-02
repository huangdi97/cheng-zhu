/**
 * v1.3 shell UI state: global dialogs/flows (UI state only — domain data
 * stays on the server and in page-local fetches).
 */
import { create } from 'zustand'

export interface LiveContext {
  sessionId: string
  goalId: string | null
  goalTitle: string
  startedAt: number
}

interface OsState {
  createGoalOpen: boolean
  goLiveOpen: boolean
  goLiveGoalId: string | null
  commandPaletteOpen: boolean
  pinDialogOpen: boolean
  quickNotesOpen: boolean
  /** Goal the user is currently looking at (Goal Room / Practice); drives context ranking. */
  contextGoalId: string | null
  live: LiveContext | null
  /** Practice session the Pin shortcut should attach to (Practice page sets it). */
  activePracticeId: string | null
  activePracticeQuestion: string
  /** Live memo side panel pinned (moved from App; persisted). */
  memoVisible: boolean
  toggleMemoVisible: () => void
  openCreateGoal: () => void
  closeCreateGoal: () => void
  openGoLive: (goalId?: string | null) => void
  closeGoLive: () => void
  setCommandPalette: (open: boolean) => void
  setPinDialog: (open: boolean) => void
  setQuickNotes: (open: boolean) => void
  setContextGoal: (goalId: string | null) => void
  setLive: (live: LiveContext | null) => void
  setActivePractice: (id: string | null, question?: string) => void
}

export const useOsStore = create<OsState>((set) => ({
  createGoalOpen: false,
  goLiveOpen: false,
  goLiveGoalId: null,
  commandPaletteOpen: false,
  pinDialogOpen: false,
  quickNotesOpen: false,
  contextGoalId: null,
  live: null,
  activePracticeId: null,
  activePracticeQuestion: '',
  memoVisible: (() => {
    try { return localStorage.getItem('ia-memo-visible') === '1' } catch { return false }
  })(),
  toggleMemoVisible: () => set((s) => {
    const next = !s.memoVisible
    try { localStorage.setItem('ia-memo-visible', next ? '1' : '0') } catch { /* ignore */ }
    return { memoVisible: next }
  }),
  openCreateGoal: () => set({ createGoalOpen: true }),
  closeCreateGoal: () => set({ createGoalOpen: false }),
  openGoLive: (goalId) => set((s) => ({ goLiveOpen: true, goLiveGoalId: goalId ?? s.contextGoalId })),
  closeGoLive: () => set({ goLiveOpen: false }),
  setCommandPalette: (open) => set({ commandPaletteOpen: open }),
  setPinDialog: (open) => set({ pinDialogOpen: open }),
  setQuickNotes: (open) => set({ quickNotesOpen: open }),
  setContextGoal: (goalId) => set({ contextGoalId: goalId }),
  setLive: (live) => set({ live }),
  setActivePractice: (id, question = '') => set({ activePracticeId: id, activePracticeQuestion: id ? question : '' }),
}))
