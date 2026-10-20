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
      <PageHeader title="资料库" subtitle="把「关于你的事实来源」和「只供回答参考的知识」分开保存；简历仍在「我的成竹」，JD 仍属于具体求职目标。" />
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

  const items = data?.items ?? []
  const factsCount = items.filter((m) => m.usage === 'FACTS' || m.usage === 'BOTH').length
  const referenceCount = items.filter((m) => m.usage === 'REFERENCE' || m.usage === 'BOTH').length

  return (
    <div>
      <section aria-label="资料用途说明" className="mb-5 grid gap-3 border-y border-bg-tertiary/70 py-3 sm:grid-cols-[1fr_auto_auto] sm:items-center">
        <div>
          <p className="text-sm font-semibold text-text-primary">项目资料先决定“怎么被使用”</p>
          <p className="mt-0.5 max-w-2xl text-xs leading-5 text-text-secondary">
            作为事实来源的内容可以帮助确认你真实做过什么；技术参考只用于回答知识问题，不会被成竹写成你的个人经历。
          </p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-lg font-semibold tabular-nums text-text-primary">{factsCount}</p>
          <p className="text-[10px] text-text-muted">可作为事实来源</p>
        </div>
        <div className="text-left sm:text-right">
          <p className="text-lg font-semibold tabular-nums text-text-primary">{referenceCount}</p>
          <p className="text-[10px] text-text-muted">可作为技术参考</p>
        </div>
      </section>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.72fr)]">
        <section aria-labelledby="material-list-heading" className="min-w-0">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 id="material-list-heading" className="text-sm font-semibold text-text-primary">已保存资料</h2>
              <p className="mt-0.5 text-[11px] text-text-muted">每份资料的用途可以随时改；版本替换不会偷偷改变它的事实边界。</p>
            </div>
            {items.length ? <span className="text-[11px] tabular-nums text-text-muted">{items.length} 份</span> : null}
          </div>

          <div className="mt-3">
            {loading && !data ? <Loading /> : null}
            {error ? <ErrorState message={error} onRetry={reload} /> : null}
            {data && !items.length ? <EmptyState title="还没有项目资料" body="把项目文档、周报或复盘放进来，并先告诉成竹它是个人事实来源还是技术参考。" /> : null}
            {items.length ? (
              <ul className="divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
                {items.map((m) => {
                  const usageMeta = USAGE.find(([k]) => k === m.usage)
                  return (
                    <li key={m.id} className="py-3">
                      <div className="flex items-start gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="truncate text-sm font-semibold text-text-primary">{m.title}</span>
                            <MaterialStateBadge state={m.lifecycle.state} />
                          </div>
                          <p className="mt-1 text-xs text-text-secondary">{usageMeta?.[1]}</p>
                          <p className="mt-0.5 text-[11px] leading-4 text-text-muted">
                            {usageMeta?.[2]}
                            {m.lifecycle.active_version ? ` · v${m.lifecycle.active_version.version} · ${m.lifecycle.active_version.chars} 字` : ''}
                          </p>
                        </div>
                        <ActionMenu label={`${m.title} 的操作`} actions={[
                          ...(m.lifecycle.actions.includes('view_reason') ? [{ key: 'reason', label: '查看原因', onSelect: () => setReasonFor(reasonFor === m.id ? null : m.id) }] : []),
                          ...(m.lifecycle.actions.includes('retry') ? [{ key: 'retry', label: '重试（重新选择文件）', onSelect: () => replaceWith(m, true) }] : []),
                          { key: 'replace', label: '替换文件', disabled: m.lifecycle.state === 'PROCESSING' || m.lifecycle.state === 'REPLACING', onSelect: () => replaceWith(m) },
                          ...USAGE.filter(([k]) => k !== m.usage).map(([k, l]) => ({ key: `usage-${k}`, label: `改为：${l}`, onSelect: () => void productApi.setMaterialUsage(m.id, k).then(reload) })),
                          { key: 'delete', label: '删除', danger: true, onSelect: () => void productApi.deleteMaterial(m.id).then(reload) },
                        ]} />
                      </div>
                      {m.lifecycle.state === 'FAILED' || reasonFor === m.id ? (
                        <div role="alert" className="mt-2 border-l-2 border-status-risk/45 pl-3 text-[11px] text-text-secondary">
                          原因：{m.lifecycle.error || '未知'}
                          {m.lifecycle.state === 'FAILED' ? (
                            <div className="mt-1.5 flex gap-2">
                              <SecondaryButton onClick={() => replaceWith(m, true)}>重试</SecondaryButton>
                              <SecondaryButton onClick={() => replaceWith(m)}>替换</SecondaryButton>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            ) : null}
          </div>
        </section>

        <aside aria-labelledby="material-add-heading" className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
          <h2 id="material-add-heading" className="text-sm font-semibold text-text-primary">添加一份资料</h2>
          <p className="mt-0.5 text-[11px] leading-5 text-text-muted">先选用途，再上传文件或直接粘贴文本。支持 Markdown、TXT、PDF、DOCX。</p>
          <form className="mt-4 space-y-3" onSubmit={(e) => { e.preventDefault(); void add() }}>
            <Field label="名称">
              <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：WenNian 产品设计文档" />
            </Field>
            <fieldset>
              <legend className="text-xs font-medium text-text-secondary">这份资料主要用来</legend>
              <div className="mt-1.5 divide-y divide-bg-tertiary/60 border-y border-bg-tertiary/70">
                {USAGE.map(([key, label, hint]) => (
                  <label key={key} className="flex items-start gap-2.5 py-2.5 text-xs">
                    <input type="radio" name="usage" value={key} checked={usage === key} onChange={() => setUsage(key)} className="mt-0.5" />
                    <span>
                      <span className="font-medium text-text-primary">{label}</span>
                      <span className="mt-0.5 block leading-4 text-text-muted">{hint}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <Field label="上传文件">
              <input type="file" accept=".md,.txt,.pdf,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="w-full text-xs text-text-secondary" />
            </Field>
            <Field label="或直接粘贴文本">
              <textarea className={`${inputCls} min-h-[92px]`} value={text} onChange={(e) => setText(e.target.value)} placeholder="适合短材料、周报片段或复盘摘要。" />
            </Field>
            {formError ? <p role="alert" className="text-xs text-status-risk">{formError}</p> : null}
            <div className="[&>button]:w-full">
              <PrimaryButton type="submit" disabled={busy || (!file && !text.trim())}>{busy ? '处理中…' : '添加到资料库'}</PrimaryButton>
            </div>
          </form>
        </aside>
      </div>
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
