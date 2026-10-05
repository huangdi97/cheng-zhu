/**
 * v1.3 Overlay 3.0 preferences: Dock × Interaction × Size (+ auto-compact).
 * Persisted in localStorage so the separate overlay renderer (same origin)
 * reads the same values and follows changes through the `storage` event.
 */
import { create } from 'zustand'

export type OverlayDock = 'TOP' | 'LEFT' | 'RIGHT' | 'FREE'
export type OverlayInteraction = 'PASSIVE' | 'INTERACTIVE'
export type OverlaySize = 'COMPACT' | 'STANDARD' | 'FOCUS'

export interface OverlayLayout {
  dock: OverlayDock
  interaction: OverlayInteraction
  size: OverlaySize
  autoCompact: boolean
}

export const OVERLAY_LAYOUT_KEY = 'chengzhu-overlay-layout-v1'
const DEFAULT: OverlayLayout = { dock: 'FREE', interaction: 'INTERACTIVE', size: 'STANDARD', autoCompact: true }

export function readOverlayLayout(): OverlayLayout {
  try {
    const raw = JSON.parse(localStorage.getItem(OVERLAY_LAYOUT_KEY) || '{}') as Partial<OverlayLayout>
    return {
      dock: (['TOP', 'LEFT', 'RIGHT', 'FREE'] as const).includes(raw.dock as OverlayDock) ? (raw.dock as OverlayDock) : DEFAULT.dock,
      interaction: raw.interaction === 'PASSIVE' ? 'PASSIVE' : 'INTERACTIVE',
      size: (['COMPACT', 'STANDARD', 'FOCUS'] as const).includes(raw.size as OverlaySize) ? (raw.size as OverlaySize) : DEFAULT.size,
      autoCompact: raw.autoCompact !== false,
    }
  } catch {
    return DEFAULT
  }
}

interface State extends OverlayLayout {
  setLayout: (patch: Partial<OverlayLayout>) => void
  reload: () => void
}

export const useOverlayLayout = create<State>((set) => ({
  ...readOverlayLayout(),
  setLayout: (patch) => {
    const next = { ...readOverlayLayout(), ...patch }
    try {
      localStorage.setItem(OVERLAY_LAYOUT_KEY, JSON.stringify(next))
    } catch {
      /* ignore */
    }
    set(next)
    void window.electronAPI?.setOverlayLayout?.({ dock: next.dock, interaction: next.interaction, size: next.size })
  },
  reload: () => set(readOverlayLayout()),
}))

/**
 * Size the overlay should show right now: idle → COMPACT when auto-compact
 * is on; a fresh cue expands to the chosen size (never smaller than STANDARD).
 */
export function effectiveOverlaySize(layout: OverlayLayout, active: boolean): OverlaySize {
  if (layout.size === 'COMPACT') return active ? 'STANDARD' : 'COMPACT'
  if (!active && layout.autoCompact) return 'COMPACT'
  return layout.size
}
