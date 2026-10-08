export type SharePrivacyMode = 'OFF' | 'PRIVATE_OVERLAY'

export interface ConversationSharePrivacyRuntime {
  requested: SharePrivacyMode
  available: boolean
  protected: boolean
  active_mode: string
  note: string
  proof: string
}

const LEASE_KEY = 'chengzhu-conversation-share-privacy-leases-v1'
const BASELINE_KEY = 'chengzhu-conversation-share-privacy-baseline-v1'
export const SHARE_PRIVACY_PROOF = 'ELECTRON_CONTENT_PROTECTION_ACTIVE'

function readLeases(): Record<string, true> {
  try {
    const parsed = JSON.parse(window.sessionStorage.getItem(LEASE_KEY) || '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return Object.fromEntries(Object.keys(parsed).map((key) => [key, true]))
  } catch {
    return {}
  }
}

function writeLeases(value: Record<string, true>) {
  try { window.sessionStorage.setItem(LEASE_KEY, JSON.stringify(value)) } catch { /* storage unavailable */ }
}

function readBaseline(): SharePrivacyMode | null {
  try {
    const value = window.sessionStorage.getItem(BASELINE_KEY)
    return value === 'PRIVATE_OVERLAY' ? 'PRIVATE_OVERLAY' : value === 'OFF' ? 'OFF' : null
  } catch {
    return null
  }
}

function writeBaseline(value: SharePrivacyMode | null) {
  try {
    if (value) window.sessionStorage.setItem(BASELINE_KEY, value)
    else window.sessionStorage.removeItem(BASELINE_KEY)
  } catch { /* storage unavailable */ }
}

function bridge() {
  const api = window.electronAPI
  if (!api?.getSharePrivacy || !api?.setSharePrivacy) {
    throw new Error('PRIVATE_OVERLAY 只在桌面版可用；当前运行环境没有 Electron Share Privacy bridge。')
  }
  return api
}

export async function inspectConversationSharePrivacy(requested: SharePrivacyMode): Promise<ConversationSharePrivacyRuntime> {
  if (requested === 'OFF') {
    return {
      requested,
      available: true,
      protected: false,
      active_mode: 'OFF',
      note: '本场未请求 Share Privacy。',
      proof: '',
    }
  }
  const api = bridge()
  const state = await api.getSharePrivacy!()
  return {
    requested,
    available: true,
    protected: Boolean(state.protected),
    active_mode: String(state.mode || 'OFF'),
    note: String(state.note || ''),
    proof: state.protected && state.mode === 'PRIVATE_OVERLAY' ? SHARE_PRIVACY_PROOF : '',
  }
}

export async function activateConversationSharePrivacy(
  sessionId: string,
  requested: SharePrivacyMode,
): Promise<ConversationSharePrivacyRuntime> {
  if (requested === 'OFF') return inspectConversationSharePrivacy('OFF')

  const api = bridge()
  const before = await api.getSharePrivacy!()
  const leases = readLeases()
  if (!Object.keys(leases).length && !readBaseline()) {
    writeBaseline(before.mode === 'PRIVATE_OVERLAY' ? 'PRIVATE_OVERLAY' : 'OFF')
  }
  leases[sessionId] = true
  writeLeases(leases)

  try {
    await api.setSharePrivacy!('PRIVATE_OVERLAY')
    const after = await api.getSharePrivacy!()
    if (after.mode !== 'PRIVATE_OVERLAY' || !after.protected) {
      throw new Error('Electron 未确认 content protection 已启用。')
    }
    return {
      requested,
      available: true,
      protected: true,
      active_mode: after.mode,
      note: String(after.note || ''),
      proof: SHARE_PRIVACY_PROOF,
    }
  } catch (error) {
    delete leases[sessionId]
    writeLeases(leases)
    if (!Object.keys(leases).length) {
      const baseline = readBaseline()
      if (baseline) {
        try { await api.setSharePrivacy!(baseline) } catch { /* fail safer: protection may remain */ }
      }
      writeBaseline(null)
    }
    throw error
  }
}

export async function restoreConversationSharePrivacy(sessionId: string): Promise<ConversationSharePrivacyRuntime> {
  const api = window.electronAPI
  const leases = readLeases()
  delete leases[sessionId]
  writeLeases(leases)

  if (!api?.getSharePrivacy || !api?.setSharePrivacy) {
    if (!Object.keys(leases).length) writeBaseline(null)
    return {
      requested: 'OFF',
      available: false,
      protected: false,
      active_mode: 'UNKNOWN',
      note: 'Electron Share Privacy bridge unavailable.',
      proof: '',
    }
  }

  if (Object.keys(leases).length) {
    await api.setSharePrivacy('PRIVATE_OVERLAY')
    const state = await api.getSharePrivacy()
    return {
      requested: 'PRIVATE_OVERLAY',
      available: true,
      protected: Boolean(state.protected),
      active_mode: String(state.mode || 'OFF'),
      note: String(state.note || ''),
      proof: state.protected && state.mode === 'PRIVATE_OVERLAY' ? SHARE_PRIVACY_PROOF : '',
    }
  }

  const baseline = readBaseline() ?? 'OFF'
  await api.setSharePrivacy(baseline)
  writeBaseline(null)
  const state = await api.getSharePrivacy()
  return {
    requested: baseline,
    available: true,
    protected: Boolean(state.protected),
    active_mode: String(state.mode || baseline),
    note: String(state.note || ''),
    proof: state.protected && state.mode === 'PRIVATE_OVERLAY' ? SHARE_PRIVACY_PROOF : '',
  }
}
