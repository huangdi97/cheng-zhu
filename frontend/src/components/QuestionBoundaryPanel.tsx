import { CheckCircle2, GitBranch, Loader2, Play, X } from 'lucide-react'
import { api, getErrorMessage } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'

const TYPE_LABELS: Record<string, string> = {
  coding: '编程题',
  system_design: '系统设计',
  behavioral: '行为题',
  project: '项目深挖',
  troubleshooting: '排障题',
  technical: '技术题',
  hr: 'HR',
  general: '综合题',
}

export default function QuestionBoundaryPanel() {
  const status = useInterviewStore((s) => s.questionParseStatus)
  const setStatus = useInterviewStore((s) => s.setQuestionParseStatus)
  const pushToast = useInterviewStore((s) => s.pushToast)

  if (!status || status.stage === 'idle' || status.stage === 'discarded') return null

  const isAssembling = status.stage === 'assembling'
  const isParsed = status.stage === 'parsed' || status.stage === 'answering'

  const flush = async () => {
    try {
      const result = await api.questionBoundaryFlush()
      if (!result.flushed) pushToast('当前没有等待确认的问题', 'info')
    } catch (error) {
      pushToast(getErrorMessage(error, '立即作答失败'), 'error')
    }
  }

  const discard = async () => {
    try {
      await api.questionBoundaryDiscard()
      setStatus(null)
    } catch (error) {
      pushToast(getErrorMessage(error, '忽略失败'), 'error')
    }
  }

  return (
    <section
      aria-live="polite"
      className="flex-shrink-0 border-t border-bg-tertiary bg-bg-secondary/95 px-3 py-2"
    >
      <div className="flex items-start gap-2">
        <span className={`mt-0.5 inline-flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg ${
          isAssembling ? 'bg-accent-blue/10 text-accent-blue' : 'bg-accent-green/10 text-accent-green'
        }`}>
          {isAssembling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitBranch className="h-3.5 w-3.5" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-text-primary">
              {isAssembling ? '正在组织问题' : '问题边界已确认'}
            </span>
            {isParsed && status.clusters && status.clusters.length > 1 ? (
              <span className="rounded-full border border-accent-blue/25 bg-accent-blue/10 px-1.5 py-0.5 text-[10px] font-medium text-accent-blue">
                {status.clusters.length} 个独立问题
              </span>
            ) : null}
            {status.needs_confirmation ? (
              <span className="rounded-full border border-accent-amber/25 bg-accent-amber/10 px-1.5 py-0.5 text-[10px] font-medium text-accent-amber">
                低置信度
              </span>
            ) : null}
          </div>
          <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-text-muted" title={status.raw_text || status.message}>
            {status.raw_text || status.message}
          </p>
          {isParsed && status.clusters?.length ? (
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {status.clusters.map((cluster, index) => (
                <span
                  key={`${cluster.primary_question}-${index}`}
                  title={cluster.primary_question}
                  className="inline-flex max-w-[320px] items-center gap-1 rounded-lg border border-bg-hover bg-bg-tertiary/45 px-2 py-1 text-[11px] text-text-secondary"
                >
                  <CheckCircle2 className="h-3 w-3 flex-shrink-0 text-accent-green" />
                  <span className="truncate">{cluster.primary_question}</span>
                  <span className="flex-shrink-0 text-text-muted">
                    {TYPE_LABELS[cluster.question_type || 'general'] || '综合题'}
                    {cluster.subquestions?.length ? ` · ${cluster.subquestions.length} 子问` : ''}
                  </span>
                </span>
              ))}
            </div>
          ) : null}
        </div>
        {isAssembling ? (
          <div className="flex flex-shrink-0 items-center gap-1">
            <button
              type="button"
              onClick={() => void flush()}
              className="inline-flex items-center gap-1 rounded-lg bg-accent-blue px-2 py-1.5 text-[11px] font-medium text-white disabled:opacity-50"
              title="不再等待后续补充，立即提交当前问题"
            >
              <Play className="h-3 w-3" />
              立即作答
            </button>
            <button
              type="button"
              onClick={() => void discard()}
              aria-label="忽略当前候选问题"
              className="inline-flex h-7 w-7 items-center justify-center rounded-lg text-text-muted hover:bg-bg-tertiary hover:text-text-primary"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : null}
      </div>
    </section>
  )
}
