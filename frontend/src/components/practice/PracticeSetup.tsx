import { useEffect, useMemo, useState } from 'react'
import { Play, Users } from 'lucide-react'
import { api, type QuestionBank } from '@/lib/api'

export interface PracticeSetupValue {
  rounds: number
  round_type: string
  persona: string
  demeanor: string
  difficulty: string
  question_bank_ids: number[]
  panel_personas: Array<{ role: string; demeanor?: string; domain?: string }>
}

const ROUNDS = [
  ['technical', '技术一面'],
  ['project', '项目深挖'],
  ['system_design', 'System Design'],
  ['hiring_manager', 'Hiring Manager'],
  ['hr', 'HR'],
  ['behavioral', 'Behavioral'],
] as const

const PERSONAS = ['Tech Lead', 'Hiring Manager', 'Product Partner', 'Senior Engineer']
const DEMEANORS = [
  ['neutral', '中性'],
  ['friendly', '友好'],
  ['strong_followup', '强追问'],
  ['skeptical', '怀疑型'],
  ['fast_paced', '快节奏'],
] as const
const DIFFICULTY = [
  ['warmup', '热身'],
  ['standard', '标准'],
  ['pressure', '压力'],
] as const

export default function PracticeSetup({
  defaultRounds = 5,
  busy,
  onStart,
}: {
  defaultRounds?: number
  busy?: boolean
  onStart: (value: PracticeSetupValue) => void
}) {
  const [banks, setBanks] = useState<QuestionBank[]>([])
  const [value, setValue] = useState<PracticeSetupValue>({
    rounds: defaultRounds,
    round_type: 'technical',
    persona: 'Tech Lead',
    demeanor: 'neutral',
    difficulty: 'standard',
    question_bank_ids: [],
    panel_personas: [],
  })
  const [panel, setPanel] = useState(false)

  useEffect(() => {
    api.productQuestionBanks().then((r) => setBanks(r.items ?? [])).catch(() => setBanks([]))
  }, [])

  const toggleBank = (id: number) => {
    setValue((current) => ({
      ...current,
      question_bank_ids: current.question_bank_ids.includes(id)
        ? current.question_bank_ids.filter((x) => x !== id)
        : [...current.question_bank_ids, id],
    }))
  }

  const panelPreview = useMemo(
    () => panel
      ? [
          { role: value.persona, demeanor: value.demeanor, domain: value.round_type },
          { role: value.persona === 'Hiring Manager' ? 'Tech Lead' : 'Hiring Manager', demeanor: 'skeptical', domain: 'follow-up' },
          { role: 'Product Partner', demeanor: 'neutral', domain: 'impact' },
        ]
      : [],
    [panel, value.demeanor, value.persona, value.round_type],
  )

  return (
    <div className="mx-auto max-w-3xl space-y-5 py-3" data-testid="practice-setup">
      <div>
        <div className="text-xs font-semibold uppercase tracking-[0.16em] text-accent-green">Practice 3.0</div>
        <h3 className="mt-1 text-xl font-bold text-text-primary">这次想怎么练？</h3>
        <p className="mt-1 text-sm text-text-muted">题目来自 Goal、最近弱项和你选择的 Question Bank；下一问会根据你的回答继续追问。</p>
      </div>

      <section className="grid gap-4 rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4 md:grid-cols-2">
        <label className="space-y-1">
          <span className="text-xs font-semibold text-text-secondary">轮次</span>
          <select value={value.round_type} onChange={(e) => setValue({ ...value, round_type: e.target.value })}
            className="w-full rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary">
            {ROUNDS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>

        <label className="space-y-1">
          <span className="text-xs font-semibold text-text-secondary">主面试官</span>
          <select value={value.persona} onChange={(e) => setValue({ ...value, persona: e.target.value })}
            className="w-full rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary">
            {PERSONAS.map((p) => <option key={p}>{p}</option>)}
          </select>
        </label>

        <label className="space-y-1">
          <span className="text-xs font-semibold text-text-secondary">面试官风格</span>
          <select value={value.demeanor} onChange={(e) => setValue({ ...value, demeanor: e.target.value })}
            className="w-full rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary">
            {DEMEANORS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>

        <label className="space-y-1">
          <span className="text-xs font-semibold text-text-secondary">难度</span>
          <select value={value.difficulty} onChange={(e) => setValue({ ...value, difficulty: e.target.value })}
            className="w-full rounded-xl border border-bg-hover bg-bg-primary px-3 py-2 text-sm text-text-primary">
            {DIFFICULTY.map(([key, label]) => <option key={key} value={key}>{label}</option>)}
          </select>
        </label>

        <label className="space-y-1">
          <span className="text-xs font-semibold text-text-secondary">题数 · {value.rounds}</span>
          <input type="range" min={3} max={10} value={value.rounds}
            onChange={(e) => setValue({ ...value, rounds: Number(e.target.value) })} className="w-full" />
        </label>

        <label className="flex items-center justify-between rounded-xl border border-bg-hover bg-bg-primary px-3 py-2">
          <span>
            <span className="flex items-center gap-1.5 text-xs font-semibold text-text-secondary"><Users className="h-3.5 w-3.5" /> Panel Practice</span>
            <span className="mt-0.5 block text-[11px] text-text-muted">3 个角色轮流追问，不同时抢话</span>
          </span>
          <input type="checkbox" checked={panel} onChange={(e) => setPanel(e.target.checked)} />
        </label>
      </section>

      <section className="rounded-2xl border border-bg-hover/60 bg-bg-secondary p-4">
        <div className="text-xs font-semibold text-text-secondary">题目来源</div>
        <div className="mt-2 flex flex-wrap gap-2">
          <span className="rounded-full border border-status-direct/30 bg-status-direct/8 px-3 py-1 text-xs text-status-direct">✓ Goal Question Graph</span>
          <span className="rounded-full border border-status-direct/30 bg-status-direct/8 px-3 py-1 text-xs text-status-direct">✓ Recent Weakness</span>
          {banks.map((bank) => (
            <button key={bank.id} type="button" onClick={() => toggleBank(bank.id)}
              className={`rounded-full border px-3 py-1 text-xs ${value.question_bank_ids.includes(bank.id) ? 'border-accent-blue/40 bg-accent-blue/10 text-accent-blue' : 'border-bg-hover text-text-muted'}`}>
              {value.question_bank_ids.includes(bank.id) ? '✓ ' : ''}{bank.name}
            </button>
          ))}
          {banks.length === 0 && <span className="text-xs text-text-muted">暂无自定义题库，可在「资料库」添加。</span>}
        </div>
      </section>

      {panel && (
        <section className="rounded-2xl border border-accent-blue/20 bg-accent-blue/5 p-4">
          <div className="text-xs font-semibold text-text-secondary">Panel turn-taking</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {panelPreview.map((p, idx) => <span key={idx} className="rounded-full bg-bg-secondary px-3 py-1 text-xs text-text-secondary">{p.role} · {p.demeanor}</span>)}
          </div>
        </section>
      )}

      <button type="button" disabled={busy} onClick={() => onStart({ ...value, panel_personas: panelPreview })}
        className="inline-flex items-center gap-2 rounded-xl bg-container-primary px-5 py-2.5 text-sm font-semibold text-container-on-primary disabled:opacity-50">
        <Play className="h-4 w-4" /> {busy ? '正在准备第一题…' : '开始这场练习'}
      </button>
    </div>
  )
}
