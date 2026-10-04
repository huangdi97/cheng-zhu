/**
 * Settings 3.0 (canonical §19): ten groups, search, and per-value layering
 * Global Default → Goal Default → This Session Override (session overrides
 * are set in Preflight and only last for that session).
 */
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { Search } from 'lucide-react'
import { navigate, paths } from '@/lib/router'
import { api } from '@/lib/api'
import { updateConfigAndRefresh } from '@/lib/configSync'
import { productApi, type SettingLayer } from '@/lib/productApi'
import { useInterviewStore } from '@/stores/configStore'
import { useKbStore } from '@/stores/kbStore'
import { SettingsSearchContext } from '@/components/settings/shared'
import { CATALOG, GROUP_LABEL_ZH, searchCatalog, SETTINGS_GROUPS, type SettingsGroup } from './settingsCatalog'
import { ErrorState, Field, inputCls, Loading, Page, PageHeader, PrimaryButton, SecondaryButton, Section, StatusBadge, useAsync } from './ui'
import OverlayPrefs from './OverlayPrefs'

const PreferencesTab = lazy(() => import('@/components/settings/PreferencesTab'))
const SpeechTab = lazy(() => import('@/components/settings/SpeechTab'))
const ModelsTab = lazy(() => import('@/components/settings/ModelsTab'))
const GlobalShortcutsEditor = lazy(() => import('@/components/settings/GlobalShortcutsEditor'))
const PolicyPrivacySection = lazy(() => import('@/components/settings/PolicyPrivacySection'))

type Opt = [string | boolean | number, string]
const LAYER_OPTIONS: Record<string, Opt[]> = {
  answer_language: [['中文', '中文'], ['English', 'English'], ['FOLLOW_INTERVIEW', '跟随面试语言']],
  whisper_language: [['auto', '自动识别'], ['zh', '中文'], ['en', 'English']],
  language: [['Python', 'Python'], ['Java', 'Java'], ['C++', 'C++'], ['JavaScript', 'JavaScript'], ['TypeScript', 'TypeScript'], ['Go', 'Go'], ['SQL', 'SQL']],
  technical_term_policy: [['AUTO', '自动（沿用默认规则）'], ['KEEP_ENGLISH', '保留英文'], ['TRANSLATE', '译为回答语言'], ['BILINGUAL', '中英并列']],
  ai_policy_mode: [['AI_FORBIDDEN', '禁止 AI'], ['AI_LIMITED', '有限 AI'], ['AI_ALLOWED', '允许 AI'], ['AI_EXPECTED', '要求使用 AI']],
  human_assistance_policy: [['HUMAN_FORBIDDEN', '禁止真人辅助'], ['HUMAN_PRACTICE_ONLY', '仅练习'], ['HUMAN_ALLOWED', '允许']],
  share_privacy_mode: [['OFF', '关闭（默认）'], ['PRIVATE_OVERLAY', '私密浮窗']],
  speech_adoption_analytics_live: [[false, '关闭（默认）'], [true, '开启']],
  proactive_guidance_enabled: [[true, '开启'], [false, '关闭']],
  kb_enabled: [[true, '开启'], [false, '关闭']],
}

function encode(v: unknown): string {
  return JSON.stringify(v)
}

/** One layered value: global default + optional Goal default, with origin. */
function LayeredRow({ k, layer, goalId, onChanged }: { k: string; layer: SettingLayer; goalId: string; onChanged: () => void }) {
  const options = LAYER_OPTIONS[k]
  if (!options) return null
  const setGlobal = (raw: string) => void updateConfigAndRefresh({ [k]: JSON.parse(raw) }).then(onChanged)
  const setGoal = (raw: string) => {
    if (!goalId) return
    const p = raw === '' ? productApi.clearSettingLayer('GOAL', goalId, k) : productApi.setSettingLayer('GOAL', goalId, k, JSON.parse(raw))
    void p.then(onChanged)
  }
  return (
    <div className="grid gap-2 border-b border-bg-tertiary/60 py-2.5 sm:grid-cols-[1fr_1fr_1fr] sm:items-end" data-setting={k}>
      <div>
        <div className="text-sm text-text-primary">{layer.label}</div>
        <StatusBadge tone={layer.origin === 'GOAL' ? 'info' : 'muted'}>当前：{layer.origin_label}</StatusBadge>
      </div>
      <Field label="全局默认">
        <select className={inputCls} value={encode(layer.global_value)} onChange={(e) => setGlobal(e.target.value)}>
          {options.map(([v, l]) => <option key={String(v)} value={encode(v)}>{l}</option>)}
        </select>
      </Field>
      <Field label={goalId ? 'Goal 默认' : 'Goal 默认（先在上方选择目标）'}>
        <select className={inputCls} disabled={!goalId} value={layer.goal_value === null || layer.goal_value === undefined ? '' : encode(layer.goal_value)} onChange={(e) => setGoal(e.target.value)}>
          <option value="">沿用全局</option>
          {options.map(([v, l]) => <option key={String(v)} value={encode(v)}>{l}</option>)}
        </select>
      </Field>
    </div>
  )
}

