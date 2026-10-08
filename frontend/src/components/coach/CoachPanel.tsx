import { useCallback, useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { api, getErrorMessage } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'

// R2 Stage U：人工教练（候选人端）。默认用于演练/练习；正式场次只有在本场
// 人工协助策略为「允许」时服务端才会创建。教练建议 ≠ 证据 ≠ 用户确认。

interface CoachSessionView {
  id: string
  session_kind: string
  target_session_id?: string
  permissions: Record<string, boolean>
  expires_at: number
  revoked: boolean
  active: boolean
  cue_count: number
  connected: boolean
}

const INTERVIEW_PERM_LABELS: Array<[string, string]> = [
  ['transcript', '转写'],
  ['ai_cue', 'AI Cue'],
  ['resume_jd', '简历 / 岗位'],
]

const CONVERSATION_PERM_LABELS: Array<[string, string]> = [
  ['transcript', '本场转写'],
  ['ai_cue', '当前 AI Guidance'],
  ['session_context', '冻结 Session Context'],
]

export default function CoachPanel({
  sessionKind = 'practice',
  targetSessionId = '',
}: {
  sessionKind?: 'practice' | 'live' | 'conversation'
  targetSessionId?: string
}) {
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [perms, setPerms] = useState<Record<string, boolean>>(
    sessionKind === 'conversation'
      ? { transcript: false, ai_cue: false, session_context: true }
      : { transcript: true, ai_cue: false, resume_jd: false },
  )
  const [lan, setLan] = useState(sessionKind !== 'conversation')
  const [sessions, setSessions] = useState<CoachSessionView[]>([])
  const [links, setLinks] = useState<Record<string, string> | null>(null)
  const [relay, setRelay] = useState('BLOCKED-EXTERNAL')
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    Promise.resolve()
      .then(() => api.coachSessions())
      .then((r) => {
        const all = (r?.sessions ?? []) as unknown as CoachSessionView[]
        setSessions(all.filter((s) => (
          s.session_kind === sessionKind
          && (sessionKind !== 'conversation' || s.target_session_id === targetSessionId)
        )))
        setRelay(r?.public_relay ?? 'BLOCKED-EXTERNAL')
      })
      .catch(() => setSessions([]))
  }, [sessionKind, targetSessionId])
  useEffect(() => { load() }, [load])

  const create = async () => {
    setError(null)
    try {
      const r = await api.coachCreate({
        session_kind: sessionKind,
        target_session_id: sessionKind === 'conversation' ? targetSessionId : undefined,
        permissions: perms,
        lan,
      })
      setLinks(r.urls)
      load()
    } catch (e) {
      setError(getErrorMessage(e, '创建失败'))
    }
  }

  const copy = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url)
      pushToast('链接已复制；只发给你信任的教练', 'success')
    } catch {
      pushToast('复制失败', 'error')
    }
  }

  return (
    <section className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-4 space-y-3" data-testid="coach-panel">
      <div className="flex items-center gap-2">
        <Users className="h-4 w-4 text-accent-blue" aria-hidden />
        <h3 className="text-sm font-semibold text-text-primary">人工教练{sessionKind === 'practice' ? '（练习）' : sessionKind === 'conversation' ? '（Conversation）' : '（正式面试）'}</h3>
      </div>
      <p className="text-[11px] text-text-muted">教练通过一次性链接看到你逐项授权的内容，并给你发文字或语音建议。建议始终标注为 HUMAN_COACH，不会成为事实或证据；教练无法控制你的电脑。{sessionKind === 'conversation' ? ' 链接只绑定当前 Conversation Session，结束后自动撤销。' : ''}</p>
      <fieldset className="flex flex-wrap gap-3 text-xs text-text-secondary">
        <legend className="sr-only">授权内容</legend>
        {(sessionKind === 'conversation' ? CONVERSATION_PERM_LABELS : INTERVIEW_PERM_LABELS).map(([key, label]) => (
          <label key={key} className="inline-flex items-center gap-1">
            <input type="checkbox" checked={Boolean(perms[key])} onChange={(e) => setPerms({ ...perms, [key]: e.target.checked })} />
            {label}
          </label>
        ))}
        <label className="inline-flex items-center gap-1">
          <input type="checkbox" checked={lan} onChange={(e) => setLan(e.target.checked)} />
          局域网链接
        </label>
      </fieldset>
      <button type="button" onClick={() => void create()} disabled={sessionKind === 'conversation' && !targetSessionId} className="rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-50">生成教练链接</button>
      {error && <p role="alert" className="text-xs text-status-risk">{error}</p>}
      {links && (
        <div className="space-y-1 text-xs">
          <p className="text-text-muted">链接只显示这一次（含一次性令牌）：</p>
          {Object.entries(links).filter(([, url]) => url).map(([kind, url]) => (
            <div key={kind} className="flex items-center gap-2">
              <span className="w-12 text-text-muted">{kind === 'lan' ? '局域网' : kind === 'local' ? '本机' : '公网'}</span>
              <code className="flex-1 truncate rounded bg-bg-tertiary/40 px-1.5 py-0.5">{url.split('#')[0]}#…</code>
              <button type="button" onClick={() => void copy(url)} className="rounded border border-bg-hover px-2 py-0.5 text-text-secondary">复制</button>
            </div>
          ))}
          <p className="text-text-muted">公网中转：{relay === 'BLOCKED-EXTERNAL' ? '未配置（需要自建中转服务）' : '已配置'}</p>
        </div>
      )}
      {sessions.length > 0 && (
        <ul className="space-y-1 text-xs">
          {sessions.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-2 rounded-lg bg-bg-tertiary/25 px-2 py-1">
              <span className="text-text-secondary">
                {s.active ? (s.connected ? '已连接' : '等待连接') : s.revoked ? '已撤销' : '已过期'} · 建议 {s.cue_count} 条 · 至 {new Date(s.expires_at * 1000).toLocaleTimeString()}
              </span>
              {s.active && (
                <button type="button" onClick={() => api.coachRevoke(s.id).then(load)} className="rounded border border-status-risk/40 px-2 py-0.5 text-status-risk">断开并撤销</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
