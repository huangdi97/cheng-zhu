import { useCallback, useEffect, useState } from 'react'
import { Lock, LockOpen, ShieldCheck, Users, EyeOff } from 'lucide-react'
import { api, type PackSummary } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'

const AI_LABEL: Record<string, string> = {
  AI_FORBIDDEN: 'AI 辅助：关闭',
  AI_ALLOWED: 'AI 辅助：允许',
  AI_KNOWLEDGE_ONLY: 'AI 辅助：仅知识',
}
const HUMAN_LABEL: Record<string, string> = {
  HUMAN_FORBIDDEN: '人工协助：禁止',
  HUMAN_PRACTICE_ONLY: '人工协助：仅练习',
  HUMAN_ALLOWED: '人工协助：允许',
}
const SHARE_LABEL: Record<string, string> = {
  OFF: '共享隐私：关',
  PRIVATE_OVERLAY: '共享隐私：私有悬浮窗',
}

// R2 Stage F/S：上场顶部的 Interview Pack 状态。正式场次必须先冻结；
// 未冻结时只使用当前简历，不带任何岗位（绝不读取“最近分析的岗位”）。
export default function LivePackBar() {
  const activeSessionId = useInterviewStore((s) => s.activeSessionId)
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)
  const [pack, setPack] = useState<PackSummary | null>(null)
  const [loaded, setLoaded] = useState(false)

  const refresh = useCallback(() => {
    // Promise.resolve().then keeps a missing/older backend route (or a
    // partial test double) from throwing synchronously during render.
    Promise.resolve()
      .then(() => api.intelPack(activeSessionId || undefined))
      .then((res) => setPack(res?.pack ?? null))
      .catch(() => setPack(null))
      .finally(() => setLoaded(true))
  }, [activeSessionId])

  useEffect(() => { refresh() }, [refresh])

  // The frozen pack's per-session Share Privacy overrides the default; an
  // unfrozen session uses the settings default (OFF unless changed).
  const defaultSharePrivacy = useInterviewStore((s) => s.config?.share_privacy_mode ?? 'OFF')
  useEffect(() => {
    if (!loaded) return
    const mode = pack?.policies.share_privacy_policy ?? defaultSharePrivacy
    void window.electronAPI?.setSharePrivacy?.(mode)
  }, [loaded, pack?.policies.share_privacy_policy, defaultSharePrivacy])

  if (!loaded) return null

  if (!pack) {
    return (
      <div data-testid="live-pack-bar" className="flex flex-wrap items-center gap-2 px-3 md:px-5 py-2 border-b border-bg-tertiary/70 bg-status-inferred/5 text-xs">
        <LockOpen className="w-3.5 h-3.5 text-status-inferred" aria-hidden />
        <span className="font-medium text-status-inferred">本场资料还没冻结</span>
        <span className="text-text-muted">练习可以直接开始；正式面试请先回到求职目标确认这一场要带进去的资料。</span>
        <button type="button" onClick={() => setAppMode('job-tracker')} className="ml-auto rounded-full border border-bg-hover px-2.5 py-0.5 font-medium text-text-secondary hover:bg-bg-hover/60">
          去冻结
        </button>
      </div>
    )
  }

  return (
    <div data-testid="live-pack-bar" className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 md:px-5 py-2 border-b border-bg-tertiary/70 bg-bg-secondary/40 text-[11px] text-text-secondary">
      <span className="inline-flex items-center gap-1 font-medium text-status-direct">
        <Lock className="w-3.5 h-3.5" aria-hidden />
        本场资料已冻结
      </span>
      <span className="text-text-primary font-medium">{pack.job.title || '未选择岗位'}{pack.job.company ? ` · ${pack.job.company}` : ''}</span>
      <span className="inline-flex items-center gap-1"><ShieldCheck className="w-3 h-3" aria-hidden />{AI_LABEL[pack.policies.ai_policy] ?? pack.policies.ai_policy}</span>
      <span className="inline-flex items-center gap-1"><Users className="w-3 h-3" aria-hidden />{HUMAN_LABEL[pack.policies.human_assistance_policy] ?? pack.policies.human_assistance_policy}</span>
      <span className="inline-flex items-center gap-1"><EyeOff className="w-3 h-3" aria-hidden />{SHARE_LABEL[pack.policies.share_privacy_policy] ?? pack.policies.share_privacy_policy}</span>
    </div>
  )
}
