import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  SHARE_PRIVACY_PROOF,
  activateConversationSharePrivacy,
  inspectConversationSharePrivacy,
  restoreConversationSharePrivacy,
  updateConversationSharePrivacyBaseline,
} from './conversationSharePrivacy'

type RuntimeState = { mode: 'OFF' | 'PRIVATE_OVERLAY'; protected: boolean; note: string }

function installBridge(initial: RuntimeState['mode'] = 'OFF') {
  let mode: RuntimeState['mode'] = initial
  const calls: string[] = []
  const api = {
    getSharePrivacy: async () => ({
      mode,
      protected: mode === 'PRIVATE_OVERLAY',
      note: 'best effort only',
    }),
    setSharePrivacy: async (next: string) => {
      mode = next === 'PRIVATE_OVERLAY' ? 'PRIVATE_OVERLAY' : 'OFF'
      calls.push(mode)
      return mode
    },
  }
  Object.defineProperty(window, 'electronAPI', { value: api, configurable: true, writable: true })
  return { calls, get mode() { return mode } }
}

describe('Conversation Share Privacy session lease', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
    Object.defineProperty(window, 'electronAPI', { value: undefined, configurable: true, writable: true })
  })

  afterEach(() => {
    window.sessionStorage.clear()
    Object.defineProperty(window, 'electronAPI', { value: undefined, configurable: true, writable: true })
  })

  it('fails closed when PRIVATE_OVERLAY is requested without Electron bridge', async () => {
    await expect(activateConversationSharePrivacy('s1', 'PRIVATE_OVERLAY'))
      .rejects.toThrow(/桌面版/)
  })

  it('activates and verifies Electron content protection for a private session', async () => {
    const runtime = installBridge('OFF')
    const active = await activateConversationSharePrivacy('s1', 'PRIVATE_OVERLAY')

    expect(active.protected).toBe(true)
    expect(active.proof).toBe(SHARE_PRIVACY_PROOF)
    expect(runtime.mode).toBe('PRIVATE_OVERLAY')
    expect(runtime.calls).toEqual(['PRIVATE_OVERLAY'])
  })

  it('keeps protection until the final private session releases its lease', async () => {
    const runtime = installBridge('OFF')
    await activateConversationSharePrivacy('s1', 'PRIVATE_OVERLAY')
    await activateConversationSharePrivacy('s2', 'PRIVATE_OVERLAY')

    await restoreConversationSharePrivacy('s1')
    expect(runtime.mode).toBe('PRIVATE_OVERLAY')

    await restoreConversationSharePrivacy('s2')
    expect(runtime.mode).toBe('OFF')
  })

  it('restores a pre-existing global PRIVATE_OVERLAY baseline instead of forcing OFF', async () => {
    const runtime = installBridge('PRIVATE_OVERLAY')
    await activateConversationSharePrivacy('s1', 'PRIVATE_OVERLAY')
    await restoreConversationSharePrivacy('s1')
    expect(runtime.mode).toBe('PRIVATE_OVERLAY')
  })

  it('lets Settings change the post-session baseline without dropping active protection', async () => {
    const runtime = installBridge('PRIVATE_OVERLAY')
    await activateConversationSharePrivacy('s1', 'PRIVATE_OVERLAY')

    // The user changes the global default to OFF while this Session still
    // requires PRIVATE_OVERLAY. Runtime remains protected until release.
    updateConversationSharePrivacyBaseline('OFF')
    expect(runtime.mode).toBe('PRIVATE_OVERLAY')

    await restoreConversationSharePrivacy('s1')
    expect(runtime.mode).toBe('OFF')
  })

  it('reports OFF without requiring Electron bridge', async () => {
    const state = await inspectConversationSharePrivacy('OFF')
    expect(state.available).toBe(true)
    expect(state.protected).toBe(false)
    expect(state.proof).toBe('')
  })
})
