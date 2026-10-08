/** Conversation-owned UI truth: a Live page is not proof that audio is listening. */
export type CaptureViewState = {
  label: string
  listening: boolean
}

export function captureViewState(
  session: { id?: string; status: string; capture_mode: string },
  capture: {
    active: boolean
    owns_requested_session: boolean
    session_id?: string
    paused?: boolean
  } | null,
  statusUnavailable = false,
): CaptureViewState {
  if (session.status === 'ENDED') return { label: '会话已结束', listening: false }
  if (session.status !== 'ACTIVE') return { label: '会话尚未开始', listening: false }
  if (session.capture_mode !== 'TRANSCRIPT') {
    return { label: session.capture_mode === 'NOTES_ONLY' ? '仅笔记 · 未采集音频' : '未采集音频', listening: false }
  }
  if (statusUnavailable) return { label: '音频状态不可确认', listening: false }
  if (!capture) return { label: '正在确认音频状态', listening: false }
  // Capture status can briefly survive a route/session switch. Ownership is
  // meaningful only for the exact Session named by the backend response.
  if (capture.owns_requested_session && session.id && capture.session_id !== session.id) {
    return { label: '正在确认本场音频状态', listening: false }
  }
  if (capture.active && capture.owns_requested_session) {
    return capture.paused
      ? { label: '转写已暂停', listening: false }
      : { label: '正在采集并转写', listening: true }
  }
  if (capture.active) return { label: '其他会话正在使用音频', listening: false }
  return { label: '转写未启动', listening: false }
}

/**
 * The Guidance history is newest-first. A later SILENT/suppressed event must
 * clear the prior card instead of resurrecting an older SHOWN event.
 */
export function latestVisibleGuidance<T extends { status: string; user_action: string; kind?: string }>(
  events: readonly T[],
): T | null {
  // Human Coach advice has its own session-scoped realtime surface. It is also
  // retained in guidance_history for audit, but must never masquerade as the
  // AI primary card or clear an existing AI card.
  const newest = events.find((event) => event.kind !== 'HUMAN_COACH')
  if (!newest || newest.status !== 'SHOWN') return null
  return ['NONE', 'EXPANDED', 'PINNED'].includes(newest.user_action) ? newest : null
}

/** Serialize Live polls and invalidate responses pre-dating a capture action. */
export function createLivePollGate() {
  let inFlight = false
  let epoch = 0
  return {
    begin(): number | null {
      if (inFlight) return null
      inFlight = true
      return epoch
    },
    current(ticket: number): boolean {
      return ticket === epoch
    },
    invalidate(): void {
      epoch += 1
    },
    finish(): void {
      inFlight = false
    },
  }
}
