import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, ChevronDown, ChevronRight, RefreshCw, Route, Sparkles, X } from 'lucide-react'
import { api, getErrorMessage } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'

/** 面试策略树提示条：展示当前问题命中的节点、追问预测与高危提示。 */
export default function CopilotHintPanel() {
  const copilotHint = useInterviewStore((s) => s.copilotHint)
  const setCopilotHint = useInterviewStore((s) => s.setCopilotHint)
  const config = useInterviewStore((s) => s.config)
  const isRecording = useInterviewStore((s) => s.isRecording)

  const [collapsed, setCollapsed] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [hasTree, setHasTree] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTree = useCallback(async () => {
    try {
      const res = await api.copilotStrategyGet(null)
      setHasTree(Boolean(res.tree))
      if (!res.tree) setCopilotHint(null)
    } catch {
      setHasTree(false)
    }
  }, [setCopilotHint])

  useEffect(() => {
    void loadTree()
  }, [loadTree])

  const handleGenerate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const res = await api.copilotStrategyGenerate({
        role: config?.position ?? '',
        jd_text: config?.jd_text ?? '',
        resume_text: config?.resume_text ?? '',
      })
      setHasTree(Boolean(res.tree))
      setCollapsed(false)
    } catch (err) {
      setError(getErrorMessage(err, '策略树生成失败'))
    } finally {
      setGenerating(false)
    }
  }

  const handleDismiss = () => setCopilotHint(null)

  const show = hasTree || Boolean(copilotHint) || isRecording
  if (!show) return null

  return (
    <div className="flex-shrink-0 border-t border-bg-tertiary bg-bg-secondary/80 backdrop-blur-sm px-3 py-2">
      <div className="flex items-start gap-2">
        <button
          type="button"
          onClick={() => setCollapsed((v) => !v)}
          className="mt-0.5 inline-flex items-center gap-1 text-[11px] font-semibold text-text-secondary hover:text-text-primary"
          title={copilotHint ? `当前节点：${copilotHint.label || copilotHint.node_id || ''}` : '面试策略树'}
        >
          {collapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          <Route className="h-3.5 w-3.5 text-accent-blue/70" />
          面试策略树
          {copilotHint?.label ? <span className="text-accent-blue">· {copilotHint.label}</span> : null}
        </button>
        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-1 rounded-md border border-bg-hover bg-bg-tertiary/50 px-2 py-1 text-[11px] text-text-secondary hover:text-accent-blue disabled:opacity-50"
            title="用当前 JD/简历生成或刷新提问策略树（面试准备页填 JD/简历后效果最好）"
          >
            {generating ? <RefreshCw className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
            {generating ? '生成中…' : hasTree ? '刷新策略树' : '生成策略树'}
          </button>
          {copilotHint && (
            <button
              type="button"
              onClick={handleDismiss}
              aria-label="关闭本次提示"
              className="inline-flex items-center rounded-md px-1 py-1 text-text-muted hover:text-text-primary"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {!collapsed && (
        <div className="mt-1.5 space-y-1.5">
          {error && <p className="text-[11px] text-accent-red">{error}</p>}
          {!hasTree && !generating && (
            <p className="text-[11px] text-text-muted leading-relaxed">
              还没生成策略树：填好 JD/简历后点「生成策略树」，面试中就能实时预测追问方向与高危点。
            </p>
          )}
          {copilotHint && (
            <>
              {copilotHint.uncertain && (
                <p className="rounded-md border border-bg-hover bg-bg-tertiary/45 px-2 py-1.5 text-[11px] text-text-muted">
                  可能仍在上一话题：当前匹配置信度较低，以下追问只作参考。
                </p>
              )}
              {copilotHint.high_risk && (
                <p className="flex items-start gap-1.5 rounded-md border border-accent-amber/30 bg-accent-amber/10 px-2 py-1.5 text-[11px] text-accent-amber">
                  <AlertTriangle className="mt-0.5 h-3 w-3 flex-shrink-0" />
                  <span>高危点：{copilotHint.risk_advice || copilotHint.advice || '注意深挖'}</span>
                </p>
              )}
              {copilotHint.predicted_followups && copilotHint.predicted_followups.length > 0 && (
                <div className="rounded-md border border-bg-hover bg-bg-tertiary/40 px-2 py-1.5">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-text-muted">可能追问</p>
                  <ul className="mt-0.5 space-y-0.5">
                    {copilotHint.predicted_followups.map((f, i) => (
                      <li key={i} className="text-[11px] text-text-secondary leading-snug">
                        <span className="text-accent-blue/80">{f.label || '追问'}：</span>
                        {f.question}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
