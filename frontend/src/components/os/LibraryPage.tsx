/**
 * 资料库 (canonical §6): Project Materials · Knowledge Bases · Quick Notes · Question Banks.
 * Resume lives in 我的成竹; JD lives in its Goal.
 */
import { useEffect, useState } from 'react'
import { navigate, paths } from '@/lib/router'
import { productApi, type Material, type QuestionBank } from '@/lib/productApi'
import { useKbStore } from '@/stores/kbStore'
import QuickNotesPanel from './QuickNotesPanel'
import { MaterialStateBadge } from './MaterialStateBadge'
import { ActionMenu, EmptyState, ErrorState, Field, inputCls, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, Tabs, useAsync } from './ui'

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
              <div className="flex min-w-0 items-center gap-2">
                <label className="btn-subtle inline-flex min-h-[32px] flex-shrink-0 cursor-pointer items-center rounded-lg px-3 py-1.5 text-xs font-medium">
                  选择文件
                  <input aria-label="选择项目资料文件" type="file" accept=".md,.txt,.pdf,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="sr-only" />
                </label>
                <span className="min-w-0 truncate text-[11px] text-text-muted">{file?.name || '未选择文件'}</span>
              </div>
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
  const status = useKbStore((s) => s.status)
  const enabled = status?.enabled ?? false
  const docs = status?.total_docs ?? 0

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1.15fr)_minmax(300px,0.7fr)]">
      <section aria-labelledby="knowledge-purpose-heading">
        <p className="text-[11px] font-medium text-text-muted">REFERENCE ONLY</p>
        <h2 id="knowledge-purpose-heading" className="mt-1 text-base font-semibold text-text-primary">只作为技术参考，不作为你的经历</h2>
        <p className="mt-1 max-w-2xl text-xs leading-5 text-text-secondary">
          上场和练习时，成竹可以从这里检索概念、框架和技术资料；它们不会被写成“你做过”“你负责过”的个人事实。
        </p>

        <div className="mt-4 grid grid-cols-2 divide-x divide-bg-tertiary/70 border-y border-bg-tertiary/70 py-3">
          <div className="pr-4">
            <p className="text-lg font-semibold text-text-primary">{enabled ? '已启用' : '未启用'}</p>
            <p className="mt-0.5 text-[10px] text-text-muted">知识检索</p>
          </div>
          <div className="pl-4">
            <p className="text-lg font-semibold tabular-nums text-text-primary">{docs}</p>
            <p className="mt-0.5 text-[10px] text-text-muted">参考文档</p>
          </div>
        </div>

        <div className="mt-4">
          <PrimaryButton onClick={toggleDrawer}>查看和管理参考文档</PrimaryButton>
        </div>
      </section>

      <aside className="lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
        <h3 className="text-sm font-semibold text-text-primary">什么时候会用到</h3>
        <div className="mt-3 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
          <div className="py-2.5">
            <p className="text-xs font-medium text-text-primary">回答技术问题</p>
            <p className="mt-0.5 text-[11px] leading-4 text-text-muted">补概念、方法、框架和术语背景。</p>
          </div>
          <div className="py-2.5">
            <p className="text-xs font-medium text-text-primary">辅助追问</p>
            <p className="mt-0.5 text-[11px] leading-4 text-text-muted">给出知识参考，但仍优先使用你自己的项目事实。</p>
          </div>
          <div className="py-2.5">
            <p className="text-xs font-medium text-text-primary">不会自动变成个人证据</p>
            <p className="mt-0.5 text-[11px] leading-4 text-text-muted">技术文档、博客和论文不会因为被检索到就进入“我的成竹”。</p>
          </div>
        </div>
      </aside>
    </div>
  )
}

