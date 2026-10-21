import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, CircleDashed, FileText, HelpCircle, XCircle } from 'lucide-react'
import { api, getErrorMessage, type FactItem, type FactsPayload, type ProvenanceStatus } from '@/lib/api'
import { useInterviewStore } from '@/stores/configStore'

// R2 Stage M「事实与来源」：来源状态（Provenance）与用户确认是两条独立的轴，
// 并排显示、分别操作。这里不叫“真相验证”——有来源不等于被认证为真。

const PROVENANCE_META: Record<ProvenanceStatus, { label: string; tone: string; Icon: typeof CheckCircle2 }> = {
  DIRECT_EVIDENCE: { label: '有直接证据', tone: 'text-status-direct', Icon: CheckCircle2 },
  SUPPORTING_EVIDENCE: { label: '有支持材料', tone: 'text-status-supported', Icon: FileText },
  NO_EVIDENCE: { label: '暂无证据', tone: 'text-status-unknown', Icon: CircleDashed },
  CONFLICTING_EVIDENCE: { label: '来源冲突', tone: 'text-status-risk', Icon: AlertTriangle },
}

const USER_META: Record<string, { label: string; tone: string; Icon: typeof CheckCircle2 }> = {
  UNREVIEWED: { label: '未确认', tone: 'text-status-unknown', Icon: HelpCircle },
  USER_CONFIRMED: { label: '用户已确认', tone: 'text-status-direct', Icon: CheckCircle2 },
  USER_DENIED: { label: '用户已否认', tone: 'text-status-risk', Icon: XCircle },
}

type Filter = 'all' | ProvenanceStatus | 'USER_CONFIRMED' | 'USER_DENIED'

