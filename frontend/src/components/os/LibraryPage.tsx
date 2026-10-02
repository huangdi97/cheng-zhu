/**
 * 资料库 (canonical §6): Project Materials · Knowledge Bases · Quick Notes · Question Banks.
 * Resume lives in 我的成竹; JD lives in its Goal.
 */
import { useEffect, useState } from 'react'
import { navigate, paths } from '@/lib/router'
import { productApi, type Material, type QuestionBank } from '@/lib/productApi'
import { useKbStore } from '@/stores/kbStore'
import KbStatusHeader from '@/components/kb/KbStatusHeader'
import QuickNotesPanel from './QuickNotesPanel'
import { MaterialStateBadge } from './MaterialStateBadge'
import { ActionMenu, EmptyState, ErrorState, Field, inputCls, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, Section, StatusBadge, Tabs, useAsync } from './ui'

type LibTab = 'materials' | 'knowledge' | 'notes' | 'banks'
const LIB_TABS: LibTab[] = ['materials', 'knowledge', 'notes', 'banks']

const USAGE: Array<[string, string, string]> = [
  ['FACTS', '项目事实与来源', '用来确认你做过什么；会进入事实与来源'],
  ['REFERENCE', '技术参考', '只作为知识，不会被当成你的经历'],
  ['BOTH', '两者', '既是你的项目材料，也包含技术参考'],
]

export default function LibraryPage({ tab }: { tab: string }) {
  const current = (LIB_TABS as string[]).includes(tab) ? (tab as LibTab) : 'materials'
  return (
    <Page testId="library-page" wide>
      <PageHeader title="资料库" subtitle="简历在「我的成竹」，JD 在各自的求职目标里。" />
      <Tabs<LibTab> label="资料库" value={current} onChange={(t) => navigate(paths.library(t), { replace: true })}
        tabs={[['materials', '项目资料'], ['knowledge', '知识库'], ['notes', '速记'], ['banks', '题库']]} />
      <div className="pt-3">
        {current === 'materials' ? <Materials /> : null}
        {current === 'knowledge' ? <Knowledge /> : null}
        {current === 'notes' ? <QuickNotesPanel context="library" /> : null}
        {current === 'banks' ? <Banks /> : null}
      </div>
    </Page>
  )
}

