import { useCallback, useEffect, useState } from 'react'
import { BookOpen, FileQuestion, Library, Plus } from 'lucide-react'
import { api, type QuestionBank } from '@/lib/api'
import QuickNotesPanel from './QuickNotesPanel'

export default function LibraryWorkspace() {
  const [banks, setBanks] = useState<QuestionBank[]>([])
  const [name, setName] = useState('')
  const [question, setQuestion] = useState('')
  const [activeBank, setActiveBank] = useState<QuestionBank | null>(null)
  const [kbCount, setKbCount] = useState(0)

  const loadBanks = useCallback(() => {
    api.productQuestionBanks().then((r) => setBanks(r.items ?? [])).catch(() => setBanks([]))
  }, [])
  useEffect(() => {
    loadBanks()
    api.kbDocs().then((r) => setKbCount(r.items?.length ?? 0)).catch(() => setKbCount(0))
  }, [loadBanks])

  const createBank = async () => {
    if (!name.trim()) return
    await api.productCreateQuestionBank({ name })
    setName('')
    loadBanks()
  }
  const openBank = async (id: number) => {
    const bank = await api.productQuestionBank(id)
    setActiveBank(bank)
  }
  const addQuestion = async () => {
    if (!activeBank || !question.trim()) return
    await api.productAddQuestion(activeBank.id, { question, origin: 'USER_ADDED' })
    setQuestion('')
    await openBank(activeBank.id)
    loadBanks()
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6" data-testid="library-workspace">
      <div className="mx-auto max-w-6xl space-y-5">
        <header>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-accent-blue"><Library className="h-4 w-4" /> 资料库</div>
          <h2 className="mt-1 text-2xl font-bold text-text-primary">不同材料，不同角色</h2>
          <p className="mt-1 text-sm text-text-muted">Knowledge 不自动证明个人经历；Quick Notes 只是你写给自己看的现场短笔记；Question Bank 只用于练习。</p>
        </header>

        <section className="grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4"><BookOpen className="h-5 w-5 text-accent-green" /><div className="mt-2 text-sm font-semibold text-text-primary">Knowledge Base</div><div className="mt-1 text-2xl font-semibold text-text-primary">{kbCount}</div><div className="text-xs text-text-muted">篇已索引文档</div></div>
          <div className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4"><FileQuestion className="h-5 w-5 text-accent-blue" /><div className="mt-2 text-sm font-semibold text-text-primary">Question Banks</div><div className="mt-1 text-2xl font-semibold text-text-primary">{banks.length}</div><div className="text-xs text-text-muted">个题库</div></div>
          <div className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4"><Library className="h-5 w-5 text-accent-amber" /><div className="mt-2 text-sm font-semibold text-text-primary">Material Roles</div><div className="mt-1 text-xs leading-relaxed text-text-muted">Resume / Project / JD / KB / Quick Notes / Question Banks / Skills / Stories</div></div>
        </section>

        <section className="grid gap-5 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-sm font-semibold text-text-primary">Quick Notes</h3>
            <QuickNotesPanel />
          </div>
          <div className="space-y-3">
            <div className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4">
              <h3 className="text-sm font-semibold text-text-primary">Question Banks</h3>
              <div className="mt-3 flex gap-2">
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="新题库名称" className="min-w-0 flex-1 rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary" />
                <button type="button" onClick={() => void createBank()} className="inline-flex items-center gap-1 rounded-xl bg-container-primary px-3 py-2 text-xs font-semibold text-container-on-primary"><Plus className="h-3.5 w-3.5" /> 创建</button>
              </div>
              <div className="mt-3 space-y-2">
                {banks.map((bank) => (
                  <button key={bank.id} type="button" onClick={() => void openBank(bank.id)}
                    className="flex w-full items-center justify-between rounded-xl bg-bg-tertiary/40 p-3 text-left hover:bg-bg-hover/60">
                    <div><div className="text-sm font-semibold text-text-primary">{bank.name}</div><div className="mt-0.5 text-[11px] text-text-muted">{bank.source_type} · {bank.item_count ?? 0} 题</div></div>
                    <span className="text-xs text-text-muted">打开</span>
                  </button>
                ))}
              </div>
            </div>

            {activeBank && (
              <div className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4">
                <div className="text-sm font-semibold text-text-primary">{activeBank.name}</div>
                <div className="mt-3 flex gap-2">
                  <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="添加练习题" className="min-w-0 flex-1 rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary" />
                  <button type="button" onClick={() => void addQuestion()} className="rounded-xl border border-bg-hover px-3 py-2 text-xs font-semibold text-text-secondary">添加</button>
                </div>
                <ol className="mt-3 space-y-2">
                  {(activeBank.items ?? []).map((item) => <li key={item.id} className="rounded-xl bg-bg-tertiary/40 p-3 text-xs text-text-secondary"><div className="font-medium text-text-primary">{item.question}</div><div className="mt-1 text-[10px] text-text-muted">{item.category} · {item.difficulty} · {item.origin}</div></li>)}
                </ol>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