function StatusChip({ tone, Icon, label }: { tone: string; Icon: typeof CheckCircle2; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 text-[11px] font-medium ${tone}`}>
      <Icon className="w-3.5 h-3.5" aria-hidden />
      {label}
    </span>
  )
}

function FactRow({ fact, evidence, onChanged }: { fact: FactItem; evidence: FactsPayload['evidence']; onChanged: () => void }) {
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [editing, setEditing] = useState(false)
  const [text, setText] = useState(fact.text)
  const [showSources, setShowSources] = useState(false)
  const [linking, setLinking] = useState(false)
  const [sessions, setSessions] = useState<Array<{ session_id: string; revision: number }> | null>(null)
  const prov = PROVENANCE_META[fact.provenance_status] ?? PROVENANCE_META.NO_EVIDENCE
  const user = USER_META[fact.user_assertion_status] ?? USER_META.UNREVIEWED
  const sources = evidence.filter((e) => fact.source_ids.includes(e.id))

  const run = async (fn: () => Promise<unknown>) => {
    try {
      await fn()
      onChanged()
    } catch (error) {
      pushToast(getErrorMessage(error, '操作失败'), 'error')
    }
  }

  return (
    <li data-testid="fact-row" className="py-3.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <StatusChip {...prov} />
        <StatusChip {...user} />
        <span className="text-[10px] text-text-muted">来源：{fact.source || '—'}</span>
      </div>
      {editing ? (
        <div className="mt-2 flex gap-2">
          <input
            aria-label="修改事实"
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="flex-1 rounded-lg border border-bg-hover bg-bg-primary px-2 py-1 text-sm text-text-primary"
          />
          <button type="button" className="rounded-lg bg-accent-blue px-2.5 py-1 text-xs text-white"
            onClick={() => run(async () => { await api.intelUpdateFact(fact.id, { text }); setEditing(false) })}>保存</button>
          <button type="button" className="rounded-lg border border-bg-hover px-2.5 py-1 text-xs text-text-muted" onClick={() => setEditing(false)}>取消</button>
        </div>
      ) : (
        <p className="mt-1.5 text-sm text-text-primary leading-relaxed">{fact.text}</p>
      )}
      {fact.provenance_status === 'NO_EVIDENCE' && fact.user_assertion_status === 'USER_CONFIRMED' && (
        <p className="mt-1 text-[11px] text-text-muted">说明：当前没有独立资料支持。上场时只能谨慎表述，不会补充指标或细节。</p>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
        <button type="button" className="py-0.5 text-text-secondary hover:text-text-primary" onClick={() => setShowSources((v) => !v)}>
          查看来源（{sources.length}）
        </button>
        <button type="button" className="py-0.5 text-text-secondary hover:text-text-primary" onClick={() => setEditing(true)}>修改</button>
        <button type="button" className="py-0.5 text-text-secondary hover:text-text-primary" onClick={() => setLinking((v) => !v)}>补来源</button>
        <button type="button" disabled={fact.user_assertion_status === 'USER_CONFIRMED'}
          className="rounded-lg border border-status-direct/35 px-2.5 py-1 text-status-direct disabled:opacity-35"
          onClick={() => run(() => api.intelUpdateFact(fact.id, { user_assertion_status: 'USER_CONFIRMED' }))}>用户确认</button>
        <button type="button" disabled={fact.user_assertion_status === 'USER_DENIED'}
          className="rounded-lg border border-status-risk/35 px-2.5 py-1 text-status-risk disabled:opacity-35"
          onClick={() => run(() => api.intelUpdateFact(fact.id, { user_assertion_status: 'USER_DENIED' }))}>用户否认</button>
        <button type="button" className="py-0.5 text-text-secondary hover:text-text-primary"
          onClick={() => api.intelFactSessions(fact.id).then(setSessions).catch(() => setSessions([]))}>在哪些场次使用</button>
        {fact.user_assertion_status !== 'USER_CONFIRMED' && fact.source !== 'resume' && (
          <button type="button" className="py-0.5 text-text-secondary hover:text-text-primary"
            onClick={() => run(() => api.intelDeleteFact(fact.id))}>删除草稿</button>
        )}
      </div>
      {showSources && (
        <ul className="mt-2 space-y-1 rounded-lg bg-bg-tertiary/30 p-2 text-[11px] text-text-secondary">
          {sources.length ? sources.map((s) => <li key={s.id}>· [{s.source}] {s.text}</li>) : <li>暂无关联来源。</li>}
        </ul>
      )}
      {linking && (
        <div className="mt-2 max-h-40 overflow-y-auto rounded-lg bg-bg-tertiary/30 p-2 text-[11px]">
          <p className="mb-1 text-text-muted">选择一条已有资料作为这条事实的来源：</p>
          {evidence.slice(0, 40).map((e) => (
            <button key={e.id} type="button" className="block w-full truncate text-left text-text-secondary hover:text-text-primary"
              onClick={() => run(async () => { await api.intelUpdateFact(fact.id, { source_ids: [...fact.source_ids, e.id] }); setLinking(false) })}>
              + [{e.source}] {e.text}
            </button>
          ))}
        </div>
      )}
      {sessions && (
        <p className="mt-2 text-[11px] text-text-muted">
          {sessions.length ? `已进入 ${sessions.length} 份 Interview Pack：` + sessions.map((s) => `${s.session_id}·rev${s.revision}`).join('，') : '尚未进入任何 Interview Pack。'}
        </p>
      )}
    </li>
  )
}

export default function FactsSources() {
  const [data, setData] = useState<FactsPayload | null>(null)
  const [filter, setFilter] = useState<Filter>('all')
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api.intelFacts().then((res) => { setData(res); setError(null) }).catch((e) => setError(getErrorMessage(e, '加载失败')))
  }, [])
  useEffect(() => { load() }, [load])

  const facts = useMemo(() => {
    const all = data?.facts ?? []
    if (filter === 'all') return all
    if (filter === 'USER_CONFIRMED' || filter === 'USER_DENIED') return all.filter((f) => f.user_assertion_status === filter)
    return all.filter((f) => f.provenance_status === filter)
  }, [data, filter])

  if (error) return <p className="p-4 text-sm text-status-risk">{error}</p>
  if (!data) return <p className="p-4 text-sm text-text-muted">加载中…</p>
  if (!data.facts.length) {
    return (
      <div className="p-6 text-sm text-text-muted" data-testid="facts-empty">
        还没有事实。上传简历后会自动抽取；也可以在复盘里确认本场口述过的内容。
      </div>
    )
  }

  const filters: Array<[Filter, string]> = [
    ['all', '全部'],
    ['DIRECT_EVIDENCE', '有直接证据'],
    ['SUPPORTING_EVIDENCE', '有支持材料'],
    ['NO_EVIDENCE', '暂无证据'],
    ['CONFLICTING_EVIDENCE', '来源冲突'],
    ['USER_CONFIRMED', '用户已确认'],
    ['USER_DENIED', '用户已否认'],
  ]

  const allFacts = data.facts
  const directCount = allFacts.filter((f) => f.provenance_status === 'DIRECT_EVIDENCE').length
  const confirmedCount = allFacts.filter((f) => f.user_assertion_status === 'USER_CONFIRMED').length
  const attentionCount = allFacts.filter((f) =>
    f.provenance_status === 'CONFLICTING_EVIDENCE'
    || f.provenance_status === 'NO_EVIDENCE'
    || f.user_assertion_status === 'UNREVIEWED'
  ).length

  const orderedFacts = [...facts].sort((a, b) => {
    const rank = (fact: FactItem) => {
      if (fact.provenance_status === 'CONFLICTING_EVIDENCE') return 0
      if (fact.provenance_status === 'NO_EVIDENCE') return 1
      if (fact.user_assertion_status === 'UNREVIEWED') return 2
      if (fact.provenance_status === 'SUPPORTING_EVIDENCE') return 3
      return 4
    }
    return rank(a) - rank(b)
  })

  return (
    <div className="p-4" data-testid="facts-sources">
      <section aria-label="事实边界摘要" className="grid gap-3 border-y border-bg-tertiary/70 py-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-center">
        <div>
          <p className="text-sm font-semibold text-text-primary">先处理会影响上场表述的事实边界</p>
          <p className="mt-0.5 max-w-2xl text-xs leading-5 text-text-secondary">
            “来源状态”回答资料是否支持这句话；“用户确认”记录你本人是否认可。两条轴独立，成竹不会把“你确认了”误写成“已有独立证据”。
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-lg font-semibold tabular-nums text-text-primary">{attentionCount}</p>
          <p className="text-[10px] text-text-muted">需要关注</p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-lg font-semibold tabular-nums text-text-primary">{directCount}</p>
          <p className="text-[10px] text-text-muted">直接证据</p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-lg font-semibold tabular-nums text-text-primary">{confirmedCount}</p>
          <p className="text-[10px] text-text-muted">你已确认</p>
        </div>
      </section>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">{filter === 'all' ? '全部个人事实' : filters.find(([key]) => key === filter)?.[1]}</h3>
          <p className="mt-0.5 text-[11px] text-text-muted">默认把冲突、暂无证据和未确认内容排在前面。</p>
        </div>
        <div className="flex flex-wrap gap-1" role="group" aria-label="筛选">
          {filters.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={filter === key} onClick={() => setFilter(key)}
              className={`rounded-lg border px-2.5 py-1 text-[11px] font-medium ${filter === key ? 'border-accent-blue/45 bg-bg-tertiary/45 text-text-primary' : 'border-transparent text-text-muted hover:border-bg-hover hover:text-text-primary'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <ul className="mt-3 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
        {orderedFacts.map((fact) => (
          <FactRow key={fact.id} fact={fact} evidence={data.evidence} onChanged={load} />
        ))}
      </ul>
    </div>
  )}
