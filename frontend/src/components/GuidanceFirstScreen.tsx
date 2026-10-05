import { useState } from 'react'
import { track } from '@/lib/productApi'
import { AlertTriangle, BookOpen, Globe, UserCheck, Users } from 'lucide-react'
import { CUE_SOURCE_LABELS, type CueSource, type FastCueViewModel } from '@/lib/guidanceViewModel'

// R2 Live Main 首屏：当前问题下的 Fast Cue（先于 Deep Answer 到达）。
// 每条 cue 都显示来源（图标 + 文字，不只靠颜色）；风险单独一栏。
// Deep Answer 由调用方在下方渲染，本组件不再解析 answer 文本。

const SOURCE_ICON: Record<CueSource, typeof BookOpen> = {
  PERSONAL_EVIDENCE: UserCheck,
  KB_KNOWLEDGE: BookOpen,
  WORLD_KNOWLEDGE: Globe,
  HUMAN_COACH: Users,
}

// 语义状态色（WCAG AA，见 index.css 的 --status-* token）。
const SOURCE_TONE: Record<CueSource, string> = {
  PERSONAL_EVIDENCE: 'text-status-direct',
  KB_KNOWLEDGE: 'text-status-supported',
  WORLD_KNOWLEDGE: 'text-status-unknown',
  HUMAN_COACH: 'text-status-inferred',
}

export function CueSourceBadge({ source }: { source: CueSource }) {
  const Icon = SOURCE_ICON[source]
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-medium ${SOURCE_TONE[source]}`}>
      <Icon className="w-3 h-3" aria-hidden />
      {CUE_SOURCE_LABELS[source]}
    </span>
  )
}

interface FastCuePanelProps {
  cue: FastCueViewModel
  /** v1.4: when set, shows the one-tap helpful / not-needed signals (local only). */
  qaId?: string
}

function CueFeedback({ qaId }: { qaId: string }) {
  const [sent, setSent] = useState<string | null>(null)
  if (sent) return <p className="text-[10px] text-text-muted" role="status">{sent}</p>
  const send = (name: 'fast_cue_helpful' | 'fast_cue_dismissed', label: string) => {
    track(name, { qa: qaId.slice(0, 32) })
    setSent(label)
  }
  return (
    <div className="flex gap-2 text-[10px]" aria-label="这条 Cue 有帮助吗">
      <button type="button" className="text-text-muted hover:text-status-direct" onClick={() => send('fast_cue_helpful', '已记录：有帮助')}>有帮助</button>
      <button type="button" className="text-text-muted hover:text-status-risk" onClick={() => send('fast_cue_dismissed', '已记录：不需要')}>不需要</button>
    </div>
  )
}

export default function GuidanceFirstScreen({ cue, qaId }: FastCuePanelProps) {
  return (
    <section aria-label="Fast Cue" data-testid="fast-cue" className="rounded-xl border border-accent-blue/20 bg-accent-blue/5 p-3 mb-2 space-y-2">
      {cue.direction && (
        <p className="text-[11px] font-semibold text-text-secondary">{cue.direction}</p>
      )}
      {cue.cues.length > 0 && (
        <ul className="space-y-1.5">
          {cue.cues.map((item, idx) => (
            <li key={idx} className="flex items-start gap-2 text-[13px] text-text-primary leading-relaxed">
              <span className="mt-[8px] h-1.5 w-1.5 flex-shrink-0 rounded-full bg-accent-blue" aria-hidden />
              <span className="min-w-0 flex-1 break-words">{item.text}</span>
              <CueSourceBadge source={item.source} />
            </li>
          ))}
        </ul>
      )}
      {cue.jobFocus && <p className="text-[11px] text-text-muted">岗位关注：{cue.jobFocus}</p>}
      {cue.cautions.length > 0 && (
        <ul className="space-y-1" aria-label="风险">
          {cue.cautions.map((item, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-[11px] font-medium text-status-risk">
              <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" aria-hidden />
              <span className="break-words">{item}</span>
            </li>
          ))}
        </ul>
      )}
      {(cue.ttfugUserMs != null || cue.ttfugInternalMs != null) && (
        <p className="text-[10px] font-mono text-text-muted tabular-nums">
          {cue.ttfugUserMs != null ? `提示 ${cue.ttfugUserMs}ms（自说完）` : `提示 ${cue.ttfugInternalMs}ms（自问题确定）`}
        </p>
      )}
      {qaId ? <CueFeedback qaId={qaId} /> : null}
    </section>
  )
}