function LayerGroup({ keys, goalId, extra }: { keys: string[]; goalId: string; extra?: React.ReactNode }) {
  const { data, error, reload } = useAsync(() => productApi.settingLayers(goalId), [goalId])
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (!data) return <Loading />
  return (
    <div>
      {keys.map((k) => data.items[k] ? <LayeredRow key={k} k={k} layer={data.items[k]} goalId={goalId} onChanged={reload} /> : null)}
      <p className="pt-2 text-[11px] text-text-muted">「本场覆盖」在上场前的 Preflight 里设置，只对那一场生效，不会改变这里的默认值。</p>
      {extra}
    </div>
  )
}

function UiLanguageRow() {
  const config = useInterviewStore((s) => s.config)
  return (
    <div className="grid gap-2 border-b border-bg-tertiary/60 py-2.5 sm:grid-cols-[1fr_2fr] sm:items-end">
      <div className="text-sm text-text-primary">界面语言<span className="block text-[11px] text-text-muted">只影响界面文字，不影响识别和回答</span></div>
      <select aria-label="界面语言" className={inputCls} value={config?.ui_language ?? 'zh-CN'} onChange={(e) => void updateConfigAndRefresh({ ui_language: e.target.value })}>
        <option value="zh-CN">简体中文</option>
        <option value="en-US">English</option>
      </select>
    </div>
  )
}

function ToggleRow({ label, hint, checked, onChange }: { label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="flex items-start justify-between gap-3 border-b border-bg-tertiary/60 py-2.5">
      <span className="text-sm text-text-primary">{label}{hint ? <span className="block text-[11px] text-text-muted">{hint}</span> : null}</span>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="mt-1" />
    </label>
  )
}

function PrivacyGroup({ goalId }: { goalId: string }) {
  const config = useInterviewStore((s) => s.config)
  const [cleared, setCleared] = useState<number | null>(null)
  return (
    <div className="space-y-2">
      <LayerGroup keys={['share_privacy_mode', 'speech_adoption_analytics_live']} goalId={goalId} />
      <p className="text-[11px] text-text-muted">共享隐私：减少成竹私人内容在受支持的屏幕共享/录屏路径中意外出现，不是安全或不可检测保证。</p>
      <ToggleRow label="练习的本地表达分析" hint="语速、结论时间、填充词；只在本机计算，不上传音频。" checked={config?.practice_delivery_analytics_enabled !== false}
        onChange={(v) => void updateConfigAndRefresh({ practice_delivery_analytics_enabled: v })} />
      <ToggleRow label="远程遥测" hint="默认关闭。本地产品分析始终只保存在这台电脑上。" checked={!!config?.remote_telemetry_opt_in}
        onChange={(v) => void updateConfigAndRefresh({ remote_telemetry_opt_in: v })} />
      <div className="flex items-center gap-2 pt-2">
        <SecondaryButton onClick={() => navigate(paths.settings('diagnostics'))}>查看本地产品分析</SecondaryButton>
        <SecondaryButton onClick={() => { if (window.confirm('清空本机记录的产品使用事件？')) void productApi.clearEvents().then((r) => setCleared(r.deleted)) }}>清空本地分析记录</SecondaryButton>
        {cleared !== null ? <span role="status" className="text-xs text-status-direct">已清空 {cleared} 条</span> : null}
      </div>
      <Suspense fallback={<Loading />}><PolicyPrivacySection /></Suspense>
    </div>
  )
}

