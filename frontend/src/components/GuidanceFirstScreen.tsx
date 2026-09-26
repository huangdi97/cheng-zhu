import { lazy, Suspense, useState } from 'react'
import { ChevronDown, Lightbulb, Loader2, Quote, Search } from 'lucide-react'
import type { ColorSchemeId } from '@/lib/colorScheme'
import type { GuidanceViewModel } from '@/lib/guidanceViewModel'

const AnswerMarkdownContent = lazy(() => import('./AnswerMarkdownContent'))

interface GuidanceFirstScreenProps {
  vm: GuidanceViewModel
  answer: string
  colorScheme: ColorSchemeId
  isStreaming?: boolean
}

function SectionTitle({ icon: Icon, label, tone }: { icon: typeof Quote; label: string; tone: string }) {
  return (
    <div className={`flex items-center gap-1.5 text-[10px] font-semibold mb-1.5 ${tone}`}>
      <Icon className="w-3 h-3" />
      {label}
    </div>
  )
}

function BulletList({ items, dotTone }: { items: string[]; dotTone: string }) {
  return (
    <ul className="space-y-1">
      {items.map((item, idx) => (
        <li key={idx} className="flex items-start gap-1.5 text-xs text-text-secondary leading-relaxed">
          <span className={`mt-[7px] h-1 w-1 flex-shrink-0 rounded-full ${dotTone}`} aria-hidden />
          <span className="min-w-0 break-words">{item}</span>
        </li>
      ))}
    </ul>
  )
}

// glance-first 首屏：答案就绪后先展示「当前问题 + 核心思路 + 我的证据」，
// 完整答案默认折叠，由 [展开] 按钮按需渲染，避免长答案淹没首屏。
export default function GuidanceFirstScreen({ vm, answer, colorScheme, isStreaming = false }: GuidanceFirstScreenProps) {
  const [expanded, setExpanded] = useState(false)
  const hasFullAnswer = answer.trim().length > 0
  const showResolved = vm.resolvedQuestion.length > 0 && vm.resolvedQuestion !== vm.question

  return (
    <div className="rounded-xl border border-accent-blue/20 bg-accent-blue/5 p-3 space-y-3">
      <div className="min-w-0">
        <SectionTitle icon={Quote} label="当前问题" tone="text-accent-blue" />
        <p className="text-sm text-text-primary leading-relaxed font-medium break-words">{vm.question}</p>
        {showResolved && (
          <p className="mt-1 text-[11px] text-text-muted leading-relaxed break-words">审题：{vm.resolvedQuestion}</p>
        )}
      </div>

      {vm.coreIdeas.length > 0 && (
        <div className="min-w-0">
          <SectionTitle icon={Lightbulb} label="核心思路" tone="text-accent-amber" />
          <BulletList items={vm.coreIdeas} dotTone="bg-accent-amber" />
        </div>
      )}

      {vm.evidence.length > 0 && (
        <div className="min-w-0">
          <SectionTitle icon={Search} label="我的证据" tone="text-accent-green" />
          <BulletList items={vm.evidence} dotTone="bg-accent-green" />
        </div>
      )}

      {(hasFullAnswer || isStreaming) && (
        <div className="border-t border-accent-blue/15 pt-2.5">
          {expanded && hasFullAnswer && (
            <div className="mb-1.5 max-h-[280px] overflow-y-auto rounded-lg bg-bg-tertiary/20 p-2.5">
              <Suspense fallback={<div className="text-xs text-text-muted">渲染答案中…</div>}>
                <AnswerMarkdownContent answer={answer} colorScheme={colorScheme} stream={false} />
              </Suspense>
            </div>
          )}
          {expanded && !hasFullAnswer && (
            <div className="flex items-center gap-2 text-text-muted text-xs py-1">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              生成中…
            </div>
          )}
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-1 text-[11px] font-medium text-accent-blue hover:underline"
          >
            {expanded ? '收起' : '展开'}
            <ChevronDown className={`w-3 h-3 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`} />
          </button>
        </div>
      )}
    </div>
  )
}
