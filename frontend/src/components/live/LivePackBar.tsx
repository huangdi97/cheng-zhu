import { useCallback, useEffect, useState } from 'react'
import { Lock, LockOpen, ShieldCheck, Users, EyeOff } from 'lucide-react'
import { api, type PackSummary } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'

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

  if (!loaded) return null

  if (!pack) {
    return (
      <div data-testid="live-pack-bar" className="flex flex-wrap items-center gap-2 px-3 md:px-5 py-2 border-b border-bg-tertiary/70 bg-status-inferred/5 text-xs">
        <LockOpen className="w-3.5 h-3.5 text-status-inferred" aria-hidden />
        <span className="font-medium text-status-inferred">Interview Pack 未冻结</span>
        <span className="text-text-muted">练习可直接开始；正式场次请先在岗位目标里冻结本场资料。</span>
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
        Pack rev {pack.revision}
      </span>
      <span className="text-text-primary font-medium">{pack.job.title || '未选择岗位'}{pack.job.company ? ` @ ${pack.job.company}` : ''}</span>
      <span className="inline-flex items-center gap-1"><ShieldCheck className="w-3 h-3" aria-hidden />{pack.policies.ai_policy}</span>
      <span className="inline-flex items-center gap-1"><Users className="w-3 h-3" aria-hidden />{HUMAN_LABEL[pack.policies.human_assistance_policy] ?? pack.policies.human_assistance_policy}</span>
      <span className="inline-flex items-center gap-1"><EyeOff className="w-3 h-3" aria-hidden />{SHARE_LABEL[pack.policies.share_privacy_policy] ?? pack.policies.share_privacy_policy}</span>
      <span className="font-mono text-text-muted">{pack.content_hash}</span>
    </div>
  )
}