function DataGroup() {
  const [result, setResult] = useState<string | null>(null)
  const run = (kind: string) => void productApi.exportData({ kind }).then((r) => setResult(`已导出：${r.path}`)).catch((e) => setResult(String(e)))
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <SecondaryButton onClick={() => run('person')}>导出我的成竹</SecondaryButton>
        <SecondaryButton onClick={() => run('quick_notes')}>导出速记</SecondaryButton>
        <SecondaryButton onClick={() => run('question_banks')}>导出题库</SecondaryButton>
      </div>
      <p className="text-[11px] text-text-muted">导出目标、场次、复盘请在对应页面的 ⋯ 菜单中操作。删除目标、场次、速记、题库和未确认的事实草稿也在各自的位置。</p>
      <div className="flex flex-wrap items-center gap-2">
        <SecondaryButton onClick={() => void productApi.integrity(false).then((r) => setResult(r.ok ? '数据完整，没有悬空引用' : `发现 ${r.issues.length} 处悬空引用`))}>检查数据完整性</SecondaryButton>
        <SecondaryButton onClick={() => void productApi.integrity(true).then(() => setResult('已修复悬空引用'))}>修复</SecondaryButton>
      </div>
      {result ? <p role="status" className="break-all text-xs text-text-secondary">{result}</p> : null}
    </div>
  )
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function metric(value: unknown, empty = '—'): string {
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : String(Math.round(value * 100) / 100)
  if (typeof value === 'string' && value) return value
  return empty
}

function rate(value: unknown): string {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

function ValidationSummary({ data }: { data: Record<string, unknown> }) {
  const goal = asRecord(data.A_goal_reuse)
  const reflection = asRecord(data.B_reflection_to_prepare)
  const cue = asRecord(data.C_fast_cue_usefulness)
  const usefulness = asRecord(cue.usefulness)
  const transfer = asRecord(data.D_practice_transfer)
  const inbox = asRecord(data.E_fact_inbox_burden)
  const value = asRecord(data.F_quick_notes_and_pins)
  const notes = asRecord(value.quick_notes)
  const pins = asRecord(value.pins)
  const evidence = String(data.evidence_level || 'NO_DATA')
  const real = String(data.real_user_validation || 'REAL_USER_VALIDATION_PENDING')
  const evidenceTone = evidence === 'LOCAL_DEVICE_USAGE' ? 'info' : evidence === 'SYNTHETIC_DOGFOOD' ? 'warn' : 'muted'

  const cards = [
    {
      key: 'A', title: 'Goal 是否持续复用', value: rate(goal.goal_reopen_rate),
      detail: `${metric(goal.goals, '0')} 个 Goal · 平均 ${metric(goal.sessions_per_goal, '0')} 场/Goal`,
    },
    {
      key: 'B', title: 'Reflection 是否改变下一步', value: rate(reflection.follow_through_rate),
      detail: `${metric(reflection.next_focus_from_reflection, '0')} 个 Next Focus 来自复盘`,
    },
    {
      key: 'C', title: 'Fast Cue 是否有帮助', value: metric(cue.rendered, '0'),
      detail: `已显示 Cue · 说话跟随率 ${rate(usefulness.speech_after_cue_rate)}`,
    },
    {
      key: 'D', title: 'Practice 是否迁移', value: metric(transfer.measured, '0'),
      detail: `${metric(transfer.improved, '0')} 个可测链路改善；Mock 不能冒充真实面试`,
    },
    {
      key: 'E', title: 'Fact Inbox 是否成负担', value: metric(inbox.backlog_size, '0'),
      detail: `当前 backlog · 解决率 ${rate(inbox.resolution_rate)}`,
    },
    {
      key: 'F', title: 'Quick Notes / Pin 是否有价值', value: metric(notes.selected_into_pack, '0'),
      detail: `速记进 Pack · Pin→Next Focus ${metric(pins.next_focus_from_pin, '0')}`,
    },
  ]

  return (
    <div className="mt-2 space-y-3" data-testid="validation-summary">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone={evidenceTone}>证据：{evidence}</StatusBadge>
        <StatusBadge tone={real === 'REAL_USER_VALIDATION_PENDING' ? 'warn' : 'ok'}>{real}</StatusBadge>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((card) => (
          <article key={card.key} className="rounded-xl border border-bg-hover/60 p-3">
            <div className="flex items-start gap-2">
              <span className="inline-flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-bg-tertiary text-[10px] font-bold text-text-secondary">{card.key}</span>
              <div className="min-w-0">
                <h4 className="text-xs font-semibold text-text-primary">{card.title}</h4>
                <p className="mt-1 text-xl font-semibold tabular-nums text-text-primary">{card.value}</p>
                <p className="mt-1 text-[11px] leading-relaxed text-text-muted">{card.detail}</p>
              </div>
            </div>
          </article>
        ))}
      </div>
      <p className="text-[11px] leading-relaxed text-text-muted">
        这里只显示这台电脑上的本地使用信号。Synthetic / automated evidence 只能证明工程闭环；
        没有真实用户证据时，成竹不会把它写成 PMF 或“面试成功率”。
      </p>
    </div>
  )
}

