import { useEffect, useRef, useState } from 'react'
import { useInterviewStore } from '@/stores/configStore'
import { useShallow } from 'zustand/react/shallow'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'
import { isLightColorScheme } from '@/lib/colorScheme'
import { api } from '@/lib/api'
import { Clipboard, FileSearch, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { ResumeMountPanel } from '@/components/resume/ResumeMount'

const JD_STORAGE_KEY = 'ia-resume-opt-jd-draft'

function readStorage(key: string, fallback = ''): string {
  try {
    return window.localStorage?.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

function writeStorage(key: string, value: string) {
  try {
    window.localStorage?.setItem(key, value)
  } catch {
    /* ignore */
  }
}

function extractRewriteSuggestions(text: string): string {
  const normalized = String(text || '').trim()
  if (!normalized) return ''
  const match = normalized.match(/^#{2,3}\s*(?:✏️|📝)?\s*(?:简历)?改写建议.*$/m)
  if (!match || match.index == null) return normalized
  return normalized.slice(match.index).trim()
}

export default function ResumeOptimizer() {
  const [jdText, setJdText] = useState(() => readStorage(JD_STORAGE_KEY))
  const [optimizingLocal, setOptimizingLocal] = useState(false)
  const { config, resumeOptStreaming, resumeOptResult, resumeOptLoading, setToastMessage, resetResumeOpt } =
    useInterviewStore(
      useShallow((s) => ({
        config: s.config,
        resumeOptStreaming: s.resumeOptStreaming,
        resumeOptResult: s.resumeOptResult,
        resumeOptLoading: s.resumeOptLoading,
        setToastMessage: s.setToastMessage,
        resetResumeOpt: s.resetResumeOpt,
      })),
    )
  const colorScheme = useUiPrefsStore((s) => s.colorScheme)
  const lightMarkdown = isLightColorScheme(colorScheme)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const displayText = resumeOptResult || resumeOptStreaming
  const isAnalyzing = resumeOptLoading || optimizingLocal
  const analysisState = isAnalyzing ? '分析中' : displayText ? '已生成' : '待开始'

  useEffect(() => {
    writeStorage(JD_STORAGE_KEY, jdText)
  }, [jdText])

  useEffect(() => {
    if (!optimizingLocal) return
    if (resumeOptLoading || displayText) {
      setOptimizingLocal(false)
    }
  }, [displayText, optimizingLocal, resumeOptLoading])

  const handleAnalyze = async () => {
    if (!jdText.trim()) return
    if (!config?.has_resume) {
      setUploadError('请先上传简历')
      return
    }
    try {
      setUploadError(null)
      setOptimizingLocal(true)
      resetResumeOpt('__pending__')
      await api.resumeOptimize(jdText.trim())
    } catch (e: any) {
      setOptimizingLocal(false)
      setUploadError(e.message || '分析失败')
    }
  }

  const handleCopy = async () => {
    if (!displayText) return
    try {
      await navigator.clipboard.writeText(displayText)
      setToastMessage('分析结果已复制')
    } catch {
      setToastMessage('复制失败，请检查浏览器权限')
    }
  }

  const handleCopyRewrite = async () => {
    if (!displayText) return
    const rewrite = extractRewriteSuggestions(displayText)
    try {
      await navigator.clipboard.writeText(rewrite || displayText)
      setToastMessage(rewrite && rewrite !== displayText ? '改写建议已复制' : '未识别到改写建议，已复制完整结果')
    } catch {
      setToastMessage('复制失败，请检查浏览器权限')
    }
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-4" data-testid="resume-workspace">
      <section aria-label="简历边界" className="grid gap-3 border-y border-bg-tertiary/70 py-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <div>
          <p className="text-sm font-semibold text-text-primary">一份当前简历，对照一个目标岗位</p>
          <p className="mt-0.5 max-w-3xl text-xs leading-5 text-text-secondary">
            这里不维护第二份“AI 简历”。成竹只读取你当前选中的简历，用目标 JD 找出该强调、补证据或改写得更清楚的地方。
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className={`text-sm font-semibold ${config?.has_resume ? 'text-status-direct' : 'text-text-primary'}`}>
            {config?.has_resume ? '当前简历已就绪' : '先选择一份简历'}
          </p>
          <p className="mt-0.5 text-[10px] text-text-muted">分析不会直接修改原文件</p>
        </div>
      </section>

      <div className="mt-5 grid gap-8 lg:grid-cols-[minmax(320px,0.78fr)_minmax(0,1.22fr)]">
        <aside aria-labelledby="resume-input-heading" className="min-w-0">
          <h3 id="resume-input-heading" className="text-sm font-semibold text-text-primary">这次要投什么</h3>
          <p className="mt-0.5 text-[11px] leading-5 text-text-muted">先确认当前简历，再把目标岗位要求放进来。JD 只用于这次简历对照，不会被写成你的个人事实。</p>

          <div className="mt-4">
            <ResumeMountPanel
              title="当前简历"
              description="准备、练习和复盘共用这份当前简历。"
              sharedNote="切换简历后，只会影响之后新冻结的 Interview Pack；旧场次保持原样。"
              variant="light"
            />
          </div>

          {uploadError ? (
            <div role="alert" className="mt-3 flex items-center gap-2 border-l-2 border-status-risk/45 pl-3 text-xs text-status-risk">
              <span className="flex-1">{uploadError}</span>
              <button type="button" aria-label="关闭错误提示" onClick={() => setUploadError(null)}><X className="h-3 w-3" /></button>
            </div>
          ) : null}

          <label className="mt-5 block">
            <span className="flex items-baseline justify-between gap-3">
              <span className="text-xs font-medium text-text-secondary">目标岗位 JD</span>
              <span className="text-[10px] tabular-nums text-text-muted">{jdText.trim().length} 字</span>
            </span>
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="粘贴这个岗位真正会考察的职责、要求和加分项…"
              className="mt-1.5 min-h-[220px] w-full resize-y rounded-xl border border-bg-hover bg-bg-primary px-3 py-2.5 text-xs leading-5 text-text-primary focus:border-accent-blue focus:outline-none"
            />
          </label>

          <div className="mt-3 [&>button]:w-full">
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={isAnalyzing || !jdText.trim() || !config?.has_resume}
              className="w-full rounded-lg bg-accent-blue px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-accent-blue/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isAnalyzing ? '正在对照简历与岗位…' : '分析这份简历'}
            </button>
          </div>
        </aside>

        <main aria-labelledby="resume-result-heading" className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-bg-tertiary/70 pb-3">
            <div>
              <p className="text-[11px] font-medium text-text-muted">FOR THIS ROLE</p>
              <h3 id="resume-result-heading" className="mt-1 text-base font-semibold text-text-primary">这份简历该怎么更贴近岗位</h3>
              <p className="mt-0.5 text-[11px] text-text-muted">关注岗位真正要求的能力、你已有的证据，以及哪些表达需要更具体。</p>
            </div>
            {displayText ? (
              <div className="flex gap-2">
                <button type="button" onClick={handleCopy}
                  className="inline-flex items-center gap-1 rounded-lg border border-bg-hover px-2.5 py-1.5 text-[11px] text-text-secondary hover:bg-bg-hover/35 hover:text-text-primary">
                  <Clipboard className="h-3.5 w-3.5" />复制全部
                </button>
                <button type="button" onClick={handleCopyRewrite}
                  className="inline-flex items-center gap-1 rounded-lg border border-bg-hover px-2.5 py-1.5 text-[11px] text-text-secondary hover:bg-bg-hover/35 hover:text-text-primary">
                  <Clipboard className="h-3.5 w-3.5" />只复制改写
                </button>
              </div>
            ) : null}
          </div>

          <div className="pt-4">
            {!displayText && isAnalyzing ? (
              <div className="max-w-2xl space-y-4" aria-busy="true" aria-live="polite">
                <p className="text-xs font-medium text-accent-blue">正在找岗位要求与你已有证据之间的差距…</p>
                {[0.78, 0.94, 0.66, 0.86].map((w, i) => (
                  <div key={i} className="space-y-1.5">
                    <div className="h-3 w-1/4 rounded bg-bg-tertiary/70 animate-pulse" />
                    <div className="h-2 rounded bg-bg-tertiary/45 animate-pulse" style={{ width: `${w * 100}%` }} />
                    <div className="h-2 rounded bg-bg-tertiary/45 animate-pulse" style={{ width: `${Math.max(0.42, w - 0.18) * 100}%` }} />
                  </div>
                ))}
              </div>
            ) : !displayText ? (
              <div className="max-w-xl border-y border-bg-tertiary/70 py-5">
                <FileSearch className="h-6 w-6 text-text-muted" aria-hidden />
                <p className="mt-2 text-sm font-medium text-text-primary">先选简历，再给一个具体岗位</p>
                <p className="mt-1 text-xs leading-5 text-text-secondary">
                  成竹会把结果拆成：岗位真正看重什么、你的简历已经证明了什么、哪些地方只是写得不够清楚，以及哪些要求目前没有证据。
                </p>
                <p className="mt-2 text-[11px] leading-5 text-text-muted">
                  “没有证据”不会被自动补成经历；它只会被明确标出来。
                </p>
              </div>
            ) : (
              <div
                className={`prose prose-sm max-w-none markdown-body
                ${lightMarkdown ? '' : 'prose-invert'}
                prose-headings:text-text-primary prose-headings:text-sm prose-headings:font-semibold prose-headings:mt-5 prose-headings:mb-2
                prose-p:text-text-secondary prose-p:text-xs prose-p:leading-relaxed
                prose-li:text-text-secondary prose-li:text-xs
                prose-strong:text-text-primary
                prose-table:text-xs
                prose-th:text-text-primary prose-th:bg-bg-tertiary prose-th:px-2 prose-th:py-1
                prose-td:text-text-secondary prose-td:px-2 prose-td:py-1 prose-td:border-bg-hover`}
              >
                <ReactMarkdown>{displayText}</ReactMarkdown>
                {isAnalyzing ? <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse rounded-sm bg-accent-blue" /> : null}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
