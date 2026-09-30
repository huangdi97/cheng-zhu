import { useCallback, useState } from 'react'
import { Briefcase, CheckCircle2, CircleAlert, Loader2, Target } from 'lucide-react'
import { buildApiUrl } from '@/lib/backendUrl'
import { getAuthToken } from '@/lib/auth'
import { getErrorMessage } from '@/lib/api'
import {
  AttackSurfaceSection,
  GapMapSection,
  QuestionGraphSection,
  StoriesSection,
  type AttackSurfaceItem,
  type GapItem,
  type QuestionNode,
  type StoryItem,
  type StoryPrompt,
  type WorkspacePayload,
} from './JobWorkspaceSections'

interface JobWorkspacePanelProps {
  jdText: string
  resumeText: string
}

interface JobAlignmentItem {
  requirement_text: string
  source?: string
  status?: string
  evidence_claim_ids?: string[]
  explanation?: string
}

interface JobPayload {
  company?: string
  title?: string
  level?: string
  technologies?: unknown
  must_have?: unknown
  nice_to_have?: unknown
  likely_interview_dimensions?: unknown
  alignment?: { requirements?: unknown } | Record<string, unknown>
  workspace?: WorkspacePayload
}

const ALIGNMENT_TONE: Record<string, string> = {
  STRONG_MATCH: 'text-accent-green',
  PARTIAL_MATCH: 'text-accent-amber',
  KNOWLEDGE_MATCH: 'text-accent-blue',
  GAP: 'text-accent-red',
  UNKNOWN: 'text-text-muted',
}

function asStringList(value: unknown, cap: number): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0).slice(0, cap)
}

function asAlignmentList(value: JobPayload['alignment']): JobAlignmentItem[] {
  const requirements = value && typeof value === 'object' && Array.isArray((value as { requirements?: unknown }).requirements)
    ? (value as { requirements: unknown[] }).requirements
    : []
  return requirements
    .filter((item): item is JobAlignmentItem => !!item && typeof item === 'object')
    .slice(0, 12)
}

function asArray<T>(value: unknown, cap: number): T[] {
  return Array.isArray(value) ? (value.filter((item) => !!item && typeof item === 'object') as T[]).slice(0, cap) : []
}

/**
 * Stage L1：Prepare 的 Job Workspace 区块。把 JD 与简历交给 Intelligence
 * Core 的确定性 Job Workspace（/api/intelligence/workspace），展示结构化岗位、
 * Candidate×Job Alignment（可解释状态，无虚假百分比）、Gap Map、简历攻击面、
 * 追问树与 Stories（只提示去哪找真实故事，从不编造经历）。
 */
export default function JobWorkspacePanel({ jdText, resumeText }: JobWorkspacePanelProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [job, setJob] = useState<JobPayload | null>(null)

  const analyze = useCallback(async () => {
    if (!jdText.trim()) {
      setError('请先填写 JD 后再分析岗位结构')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await fetch(buildApiUrl('/api/intelligence/workspace'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: getAuthToken() },
        body: JSON.stringify({ jd_text: jdText, resume_text: resumeText }),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(text || `请求失败 (${res.status})`)
      }
      const data: unknown = await res.json()
      setJob(data && typeof data === 'object' && !Array.isArray(data) ? (data as JobPayload) : null)
    } catch (e) {
      setError(getErrorMessage(e, '岗位结构分析失败'))
    } finally {
      setLoading(false)
    }
  }, [jdText, resumeText])

  const technologies = asStringList(job?.technologies, 12)
  const mustHave = asStringList(job?.must_have, 10)
  const niceToHave = asStringList(job?.nice_to_have, 8)
  const dimensions = asStringList(job?.likely_interview_dimensions, 10)
  const alignment = asAlignmentList(job?.alignment)
  const workspace = job?.workspace && typeof job.workspace === 'object' ? job.workspace : undefined
  const gaps = asArray<GapItem>(workspace?.gap_map, 12)
  const attackSurface = asArray<AttackSurfaceItem>(workspace?.attack_surface, 6)
  const questionNodes = asArray<QuestionNode>(workspace?.question_graph, 80)
  const storyItems = asArray<StoryItem>(workspace?.stories?.items, 12)
  const storyPrompts = asArray<StoryPrompt>(workspace?.stories?.prompts, 6)

  return (
    <div className="rounded-xl border border-bg-tertiary/80 bg-bg-secondary/40 p-3 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-sm font-semibold text-text-primary">
          <Briefcase className="h-4 w-4 text-accent-blue" aria-hidden />
          岗位工作台（Job Workspace）
        </div>
        <button
          type="button"
          onClick={analyze}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-xl bg-container-primary px-3 py-1.5 text-xs font-medium text-container-on-primary transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Target className="h-3.5 w-3.5" aria-hidden />}
          {loading ? '分析中…' : '分析岗位'}
        </button>
      </div>

      {error && (
        <p className="flex items-start gap-1.5 text-xs text-accent-red leading-relaxed" role="alert">
          <CircleAlert className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden />
          <span className="min-w-0 break-words">{error}</span>
        </p>
      )}

      {job && (
        <div className="space-y-2.5">
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-text-secondary">
            <span className="font-medium text-text-primary">{job.title || '未识别岗位'}</span>
            {job.level && <span className="rounded-lg bg-bg-tertiary px-1.5 py-0.5 text-[10px]">{job.level}</span>}
            {job.company && <span className="text-text-muted">{job.company}</span>}
          </div>

          {technologies.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {technologies.map((tech) => (
                <span key={tech} className="rounded-lg bg-accent-blue/10 px-2 py-0.5 text-[10px] text-accent-blue">
                  {tech}
                </span>
              ))}
            </div>
          )}

          {mustHave.length > 0 && (
            <ul className="space-y-1">
              {mustHave.map((item, idx) => (
                <li key={idx} className="flex items-start gap-1.5 text-xs text-text-secondary leading-relaxed">
                  <CheckCircle2 className="mt-0.5 h-3 w-3 flex-shrink-0 text-accent-green" aria-hidden />
                  <span className="min-w-0 break-words">{item}</span>
                </li>
              ))}
            </ul>
          )}

          {niceToHave.length > 0 && (
            <p className="text-[11px] text-text-muted leading-relaxed">加分：{niceToHave.join('；')}</p>
          )}

          {dimensions.length > 0 && (
            <p className="text-[11px] text-text-muted leading-relaxed">可能考察：{dimensions.join(' / ')}</p>
          )}

          {alignment.length > 0 && (
            <div className="space-y-1.5 border-t border-bg-tertiary/70 pt-2">
              {alignment.map((item, idx) => (
                <div key={idx} className="flex items-start gap-1.5 text-xs leading-relaxed">
                  <span className={`flex-shrink-0 font-medium ${ALIGNMENT_TONE[item.status ?? ''] ?? 'text-text-muted'}`}>
                    {item.status ?? 'UNKNOWN'}
                  </span>
                  <span className="min-w-0 break-words text-text-secondary">
                    {item.requirement_text}
                    {item.explanation && <span className="text-text-muted"> — {item.explanation}</span>}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="space-y-3 border-t border-bg-tertiary/70 pt-2.5">
            <GapMapSection gaps={gaps} />
            <AttackSurfaceSection items={attackSurface} />
            <QuestionGraphSection nodes={questionNodes} />
            <StoriesSection items={storyItems} prompts={storyPrompts} />
          </div>
        </div>
      )}
    </div>
  )
}