function DiagnosticsGroup() {
  const config = useInterviewStore((s) => s.config)
  const kb = useKbStore((s) => s.status)
  const diag = useAsync(() => api.intelDiagnostics(), [])
  const validation = useAsync(() => productApi.validation(), [])
  const cpu = (diag.data as { cpu?: { percent?: number } } | null)?.cpu?.percent
  return (
    <div className="space-y-3">
      <ul className="grid gap-2 sm:grid-cols-2">
        <li><StatusBadge tone={config?.api_key_set ? 'ok' : 'risk'}>答题模型：{config?.model_name || '未配置'}</StatusBadge></li>
        <li><StatusBadge tone={kb?.enabled ? 'ok' : 'muted'}>知识库：{kb?.enabled ? `${kb.total_docs ?? 0} 篇文档` : '未开启'}</StatusBadge></li>
        <li><StatusBadge tone={config?.has_resume ? 'ok' : 'warn'}>简历：{config?.has_resume ? '已载入' : '未上传'}</StatusBadge></li>
        <li><StatusBadge tone="muted">CPU：{typeof cpu === 'number' ? `${cpu}%` : '—'}</StatusBadge></li>
      </ul>
      <details className="text-xs">
        <summary className="cursor-pointer text-text-secondary">运行诊断（v1.2 Core）</summary>
        <pre className="mt-2 max-h-72 overflow-auto rounded-xl bg-bg-tertiary/50 p-2 text-[11px]">{JSON.stringify(diag.data, null, 2)}</pre>
      </details>
      <section aria-label="产品循环验证（v1.4）" className="rounded-2xl border border-bg-hover/60 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-text-primary">产品循环验证（v1.4）</h3>
            <p className="text-[11px] text-text-muted">Goal → Practice → Live → Reflection → Next Focus 的本地证据。</p>
          </div>
          {validation.loading ? <StatusBadge tone="busy">整理中</StatusBadge> : null}
        </div>
        {validation.error ? <div className="mt-2"><ErrorState message={validation.error} onRetry={validation.reload} /></div> : null}
        {validation.data ? <ValidationSummary data={validation.data} /> : null}
        {validation.data ? (
          <details className="mt-3 text-xs">
            <summary className="cursor-pointer text-text-secondary">查看原始本地指标</summary>
            <pre className="mt-2 max-h-96 overflow-auto rounded-xl bg-bg-tertiary/50 p-2 text-[11px]">{JSON.stringify(validation.data, null, 2)}</pre>
          </details>
        ) : null}
      </section>
    </div>
  )
}

