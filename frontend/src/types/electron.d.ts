import type { OverlayStatePayload } from '@/lib/interviewOverlay'

export {}

declare global {
  interface Window {
    electronAPI?: {
    hideWindow: () => Promise<void>
    minimizeWindow: () => Promise<void>
    quitApp: () => Promise<void>
    showWindow: () => Promise<void>
      getShortcuts: () => Promise<Record<string, { action: string; key: string; defaultKey: string; label: string; category: string; status?: string }>>
      updateShortcuts: (shortcuts: Array<{ action: string; key: string }>) => Promise<{ ok: boolean; error?: string; shortcuts: Record<string, unknown> }>
      resetShortcuts: () => Promise<{ ok: boolean; error?: string; shortcuts: Record<string, unknown> }>
      toggleAlwaysOnTop: () => Promise<boolean>
      toggleContentProtection: () => Promise<boolean>
      setSharePrivacy?: (mode: 'OFF' | 'PRIVATE_OVERLAY' | string) => Promise<string>
      getSharePrivacy?: () => Promise<{
        mode: string
        protected: boolean
        runtime_verified?: boolean
        main_window_protected?: boolean | null
        overlay_window_protected?: boolean | null
        platform?: string
        windows_capture_exclusion_may_lag?: boolean
        macos_screencapturekit_limitation?: boolean
        note: string
      }>
      getWindowState: () => Promise<{ alwaysOnTop: boolean; contentProtection: boolean; visible: boolean }>
      captureRegion?: () => Promise<{ left: number; top: number; width: number; height: number } | null>
      syncOverlayWindow?: (payload: Partial<OverlayStatePayload> & { visible?: boolean }) => Promise<{ ok: boolean; visible: boolean }>
      resizeOverlayWindow?: (payload: { width?: number; height?: number }) => Promise<{ ok: boolean; width?: number; height?: number; skipped?: boolean }>
      destroyOverlay?: () => Promise<{ ok: boolean }>
      moveOverlayWindow?: (dx: number, dy: number) => Promise<void>
      overlayDragStart?: () => void
      overlayDragEnd?: () => void
      getOverlayState?: () => Promise<(OverlayStatePayload & { visible: boolean }) | null>
      setOverlayLayout?: (layout: { dock?: string; interaction?: string; size?: string }) => Promise<{ ok: boolean; layout: { dock: string; interaction: string; size: string } }>
      onOverlayState?: (callback: (payload: OverlayStatePayload) => void) => (() => void)
      onShortcuts?: (callback: (payload: Record<string, Record<string, unknown>> | undefined) => void) => (() => void)
      onFocusTabCommand?: (callback: (direction: 'prev' | 'next') => void) => (() => void)
      onOverlayQuestionCommand?: (callback: (direction: 'prev' | 'next') => void) => (() => void)
      removeOverlayStateListener?: (listener?: (...args: unknown[]) => void) => void
    }
  }
}
