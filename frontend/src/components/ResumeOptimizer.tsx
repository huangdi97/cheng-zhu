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
    <div className="flex-1 min-h-0 overflow-y-auto" data-testid="resume-workspace">
      <div className="grid gap-8 p-4 lg:grid-cols-[minmax(320px,0.82fr)_minmax(0,1.18fr)]">
        <section aria-labelledby="resume-source-heading" className="min-w-0">
          <p className="text-[11px] font-medium text-text-muted">PERSONAL RECORD</p>
          <h2 id="resume-source-heading" className="mt-1 text-base font-semibold text-text-primary">当前履历事实</h2>
          <p className="mt-1 max-w-2xl text-xs leading-5 text-text-secondary">
            这里选中的简历是成竹理解你经历的一个来源，不是另一套独立档案。准备、练习、上场和复盘都会引用同一份当前简历。
          </p>

          <div className="mt-4">
            <ResumeMountPanel
              title="当前简历"
              description="选一份你当前愿意用于求职和面试的履历。"
              sharedNote="切换简历后，新的 Interview Pack 才会使用新的内容；不会改写已经冻结的历史场次。"
              variant="light"
              className="!rounded-none !border-x-0 !border-b-0 !border-t !border-bg-tertiary/70 !bg-transparent !px-0"
            />
          </div>

          {uploadError && (
            <div className="mt-3 flex items-center gap-2 border-l-2 border-status-risk/45 pl-3 text-xs text-status-risk">
              <span className="flex-1">{uploadError}</span>
              <button type="button" onClick={() => setUploadError(null)} aria-label="关闭错误"><X className="h-3 w-3" /></button>
            </div>
          )}

          <div className="mt-5 border-t border-bg-tertiary/70 pt-4">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-text-primary">拿这份简历去匹配哪个岗位</h3>
                <p className="mt-0.5 text-[11px] leading-5 text-text-muted">粘贴 JD 只是做这次分析，不会把它另存成一个新的 Goal。</p>
              </div>
              <span className="text-[10px] tabular-nums text-text-muted">{jdText.trim().length} 字</span>
            </div>
            <textarea
              value={jdText}
              onChange={e => setJdText(e.target.value)}
              placeholder="粘贴目标岗位 JD，重点保留职责、能力要求和业务场景。"
              className="mt-3 min-h-[210px] w-full resize-y rounded-xl border border-bg-hover bg-bg-primary px-3 py-2.5 text-xs leading-5 text-text-primary focus:border-accent-blue focus:outline-none"
            />
            <button
              type="button"
              onClick={handleAnalyze}
              disabled={isAnalyzing || !jdText.trim() || !config?.has_resume}
              className="mt-3 w-full rounded-lg bg-accent-blue px-3 py-2 text-xs font-medium text-white hover:bg-accent-blue/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isAnalyzing ? '正在分析这份履历…' : '分析这份履历与岗位'}
            </button>
            {!config?.has_resume ? <p className="mt-1.5 text-[10px] text-text-muted">先选用一份简历，才能开始匹配。</p> : null}
          </div>
        </section>

        <section aria-labelledby="resume-fit-heading" className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-bg-tertiary/70 pb-3">
            <div>
              <p className="text-[11px] font-medium text-text-muted">ROLE FIT</p>
              <h2 id="resume-fit-heading" className="mt-1 text-base font-semibold text-text-primary">这份履历对这个岗位怎么讲</h2>
              <p className="mt-1 text-xs leading-5 text-text-secondary">优先找“已有证据怎么表达得更准确”，其次才是缺口；不把没做过的事补进简历。</p>
            </div>
            <span className="text-[11px] text-text-muted">{analysisState}</span>
          </div>

          <div className="pt-4">
            {!displayText && isAnalyzing ? (
              <div className="space-y-3" aria-busy="true" aria-live="polite">
                <span className="sr-only">正在分析简历与 JD 的匹配度…</span>
                <div className="flex items-center gap-2 text-xs text-accent-blue">
                  <span className="inline-block h-2 w-2 rounded-full bg-accent-blue animate-pulse" />
                  正在对照岗位要求与当前履历…
                </div>
                {[0.7, 0.95, 0.85, 0.6, 0.9].map((w, i) => (
                  <div key={i} className="space-y-1.5">
                    <div className="h-3 w-1/4 rounded bg-bg-tertiary/60 animate-pulse" style={{ animationDelay: `${i * 120}ms` }} />
                    <div className="h-2 rounded bg-bg-tertiary/40 animate-pulse" style={{ animationDelay: `${i * 120 + 40}ms`, width: `${w * 100}%` }} />
                  </div>
                ))}
              </div>
            ) : !displayText ? (
              <div className="py-10 text-center text-text-muted">
                <FileSearch className="mx-auto h-7 w-7 opacity-30" />
                <p className="mt-3 text-sm font-medium text-text-primary">先选履历，再给一个真实岗位。</p>
                <p className="mx-auto mt-1 max-w-md text-xs leading-5">结果会分清：当前履历已经能证明什么、哪些要求没有证据、哪些句子只是表达可以更清楚。</p>
              </div>
            ) : (
              <>
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap gap-2 text-[10px] text-text-muted">
                    <span>岗位要求</span><span>·</span><span>已有证据</span><span>·</span><span>表达缺口</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button type="button" onClick={handleCopy} disabled={!displayText}
                      className="inline-flex items-center gap-1 rounded-lg border border-bg-hover/60 px-2.5 py-1.5 text-[11px] text-text-secondary hover:bg-bg-hover/35 disabled:opacity-40">
                      <Clipboard className="h-3.5 w-3.5" />复制全部
                    </button>
                    <button type="button" onClick={handleCopyRewrite}
                      className="inline-flex items-center gap-1 rounded-lg border border-bg-hover/60 px-2.5 py-1.5 text-[11px] text-text-secondary hover:bg-bg-hover/35">
                      <Clipboard className="h-3.5 w-3.5" />只复制改写建议
                    </button>
                  </div>
                </div>
                <div
                  className={`prose prose-sm max-w-none markdown-body
                    ${lightMarkdown ? '' : 'prose-invert'}
                    prose-headings:text-text-primary prose-headings:text-sm prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-2
                    prose-p:text-text-secondary prose-p:text-xs prose-p:leading-relaxed
                    prose-li:text-text-secondary prose-li:text-xs
                    prose-strong:text-text-primary
                    prose-table:text-xs
                    prose-th:text-text-primary prose-th:bg-bg-tertiary prose-th:px-2 prose-th:py-1
                    prose-td:text-text-secondary prose-td:px-2 prose-td:py-1 prose-td:border-bg-hover
                  `}
                >
                  <ReactMarkdown>{displayText}</ReactMarkdown>
                  {isAnalyzing && <span className="ml-0.5 inline-block h-3 w-1.5 rounded-sm bg-accent-blue animate-pulse" />}
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
