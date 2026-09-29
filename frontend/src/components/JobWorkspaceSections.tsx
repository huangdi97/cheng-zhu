import { useState } from 'react'
import { BookOpen, ChevronDown, ChevronRight, Crosshair, GitBranch, Map as MapIcon } from 'lucide-react'

export interface GapItem {
  topic: string
  status: string
  source: string
  priority: string
  reason: string
}

export interface AttackSurfaceItem {
  claim_id: string
  text: string
  truth_status?: string
  job_aligned?: boolean
  risks?: string[]
  probes?: string[]
}

export interface QuestionNode {
  id: string
  text: string
  kind: string
  source?: string
  parent_id: string
}

export interface StoryPrompt {
  competency: string
  hint: string
  candidate_sources?: string[]
}

export interface StoryItem {
  id: string
  title: string
  tags?: string[]
  truth_status?: string
}

export interface WorkspacePayload {
  gap_map?: GapItem[]
  attack_surface?: AttackSurfaceItem[]
  question_graph?: QuestionNode[]
  stories?: { items?: StoryItem[]; prompts?: StoryPrompt[] }
}

const PRIORITY_LABEL: Record<string, { text: string; tone: string }> = {
  high: { text: '优先', tone: 'bg-accent-red/10 text-accent-red' },
  medium: { text: '准备', tone: 'bg-accent-amber/10 text-accent-amber' },
  low: { text: '补充', tone: 'bg-bg-tertiary text-text-muted' },
}

const NODE_KIND_LABEL: Record<string, string> = {
  PROJECT_DEEP_DIVE: '深挖',
  FOLLOW_UP: '追问',
  KNOWLEDGE: '知识',
  EXPERIENCE_BOUNDARY: '事实边界',
  OPEN_DESIGN: '开放设计',
}

function SectionTitle({ icon: Icon, children }: { icon: typeof MapIcon; children: string }) {
  return (
    <div className="flex items-center gap-1.5 text-xs font-semibold text-text-primary">
      <Icon className="h-3.5 w-3.5 text-accent-blue" aria-hidden />
      {children}
    </div>
  )
}

export function GapMapSection({ gaps }: { gaps: GapItem[] }) {
  if (gaps.length === 0) return null
  return (
    <section className="space-y-1.5" aria-label="Gap Map">
      <SectionTitle icon={MapIcon}>Gap Map · 需要准备的缺口</SectionTitle>
      <ul className="space-y-1">
        {gaps.map((gap) => {
          const label = PRIORITY_LABEL[gap.priority] ?? PRIORITY_LABEL.low
          return (
            <li key={`${gap.source}-${gap.topic}`} className="flex items-start gap-1.5 text-xs leading-relaxed">
              <span className={`flex-shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium ${label.tone}`}>{label.text}</span>
              <span className="min-w-0 break-words text-text-secondary">
                <span className="font-medium text-text-primary">{gap.topic}</span>
                <span className="text-text-muted"> — {gap.reason}</span>
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

export function AttackSurfaceSection({ items }: { items: AttackSurfaceItem[] }) {
  if (items.length === 0) return null
  return (
    <section className="space-y-1.5" aria-label="Attack Surface">
      <SectionTitle icon={Crosshair}>简历攻击面 · 最可能被深挖的经历</SectionTitle>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.claim_id} className="rounded-lg bg-bg-tertiary/40 px-2.5 py-2 text-xs leading-relaxed">
            <p className="break-words text-text-primary">{item.text}</p>
            {item.risks && item.risks.length > 0 && (
              <p className="mt-0.5 text-[11px] text-accent-amber">{item.risks.join(' · ')}</p>
            )}
            {item.probes && item.probes.length > 0 && (
              <p className="mt-0.5 text-[11px] text-text-muted break-words">可能追问：{item.probes.join(' / ')}</p>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}

function QuestionBranch({ node, childrenOf, depth }: { node: QuestionNode; childrenOf: Map<string, QuestionNode[]>; depth: number }) {
  const kids = childrenOf.get(node.id) ?? []
  return (
    <li className="space-y-1">
      <div className="flex items-start gap-1.5 text-xs leading-relaxed">
        <span className="flex-shrink-0 rounded-md bg-accent-blue/10 px-1.5 py-0.5 text-[10px] text-accent-blue">
          {NODE_KIND_LABEL[node.kind] ?? node.kind}
        </span>
        <span className="min-w-0 break-words text-text-secondary">{node.text}</span>
      </div>
      {kids.length > 0 && depth < 4 && (
        <ul className="ml-3 space-y-1 border-l border-bg-tertiary pl-2">
          {kids.map((kid) => (
            <QuestionBranch key={kid.id} node={kid} childrenOf={childrenOf} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  )
}

export function QuestionGraphSection({ nodes }: { nodes: QuestionNode[] }) {
  const [open, setOpen] = useState(false)
  if (nodes.length === 0) return null
  const childrenOf = new Map<string, QuestionNode[]>()
  for (const node of nodes) {
    if (!node.parent_id) continue
    childrenOf.set(node.parent_id, [...(childrenOf.get(node.parent_id) ?? []), node])
  }
  const roots = nodes.filter((node) => !node.parent_id)
  const Chevron = open ? ChevronDown : ChevronRight
  return (
    <section className="space-y-1.5" aria-label="Question Graph">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex items-center gap-1 rounded-md text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent-blue"
      >
        <Chevron className="h-3.5 w-3.5 text-text-muted" aria-hidden />
        <SectionTitle icon={GitBranch}>{`Question Graph · 追问树（${roots.length} 条主线）`}</SectionTitle>
      </button>
      {open && (
        <ul className="space-y-2">
          {roots.map((root) => (
            <QuestionBranch key={root.id} node={root} childrenOf={childrenOf} depth={0} />
          ))}
        </ul>
      )}
    </section>
  )
}

export function StoriesSection({ items, prompts }: { items: StoryItem[]; prompts: StoryPrompt[] }) {
  if (items.length === 0 && prompts.length === 0) return null
  return (
    <section className="space-y-1.5" aria-label="Stories">
      <SectionTitle icon={BookOpen}>Stories · 行为题故事</SectionTitle>
      {items.length > 0 && (
        <ul className="space-y-1">
          {items.map((story) => (
            <li key={story.id} className="text-xs text-text-secondary break-words">
              {story.title}
              {story.tags && story.tags.length > 0 && <span className="text-text-muted">（{story.tags.join('、')}）</span>}
            </li>
          ))}
        </ul>
      )}
      {prompts.length > 0 && (
        <ul className="space-y-1">
          {prompts.map((prompt) => (
            <li key={prompt.competency} className="text-[11px] leading-relaxed text-text-muted break-words">
              <span className="font-medium text-text-secondary">缺少「{prompt.competency}」故事：</span>
              {prompt.hint}
              {prompt.candidate_sources && prompt.candidate_sources.length > 0 && (
                <span>。可以从这些经历里找：{prompt.candidate_sources.join('；')}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
