import { useEffect, useRef, useState } from 'react'
import { Brain, PencilLine, Check, RefreshCw, Eraser } from 'lucide-react'
import { useInterviewStore } from '@/stores/configStore'
import { api } from '@/lib/api'

function MemoBody({ text }: { text: string }) {
  const lines = (text || '').split('\n')
  const blocks: React.ReactNode[] = []
  let list: string[] = []
  let listKey = 0
  const flushList = () => {
    if (!list.length) return
    blocks.push(
      <ul key={`ul-${listKey++}`} className="space-y-1">
        {list.map((item, idx) => (
          <li key={idx} className="flex items-start gap-1.5">
            <span className="mt-[5px] h-1 w-1 rounded-full bg-accent-blue/70 flex-shrink-0" />
            <span className="min-w-0">{item}</span>
          </li>
        ))}
      </ul>,
    )
    list = []
  }
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    if (trimmed.startsWith('## ')) {
      flushList()
      blocks.push(
        <div key={`h-${listKey++}`} className="mt-2 mb-1 text-[11px] font-semibold text-accent-blue first:mt-0">
          {trimmed.replace(/^##\s*/, '')}
        </div>,
      )
    } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      list.push(trimmed.replace(/^[-*]\s*/, ''))
    } else {
      flushList()
      blocks.push(
        <p key={`p-${listKey++}`} className="text-xs text-text-secondary leading-relaxed">
          {trimmed}
        </p>,
      )
    }
  }
  flushList()
  return <div className="space-y-1">{blocks}</div>
}

export default function MemoPanel() {
  const systemSummary = useInterviewStore((s) => s.systemSummary)
  const memoManual = useInterviewStore((s) => s.memoManual)
  const setMemo = useInterviewStore((s) => s.setMemo)
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [draft, setDraft] = useState(memoManual)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(false)
  const timerRef = useRef<number | null>(null)

  // 外部广播（如服务端压缩完成后）更新手动备忘时同步草稿
  useEffect(() => {
    setDraft(memoManual)
  }, [memoManual])

  const save = async (text: string) => {
    setSaving(true)
    try {
      await api.updateMemo(text)
      setMemo({ memo_manual: text })
      pushToast('面试备忘已保存', 'success')
    } catch (err) {
      pushToast('备忘保存失败，请重试', 'error')
    } finally {
      setSaving(false)
    }
  }

  // 自动保存（停止输入 800ms 后）
  const onDraftChange = (text: string) => {
    setDraft(text)
    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => {
      void save(text)
    }, 800)
  }

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const hasAuto = Boolean((systemSummary || '').trim())
  const hasManual = Boolean((memoManual || '').trim())

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-bg-tertiary/60 flex-shrink-0">
        <Brain className="w-4 h-4 text-accent-blue" />
        <span className="text-sm font-semibold tracking-tight">面试备忘</span>
        <span className="ml-auto flex items-center gap-1 text-[10px] text-text-muted">
          {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3 text-accent-green" />}
          {saving ? '保存中' : '自动保存'}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {/* 自动滚动备忘 */}
        <section className="rounded-lg border border-bg-hover/40 bg-bg-tertiary/30 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <span className="text-[10px] font-semibold text-accent-blue">自动滚动备忘</span>
            {!hasAuto && <span className="text-[10px] text-text-muted">（长面时自动压缩生成）</span>}
          </div>
          {hasAuto ? (
            <MemoBody text={systemSummary} />
          ) : (
            <p className="text-[11px] text-text-muted leading-relaxed">还没有自动备忘。对话超过一定轮数后，系统会把前面问答压成「已问问题 / 我声称的事实 / 面试官关注点」三段。</p>
          )}
        </section>

        {/* 手动备忘 */}
        <section className="rounded-lg border border-bg-hover/40 bg-bg-tertiary/30 p-3">
          <div className="flex items-center gap-1.5 mb-2">
            <PencilLine className="w-3 h-3 text-accent-amber" />
            <span className="text-[10px] font-semibold text-accent-amber">手动备忘</span>
            <span className="text-[10px] text-text-muted">（写下来会注入 AI 上下文，可随时改）</span>
            {hasManual && !editing && (
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="ml-auto text-[10px] text-accent-blue hover:underline"
              >
                编辑
              </button>
            )}
            {editing && (
              <button
                type="button"
                onClick={() => {
                  setEditing(false)
                  setDraft(memoManual)
                }}
                className="ml-auto text-[10px] text-text-muted hover:text-text-primary"
              >
                取消
              </button>
            )}
          </div>
          {editing || !hasManual ? (
            <div className="space-y-2">
              <textarea
                value={draft}
                onChange={(e) => onDraftChange(e.target.value)}
                rows={6}
                placeholder={'例如：\n- 重点强调支付项目的降级方案（QPS 从 2k 扛到 8k）\n- 别主动提上一家的技术栈\n- 面试官关注 Redis 一致性，多准备缓存穿透'}
                className="w-full resize-none rounded-lg border border-bg-hover bg-bg-primary/60 px-2.5 py-2 text-xs text-text-primary leading-relaxed outline-none focus:border-accent-blue/60"
              />
              <button
                type="button"
                onClick={() => {
                  void save(draft)
                  setEditing(false)
                }}
                className="w-full rounded-lg bg-accent-blue/90 py-1.5 text-xs font-medium text-white hover:bg-accent-blue disabled:opacity-60"
                disabled={saving}
              >
                保存备忘
              </button>
              <button
                type="button"
                onClick={() => {
                  setDraft('')
                  void save('')
                }}
                className="w-full flex items-center justify-center gap-1 rounded-lg border border-bg-hover py-1.5 text-[10px] text-text-muted hover:text-text-primary"
              >
                <Eraser className="w-3 h-3" /> 清空手动备忘
              </button>
            </div>
          ) : (
            <p className="text-xs text-text-secondary leading-relaxed whitespace-pre-wrap">{memoManual}</p>
          )}
        </section>
      </div>
    </div>
  )
}
