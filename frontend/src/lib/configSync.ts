import { api } from './api'
import { useInterviewStore, type AppConfig } from '@/stores/configStore'
import { hasActiveConversationSharePrivacyLeases, updateConversationSharePrivacyBaseline } from './conversationSharePrivacy'

export async function refreshConfig(): Promise<AppConfig> {
  const nextConfig = await api.getConfig()
  useInterviewStore.getState().setConfig(nextConfig)
  return nextConfig
}

export async function updateConfigAndRefresh(data: Record<string, unknown>): Promise<AppConfig> {
  const requestedSharePrivacy = data.share_privacy_mode
  const electron = window.electronAPI
  const shareMode = requestedSharePrivacy === 'PRIVATE_OVERLAY' || requestedSharePrivacy === 'OFF'
    ? requestedSharePrivacy
    : null
  const sessionOverrideActive = shareMode ? hasActiveConversationSharePrivacyLeases() : false
  let previousSharePrivacy: 'OFF' | 'PRIVATE_OVERLAY' | null = null

  if (shareMode && electron?.getSharePrivacy && electron?.setSharePrivacy) {
    const previous = await electron.getSharePrivacy()
    previousSharePrivacy = previous.mode === 'PRIVATE_OVERLAY' ? 'PRIVATE_OVERLAY' : 'OFF'

    // A Conversation PRIVATE_OVERLAY lease is stronger than the persisted
    // global default for the duration of that session. Changing Settings while
    // the session is active updates what should happen *after* the session,
    // but must not silently drop protection mid-session.
    const runtimeTarget: 'OFF' | 'PRIVATE_OVERLAY' = sessionOverrideActive ? 'PRIVATE_OVERLAY' : shareMode
    await electron.setSharePrivacy(runtimeTarget)
    const verified = await electron.getSharePrivacy()
    const shouldProtect = runtimeTarget === 'PRIVATE_OVERLAY'
    if (verified.mode !== runtimeTarget || Boolean(verified.protected) !== shouldProtect) {
      try { await electron.setSharePrivacy(previousSharePrivacy) } catch { /* fail safer: current protection may remain */ }
      throw new Error('共享隐私设置未被桌面窗口确认；配置未保存。')
    }
  }

  try {
    await api.updateConfig(data)
    if (shareMode && sessionOverrideActive) updateConversationSharePrivacyBaseline(shareMode)
  } catch (error) {
    if (previousSharePrivacy && electron?.setSharePrivacy) {
      try { await electron.setSharePrivacy(previousSharePrivacy) } catch { /* fail safer: current protection may remain */ }
    }
    throw error
  }
  return refreshConfig()
}
