import { api } from './api'
import { useInterviewStore, type AppConfig } from '@/stores/configStore'

export async function refreshConfig(): Promise<AppConfig> {
  const nextConfig = await api.getConfig()
  useInterviewStore.getState().setConfig(nextConfig)
  return nextConfig
}

export async function updateConfigAndRefresh(data: Record<string, unknown>): Promise<AppConfig> {
  const requestedSharePrivacy = data.share_privacy_mode
  const electron = window.electronAPI
  let previousSharePrivacy: 'OFF' | 'PRIVATE_OVERLAY' | null = null

  if (
    (requestedSharePrivacy === 'OFF' || requestedSharePrivacy === 'PRIVATE_OVERLAY')
    && electron?.getSharePrivacy
    && electron?.setSharePrivacy
  ) {
    const previous = await electron.getSharePrivacy()
    previousSharePrivacy = previous.mode === 'PRIVATE_OVERLAY' ? 'PRIVATE_OVERLAY' : 'OFF'
    await electron.setSharePrivacy(requestedSharePrivacy)
    const verified = await electron.getSharePrivacy()
    const shouldProtect = requestedSharePrivacy === 'PRIVATE_OVERLAY'
    if (verified.mode !== requestedSharePrivacy || Boolean(verified.protected) !== shouldProtect) {
      try { await electron.setSharePrivacy(previousSharePrivacy) } catch { /* fail safer: current protection may remain */ }
      throw new Error('共享隐私设置未被桌面窗口确认；配置未保存。')
    }
  }

  try {
    await api.updateConfig(data)
  } catch (error) {
    if (previousSharePrivacy && electron?.setSharePrivacy) {
      try { await electron.setSharePrivacy(previousSharePrivacy) } catch { /* fail safer: current protection may remain */ }
    }
    throw error
  }
  return refreshConfig()
}