export default function SettingsPage({ group, query }: { group: string; query: Record<string, string> }) {
  const current = (SETTINGS_GROUPS.map(([g]) => g) as string[]).includes(group) ? (group as SettingsGroup) : 'general'
  const [search, setSearch] = useState('')
  const goals = useAsync(() => productApi.goals(), [])
  const [goalId, setGoalId] = useState(query.goal ?? '')
  useEffect(() => { if (query.goal) setGoalId(query.goal) }, [query.goal])
  const hits = useMemo(() => searchCatalog(search), [search])
  const toggleKb = useKbStore((s) => s.toggleDrawer)
  const openOnboarding = () => void updateConfigAndRefresh({ onboarding_completed: false })

  const goalPicker = (
    <Field label="编辑范围">
      <select className={inputCls} value={goalId} onChange={(e) => setGoalId(e.target.value)}>
        <option value="">只改全局默认</option>
        {(goals.data?.items ?? []).map((g) => <option key={g.id} value={g.id}>Goal 默认：{g.title}</option>)}
      </select>
    </Field>
  )

  return (
    <Page testId="settings-page" wide>
      <PageHeader title="设置" subtitle="每个值都标明来源：全局默认 / Goal 默认 / 本场覆盖。" />
      <div className="relative mb-3">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" aria-hidden />
        <input type="search" aria-label="搜索设置" placeholder="搜索设置，例如：回答语言、浮窗、共享、快捷键" value={search} onChange={(e) => setSearch(e.target.value)}
          className={`${inputCls} pl-8`} data-testid="settings-search" />
        {search ? (
          <ul role="listbox" aria-label="搜索结果" className="absolute inset-x-0 top-[calc(100%+4px)] z-30 max-h-72 overflow-auto rounded-xl border border-bg-hover bg-bg-primary p-1 shadow-lg">
            {hits.length ? hits.map((h) => (
              <li key={h.key} role="option" aria-selected={false}>
                <button type="button" className="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-left text-xs hover:bg-bg-hover"
                  onClick={() => { navigate(paths.settings(h.group)); setSearch(''); window.setTimeout(() => document.querySelector(`[data-setting="${h.key}"]`)?.scrollIntoView({ block: 'center' }), 80) }}>
                  <span className="text-text-primary">{h.label}</span>
                  <span className="text-text-muted">{GROUP_LABEL_ZH[h.group]}{h.layered ? ' · 可按目标/本场覆盖' : ''}</span>
                </button>
              </li>
            )) : <li className="px-2.5 py-2 text-xs text-text-muted">没有匹配的设置</li>}
          </ul>
        ) : null}
      </div>
      <div className="grid gap-4 md:grid-cols-[180px_1fr]">
        <nav aria-label="设置分组">
          <ul className="flex gap-1 overflow-x-auto md:flex-col md:overflow-visible">
            {SETTINGS_GROUPS.map(([g, en]) => (
              <li key={g}>
                <button type="button" aria-current={current === g ? 'page' : undefined} onClick={() => navigate(paths.settings(g), { replace: true })}
                  className={`w-full whitespace-nowrap rounded-xl px-3 py-1.5 text-left text-xs ${current === g ? 'bg-container-primary text-container-on-primary font-semibold' : 'text-text-secondary hover:bg-bg-hover'}`}>
                  {/* WCAG AA: the hint must not be dimmed with opacity — the active
                      row already has a coloured background, so 70% text fails
                      contrast. Weight carries the hierarchy instead. */}
                  {GROUP_LABEL_ZH[g]}<span className="ml-1 text-[10px] font-normal">{en}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <div className="min-w-0">
          <SettingsSearchContext.Provider value="">
            <Suspense fallback={<Loading />}>
              {current === 'general' ? (
                <Section title="通用">
                  <div className="flex flex-wrap gap-2 pb-3"><SecondaryButton onClick={openOnboarding}>重新运行首次引导</SecondaryButton></div>
                  <PreferencesTab />
                </Section>
              ) : null}
              {current === 'models' ? <ModelsTab /> : null}
              {current === 'speech' ? <SpeechTab /> : null}
              {current === 'language' ? (
                <Section title="语言（五层彼此独立）">
                  {goalPicker}
                  <UiLanguageRow />
                  <LayerGroup keys={['whisper_language', 'answer_language', 'language', 'technical_term_policy']} goalId={goalId} />
                </Section>
              ) : null}
              {current === 'live' ? (
                <Section title="上场与浮窗">
                  {goalPicker}
                  <LayerGroup keys={['ai_policy_mode', 'human_assistance_policy', 'proactive_guidance_enabled']} goalId={goalId} />
                  <div className="pt-3" data-setting="overlay"><OverlayPrefs /></div>
                </Section>
              ) : null}
              {current === 'privacy' ? <Section title="隐私">{goalPicker}<PrivacyGroup goalId={goalId} /></Section> : null}
              {current === 'knowledge' ? (
                <Section title="知识库">
                  {goalPicker}
                  <LayerGroup keys={['kb_enabled']} goalId={goalId} />
                  <div className="pt-2"><PrimaryButton onClick={toggleKb}>管理知识库文件</PrimaryButton></div>
                </Section>
              ) : null}
              {current === 'shortcuts' ? (
                <Section title="快捷键" id="shortcuts">
                  <ul className="mb-3 space-y-1 text-xs text-text-secondary" data-setting="shortcuts">
                    <li><kbd className="rounded border border-bg-hover px-1">Ctrl+K</kbd> 命令面板</li>
                    <li><kbd className="rounded border border-bg-hover px-1">Ctrl+,</kbd> 设置</li>
                    <li><kbd className="rounded border border-bg-hover px-1">Ctrl+P</kbd> 标记这一刻（练习 / 上场中）</li>
                  </ul>
                  <GlobalShortcutsEditor />
                </Section>
              ) : null}
              {current === 'data' ? <Section title="数据与导出"><DataGroup /></Section> : null}
              {current === 'diagnostics' ? <Section title="诊断"><DiagnosticsGroup /></Section> : null}
            </Suspense>
          </SettingsSearchContext.Provider>
          <p className="pt-4 text-[11px] text-text-muted">共 {CATALOG.length} 项可搜索设置。</p>
        </div>
      </div>
    </Page>
  )
}
