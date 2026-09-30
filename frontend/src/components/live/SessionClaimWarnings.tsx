import { useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { api, getErrorMessage } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'

// R2 Stage E：本场口述但 Interview Pack 暂无来源支持的陈述 → 私有提示 + 同场纠错入口。
// 选择只影响本场（口误 = SESSION_CORRECTED，之后不再使用）；长期事实只能在复盘确认。
export default function SessionClaimWarnings() {
  const warnings = useInterviewStore((s) => s.sessionClaimWarnings)
  const dismiss = useInterviewStore((s) => s.dismissSessionClaimWarning)
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [busy, setBusy] = useState<string | null>(null)

  if (!warnings.length) return null

  const act = async (id: string, action: string) => {
    setBusy(`${id}:${action}`)
    try {
      await api.intelResolveSessionClaim(id, action)
      dismiss(id)
    } catch (error) {
      pushToast(getErrorMessage(error, '操作失败'), 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="px-3 md:px-5 pt-2 space-y-2" aria-live="polite">
      {warnings.map((w) => (
        <div
          key={w.id}
          role="alert"
          data-testid="session-claim-warning"
          className="rounded-xl border border-status-risk/30 bg-status-risk/5 px-3 py-2"
        >
          <div className="flex items-start gap-2 text-xs text-text-primary">
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 text-status-risk flex-shrink-0" aria-hidden />
            <span className="leading-relaxed">{w.message}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5 pl-5">
            {w.actions.map((a) => (
              <button
                key={a.id}
                type="button"
                disabled={busy !== null}
                onClick={() => act(w.id, a.id)}
                className="rounded-full border border-bg-hover px-2.5 py-1 text-[11px] font-medium text-text-secondary hover:bg-bg-hover/60 disabled:opacity-50"
              >
                {busy === `${w.id}:${a.id}` ? '处理中…' : a.label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
