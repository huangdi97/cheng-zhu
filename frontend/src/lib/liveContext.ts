/** Shared between the main window and the overlay renderer (same origin). */
export const LIVE_CONTEXT_KEY = 'chengzhu-live-context'

export function setLiveContextLabel(label: string): void {
  try {
    if (label) localStorage.setItem(LIVE_CONTEXT_KEY, label)
    else localStorage.removeItem(LIVE_CONTEXT_KEY)
  } catch {
    /* ignore */
  }
}