function Materials() {
  const { data, error, loading, reload } = useAsync(() => productApi.materials('PROJECT'), [])
  const [title, setTitle] = useState('')
  const [usage, setUsage] = useState('FACTS')
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [reasonFor, setReasonFor] = useState<string | null>(null)
  const pending = (data?.items ?? []).some((m) => m.lifecycle.state === 'PROCESSING' || m.lifecycle.state === 'REPLACING')
  useEffect(() => {
    if (!pending) return
    const t = setInterval(() => void reload(), 1500)
    return () => clearInterval(t)
  }, [pending, reload])

  const add = async () => {
    setBusy(true)
    setFormError(null)
    try {
      await productApi.createMaterial({ title: title || file?.name || '', kind: 'PROJECT', usage, text, file })
      setTitle(''); setText(''); setFile(null)
      await reload()
    } catch (e) {
      setFormError(e instanceof Error ? e.message : '上传失败')
    } finally {
      setBusy(false)
    }
  }

  const replaceWith = (m: Material, retry = false) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.md,.txt,.pdf,.docx'
    input.onchange = () => {
      const f = input.files?.[0]
      if (!f) return
      const call = retry ? productApi.retryMaterial(m.id, { file: f }) : productApi.replaceMaterial(m.id, { file: f })
      void call.then(() => reload()).catch((e) => setFormError(e instanceof Error ? e.message : '操作失败'))
    }
    input.click()
  }

  return (
    <div className="grid gap-x-6 lg:grid-cols-[1fr_1.2fr]">
      <Section title="添加项目资料">
        <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); void add() }}>
          <Field label="名称"><input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如 WenNian 设计文档" /></Field>
          <fieldset>
            <legend className="text-xs font-medium text-text-secondary">主要用于</legend>
            <div className="mt-1 space-y-1">
              {USAGE.map(([key, label, hint]) => (
                <label key={key} className="flex items-start gap-2 text-xs">
                  <input type="radio" name="usage" value={key} checked={usage === key} onChange={() => setUsage(key)} className="mt-0.5" />
                  <span><span className="font-medium text-text-primary">{label}</span><span className="block text-[11px] text-text-muted">{hint}</span></span>
                </label>
              ))}
            </div>
          </fieldset>
          <Field label="文件（.md / .txt / .pdf / .docx）"><input type="file" accept=".md,.txt,.pdf,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-xs" /></Field>
          <Field label="或直接粘贴文本"><textarea className={`${inputCls} min-h-[80px]`} value={text} onChange={(e) => setText(e.target.value)} /></Field>
          {formError ? <p role="alert" className="text-xs text-status-risk">{formError}</p> : null}
          <PrimaryButton type="submit" disabled={busy || (!file && !text.trim())}>{busy ? '上传中…' : '添加'}</PrimaryButton>
        </form>
      </Section>
      <Section title="项目资料">
        {loading && !data ? <Loading /> : null}
        {error ? <ErrorState message={error} onRetry={reload} /> : null}
        {data && !data.items.length ? <EmptyState title="还没有项目资料" body="上传设计文档、周报或复盘，成竹会用它们确认你的事实边界。" /> : null}
        <ul className="space-y-2">
          {(data?.items ?? []).map((m) => (
            <li key={m.id} className="rounded-xl border border-bg-hover/50 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-text-primary">{m.title}</span>
                <MaterialStateBadge state={m.lifecycle.state} />
                <ActionMenu label={`${m.title} 的操作`} actions={[
                  ...(m.lifecycle.actions.includes('view_reason') ? [{ key: 'reason', label: '查看原因', onSelect: () => setReasonFor(reasonFor === m.id ? null : m.id) }] : []),
                  ...(m.lifecycle.actions.includes('retry') ? [{ key: 'retry', label: '重试（重新选择文件）', onSelect: () => replaceWith(m, true) }] : []),
                  { key: 'replace', label: '替换文件', disabled: m.lifecycle.state === 'PROCESSING' || m.lifecycle.state === 'REPLACING', onSelect: () => replaceWith(m) },
                  ...USAGE.filter(([k]) => k !== m.usage).map(([k, l]) => ({ key: `usage-${k}`, label: `改为：${l}`, onSelect: () => void productApi.setMaterialUsage(m.id, k).then(reload) })),
                  { key: 'delete', label: '删除', danger: true, onSelect: () => void productApi.deleteMaterial(m.id).then(reload) },
                ]} />
              </div>
              <div className="text-[11px] text-text-muted">
                {USAGE.find(([k]) => k === m.usage)?.[1]}
                {m.lifecycle.active_version ? ` · v${m.lifecycle.active_version.version} · ${m.lifecycle.active_version.chars} 字` : ''}
              </div>
              {m.lifecycle.state === 'FAILED' || reasonFor === m.id ? (
                <div role="alert" className="mt-1.5 rounded-lg border border-status-risk/25 bg-status-risk/5 p-2 text-[11px] text-text-secondary">
                  原因：{m.lifecycle.error || '未知'}
                  {m.lifecycle.state === 'FAILED' ? (
                    <div className="mt-1 flex gap-2">
                      <SecondaryButton onClick={() => replaceWith(m, true)}>重试</SecondaryButton>
                      <SecondaryButton onClick={() => replaceWith(m)}>替换</SecondaryButton>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  )
}

function Knowledge() {
  const toggleDrawer = useKbStore((s) => s.toggleDrawer)
  return (
    <div className="space-y-3">
      <p className="text-xs text-text-secondary">知识库是技术参考：上场时可以被检索引用，但<strong>不会</strong>被当作你本人的经历或证据。</p>
      <div className="rounded-2xl border border-bg-hover/60 overflow-hidden"><KbStatusHeader /></div>
      <PrimaryButton onClick={toggleDrawer}>管理知识库文件</PrimaryButton>
    </div>
  )
}

function Banks() {
  const { data, error, loading, reload } = useAsync(() => productApi.banks(), [])
  const [selected, setSelected] = useState<QuestionBank | null>(null)
  const [name, setName] = useState('')
  if (loading && !data) return <Loading />
  if (error) return <ErrorState message={error} onRetry={reload} />
  const banks = data?.items ?? []
  return (
    <div className="grid gap-x-6 lg:grid-cols-[1fr_1.4fr]">
      <Section title="题库">
        <ul className="space-y-1.5">
          {banks.map((b) => (
            <li key={b.id}>
              <button type="button" onClick={() => setSelected(b)} aria-pressed={selected?.id === b.id}
                className={`flex w-full items-center gap-2 rounded-xl border px-3 py-2 text-left ${selected?.id === b.id ? 'border-accent-blue/50 bg-accent-blue/5' : 'border-bg-hover/50 hover:bg-bg-hover/40'}`}>
                <span className="min-w-0 flex-1 truncate text-sm text-text-primary">{b.name}</span>
                <StatusBadge tone={b.builtin ? 'info' : 'muted'}>{b.builtin ? '内置 · 只读' : b.source_type === 'PREVIOUS_SESSION' ? '历史场次' : '我的'}</StatusBadge>
                <span className="text-[11px] text-text-muted">{b.item_count}</span>
              </button>
            </li>
          ))}
        </ul>
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); void productApi.createBank({ name }).then(() => { setName(''); void reload() }) }}>
          <input aria-label="新题库名称" className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="新题库名称" />
          <PrimaryButton type="submit" disabled={!name.trim()}>新建</PrimaryButton>
        </form>
      </Section>
      <Section title={selected ? selected.name : '题目'}>
        {selected ? <BankItems bank={selected} onChanged={reload} onDeleted={() => { setSelected(null); void reload() }} /> : <EmptyState title="选择左侧的题库查看题目" />}
      </Section>
    </div>
  )
}

function BankItems({ bank, onChanged, onDeleted }: { bank: QuestionBank; onChanged: () => void; onDeleted: () => void }) {
  const { data, reload } = useAsync(() => productApi.bankItems(bank.id), [bank.id])
  const [text, setText] = useState('')
  const [bulk, setBulk] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const refresh = () => { void reload(); onChanged() }
  return (
    <div className="space-y-3">
      {bank.builtin ? <p className="text-[11px] text-text-muted">成竹通用题：按岗位整理的常见问题，不代表任何公司的真实面经。</p> : null}
      <ul className="space-y-1.5">
        {(data?.items ?? []).map((item) => (
          <li key={item.id} className="flex items-start gap-2 rounded-xl border border-bg-hover/50 px-3 py-2">
            <span className="min-w-0 flex-1 text-xs text-text-primary">{item.text}
              <span className="block text-[10px] text-text-muted">{item.label}{item.source_url ? ` · ${item.source_url}` : ''} · {item.difficulty === 'WARMUP' ? '热身' : item.difficulty === 'PRESSURE' ? '压力' : '标准'}</span>
            </span>
            {!bank.builtin ? <button type="button" aria-label="删除这道题" className="text-[11px] text-text-muted hover:text-status-risk" onClick={() => void productApi.deleteBankItem(item.id).then(refresh)}>删除</button> : null}
          </li>
        ))}
      </ul>
      {!bank.builtin ? (
        <>
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); void productApi.addBankItem(bank.id, { text }).then(() => { setText(''); refresh() }).catch((x) => setErr(String(x))) }}>
            <input aria-label="新题目" className={inputCls} value={text} onChange={(e) => setText(e.target.value)} placeholder="添加一道题" />
            <PrimaryButton type="submit" disabled={!text.trim()}>添加</PrimaryButton>
          </form>
          <details className="text-xs">
            <summary className="cursor-pointer text-text-secondary">批量导入（每行一题）</summary>
            <div className="mt-2 space-y-1.5">
              <textarea aria-label="批量导入题目" className={`${inputCls} min-h-[80px]`} value={bulk} onChange={(e) => setBulk(e.target.value)} />
              <input aria-label="来源链接（可选）" className={inputCls} value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="来源链接（有来源才会标为真实面经）" />
              <SecondaryButton disabled={!bulk.trim()} onClick={() => void productApi.importBankItems(bank.id, bulk.split('\n'), sourceUrl).then(() => { setBulk(''); refresh() }).catch((x) => setErr(String(x)))}>导入</SecondaryButton>
            </div>
          </details>
          {err ? <p role="alert" className="text-xs text-status-risk">{err}</p> : null}
          <SecondaryButton onClick={() => void productApi.deleteBank(bank.id).then(onDeleted)}>删除这个题库</SecondaryButton>
        </>
      ) : null}
    </div>
  )
}