function Banks() {
  const { data, error, loading, reload } = useAsync(() => productApi.banks(), [])
  const [selected, setSelected] = useState<QuestionBank | null>(null)
  const [name, setName] = useState('')
  const banks = data?.items ?? []

  useEffect(() => {
    if (!selected && banks.length) setSelected(banks[0])
    if (selected && !banks.some((b) => b.id === selected.id)) setSelected(banks[0] ?? null)
  }, [banks, selected])

  if (loading && !data) return <Loading />
  if (error) return <ErrorState message={error} onRetry={reload} />

  return (
    <div>
      <section aria-label="题库用途" className="mb-5 border-y border-bg-tertiary/70 py-3">
        <p className="text-sm font-semibold text-text-primary">题库是练习来源，不是“答案库”</p>
        <p className="mt-0.5 max-w-3xl text-xs leading-5 text-text-secondary">
          内置题用于常见岗位练习；历史场次题只表示“曾经被问过”；只有带明确来源的内容才可以标成真实面经。题库不会替你生成个人经历。
        </p>
      </section>

      <div className="grid gap-8 lg:grid-cols-[minmax(260px,0.72fr)_minmax(0,1.28fr)]">
        <aside aria-labelledby="bank-list-heading">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h2 id="bank-list-heading" className="text-sm font-semibold text-text-primary">练习来源</h2>
              <p className="mt-0.5 text-[11px] text-text-muted">先选来源，再看具体问题。</p>
            </div>
            <span className="text-[11px] tabular-nums text-text-muted">{banks.length} 个</span>
          </div>

          <ul className="mt-3 divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
            {banks.map((b) => (
              <li key={b.id}>
                <button type="button" onClick={() => setSelected(b)} aria-pressed={selected?.id === b.id}
                  className={`flex w-full items-start gap-3 py-3 text-left ${selected?.id === b.id ? 'text-text-primary' : 'text-text-secondary hover:text-text-primary'}`}>
                  <span className={`mt-1 h-2 w-2 flex-shrink-0 rounded-full ${selected?.id === b.id ? 'bg-accent-blue' : 'bg-bg-hover'}`} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{b.name}</span>
                    <span className="mt-0.5 block text-[10px] text-text-muted">
                      {b.builtin ? '成竹内置 · 只读' : b.source_type === 'PREVIOUS_SESSION' ? '历史场次' : '我的题库'} · {b.item_count} 题
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>

          <details className="mt-4 text-xs">
            <summary className="cursor-pointer font-medium text-text-secondary">新建自己的题库</summary>
            <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); void productApi.createBank({ name }).then(() => { setName(''); void reload() }) }}>
              <input aria-label="新题库名称" className={inputCls} value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：AI 产品 Case" />
              <PrimaryButton type="submit" disabled={!name.trim()}>新建</PrimaryButton>
            </form>
          </details>
        </aside>

        <section aria-labelledby="bank-items-heading" className="min-w-0 lg:border-l lg:border-bg-tertiary/70 lg:pl-7">
          <div className="mb-3">
            <h2 id="bank-items-heading" className="text-sm font-semibold text-text-primary">{selected ? selected.name : '选择一个练习来源'}</h2>
            {selected ? (
              <p className="mt-0.5 text-[11px] text-text-muted">
                {selected.builtin ? '常见岗位问题，只读；不代表任何公司的真实面经。' : selected.source_type === 'PREVIOUS_SESSION' ? '来自历史场次，用于复练曾经被问过的问题。' : '你自己维护的练习问题。'}
              </p>
            ) : null}
          </div>
          {selected ? <BankItems bank={selected} onChanged={reload} onDeleted={() => { setSelected(null); void reload() }} /> : <EmptyState title="还没有可用题库" body="可以新建一个自己的练习来源。" />}
        </section>
      </div>
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
  const items = data?.items ?? []

  return (
    <div>
      {items.length ? (
        <ol className="divide-y divide-bg-tertiary/70 border-y border-bg-tertiary/70">
          {items.map((item, index) => (
            <li key={item.id} className="flex items-start gap-3 py-3">
              <span className="w-5 flex-shrink-0 pt-0.5 text-[10px] tabular-nums text-text-muted">{String(index + 1).padStart(2, '0')}</span>
              <div className="min-w-0 flex-1">
                <p className="text-xs leading-5 text-text-primary">{item.text}</p>
                <p className="mt-0.5 text-[10px] text-text-muted">
                  {item.label}{item.source_url ? ' · 有来源' : ''} · {item.difficulty === 'WARMUP' ? '热身' : item.difficulty === 'PRESSURE' ? '压力' : '标准'}
                </p>
              </div>
              {!bank.builtin ? (
                <button type="button" aria-label="删除这道题" className="flex-shrink-0 text-[11px] text-text-muted hover:text-status-risk"
                  onClick={() => void productApi.deleteBankItem(item.id).then(refresh)}>删除</button>
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState title="这个来源还没有问题" body={bank.builtin ? '内置题库暂时为空。' : '先添加一道你确实想练的问题。'} />
      )}

      {!bank.builtin ? (
        <div className="mt-5 border-t border-bg-tertiary/70 pt-4">
          <h3 className="text-xs font-semibold text-text-primary">补充问题</h3>
          <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); void productApi.addBankItem(bank.id, { text }).then(() => { setText(''); refresh() }).catch((x) => setErr(String(x))) }}>
            <input aria-label="新题目" className={inputCls} value={text} onChange={(e) => setText(e.target.value)} placeholder="添加一道题" />
            <PrimaryButton type="submit" disabled={!text.trim()}>添加</PrimaryButton>
          </form>

          <details className="mt-3 text-xs">
            <summary className="cursor-pointer text-text-secondary">批量导入更多问题</summary>
            <div className="mt-2 space-y-2">
              <textarea aria-label="批量导入题目" className={`${inputCls} min-h-[88px]`} value={bulk} onChange={(e) => setBulk(e.target.value)} placeholder="每行一道题" />
              <input aria-label="来源链接（可选）" className={inputCls} value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} placeholder="来源链接；有来源才会标为真实面经" />
              <SecondaryButton disabled={!bulk.trim()} onClick={() => void productApi.importBankItems(bank.id, bulk.split('\n'), sourceUrl).then(() => { setBulk(''); refresh() }).catch((x) => setErr(String(x)))}>导入</SecondaryButton>
            </div>
          </details>

          {err ? <p role="alert" className="mt-2 text-xs text-status-risk">{err}</p> : null}
          <div className="mt-4">
            <button type="button" className="text-[11px] text-text-muted hover:text-status-risk" onClick={() => void productApi.deleteBank(bank.id).then(onDeleted)}>删除这个题库</button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
