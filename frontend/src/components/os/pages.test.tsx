import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { parsePath, useRouter } from '@/lib/router'
import { useOsStore } from '@/stores/osStore'

const productApiMock = vi.hoisted(() => ({
  home: vi.fn(),
  goals: vi.fn(),
  goal: vi.fn(),
  reflection: vi.fn(),
  reflectionAction: vi.fn(),
  factInbox: vi.fn(),
  factAction: vi.fn(),
  quickNotes: vi.fn(),
  patchQuickNote: vi.fn(),
  completeFocus: vi.fn(),
  dismissFocus: vi.fn(),
  settingLayers: vi.fn(),
  validation: vi.fn(),
}))

vi.mock('@/lib/productApi', () => ({ productApi: productApiMock, track: vi.fn() }))
vi.mock('@/lib/api', () => ({ api: { intelDiagnostics: vi.fn(async () => ({})) }, apiRequest: vi.fn(), apiUpload: vi.fn() }))

import HomePage from './HomePage'
import ReflectionPage from './ReflectionPage'
import FactInboxView from './FactInboxView'
import QuickNotesPanel from './QuickNotesPanel'
import { FeedbackSplit } from './PracticePage'

const focusItem = {
  id: 'nf1', goal_id: 'g1', type: 'KNOWLEDGE_GAP', title: 'Redis Cluster',
  reason: '岗位要求 Redis HA；你有 Redis 事实，但没有 Cluster 生产来源。', source_kind: 'GAP', source_ref: '',
  actions: [{ key: 'learn', label: '学知识' }, { key: 'add_source', label: '补来源' }, { key: 'practice', label: '练这个问题' }],
  priority: 60, status: 'ACTIVE', origin: 'DERIVED',
}

beforeEach(() => {
  vi.clearAllMocks()
  useRouter.setState({ route: parsePath('#/home') })
  useOsStore.setState({ createGoalOpen: false, contextGoalId: null })
})

describe('Action Home', () => {
  it('starts from a goal when there is none', async () => {
    productApiMock.home.mockResolvedValue({ state: 'NO_GOAL', primary_action: { key: 'create_goal', label: '创建第一个求职目标' }, next_interview: null, focus_goal: null, next_focus: [], needs_attention: [], recent_session: null, active_goal_count: 0 })
    render(<HomePage />)
    fireEvent.click(await screen.findByRole('button', { name: '创建第一个求职目标' }))
    expect(useOsStore.getState().createGoalOpen).toBe(true)
  })

  it('shows next interview, next focus with reasons, blockers — and no readiness score', async () => {
    productApiMock.home.mockResolvedValue({
      state: 'ACTIVE', primary_action: { key: 'continue_prepare', label: '继续准备', goal_id: 'g1' },
      next_interview: { goal_id: 'g1', interview_id: 'i1', title: 'MindRank · 技术二面', company: 'MindRank', role: 'AIDD', round: '技术二面', scheduled_at: Date.now() / 1000 + 86400, actions: [] },
      focus_goal: { id: 'g1', title: 'MindRank · AIDD' }, next_focus: [focusItem],
      needs_attention: [{ kind: 'FACT_INBOX', text: '3 个事实待确认', action: { key: 'open_fact_inbox', label: '去确认' } }],
      recent_session: null, active_goal_count: 1,
    })
    const { container } = render(<HomePage />)
    expect(await screen.findByText('MindRank · 技术二面')).toBeInTheDocument()
    for (const label of ['继续准备', '开始练习', '上场检查']) expect(screen.getAllByRole('button', { name: label }).length).toBeGreaterThan(0)
    expect(screen.getByText(/没有 Cluster 生产来源/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '练这个问题' })).toBeInTheDocument()
    expect(screen.getByText('3 个事实待确认')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/%|readiness|准备度|录用概率/)
    fireEvent.click(screen.getByRole('button', { name: '去确认' }))
    expect(useRouter.getState().route).toMatchObject({ name: 'me', params: { tab: 'inbox' } })
  })
})

describe('Reflection 3.0', () => {
  it('puts pinned moments first and writes back through the API', async () => {
    productApiMock.reflection.mockResolvedValue({
      session_kind: 'PRACTICE', session_ref: 'pr1', goal_id: 'g1', title: '练习复盘',
      first_screen: {
        next_step: { kind: 'OWNERSHIP', title: 'Ownership 表达', reason: '多用“我们”', finding_id: 't1:OWNERSHIP' },
        pinned_moments: [{ id: 'pin1', session_kind: 'PRACTICE', session_id: 'pr1', turn_id: '', goal_id: 'g1', tag: 'BAD_ANSWER', tag_label: '没答好', question: 'Redis 集群怎么扩容？', transcript_excerpt: '', note: '', ts: 1 }],
        went_well: [], fact_checks: [], story_opportunities: [],
        to_improve: [{ id: 't1:OWNERSHIP', kind: 'OWNERSHIP', kind_label: 'Ownership 表达', finding: '听不出你本人做了什么', question: '讲讲项目', actual_speech: '我们团队一起做的', occurrences: 2 }],
      },
      delivery: [], timeline: [], actions: [], ask_cue_feedback: false,
    })
    productApiMock.reflectionAction.mockResolvedValue({ next_focus: { id: 'nf9' } })
    render(<ReflectionPage kind="PRACTICE" sessionRef="pr1" />)
    expect(await screen.findByText('Redis 集群怎么扩容？')).toBeInTheDocument()
    const sections = screen.getAllByRole('region').map((r) => r.getAttribute('aria-labelledby'))
    expect(sections.length).toBeGreaterThan(2)
    expect(screen.getByText(/你说的：“我们团队一起做的”/)).toBeInTheDocument()
    fireEvent.click(screen.getAllByRole('button', { name: '设为下一步重点' })[0])
    await waitFor(() => expect(productApiMock.reflectionAction).toHaveBeenCalledWith('PRACTICE', 'pr1', expect.objectContaining({ action: 'SET_NEXT_FOCUS' })))
  })
})

describe('Fact Inbox', () => {
  it('shows what the material supports and offers 我主导 / 我参与', async () => {
    productApiMock.factInbox.mockResolvedValue({
      count: 1, batch: null, merge_suggestions: [], policy: { mode: 'STANDARD', reasons: [] },
      items: [{ id: 'c1', text: '我负责完整 RAG 架构设计', project: 'WenNian', source: 'resume', provenance_status: 'SUPPORTING_EVIDENCE', risk: 'HIGH', supported_label: '参与（材料里没有主导的说法）', lead_language: true, primary_actions: [], more_actions: [] }],
    })
    productApiMock.factAction.mockResolvedValue({})
    render(<FactInboxView />)
    expect(await screen.findByText('需要你确认 · 1')).toBeInTheDocument()
    expect(screen.getByText('WenNian')).toBeInTheDocument()
    expect(screen.getByText(/参与（材料里没有主导的说法）/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '我参与' }))
    await waitFor(() => expect(productApiMock.factAction).toHaveBeenCalledWith('c1', 'PARTICIPATE', {}))
  })
})

describe('Quick Notes', () => {
  it('is read-only in Live and states it is not evidence', async () => {
    productApiMock.quickNotes.mockResolvedValue({ items: [{ id: 'q1', scope: 'GLOBAL', goal_id: null, title: '想问', content: '团队规模？', pinned: true, sort_order: 10, tags: [], revision: 1, created_at: 1, updated_at: 1 }] })
    render(<QuickNotesPanel readOnly context="live" />)
    expect(await screen.findByText('团队规模？')).toBeInTheDocument()
    expect(screen.getByText(/不是证据/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '添加速记' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '速记操作' })).not.toBeInTheDocument()
  })
})

describe('Practice feedback', () => {
  it('keeps Content and Delivery separate and shows no score', () => {
    render(<FeedbackSplit feedback={{
      content: { signals: {}, strengths: [], findings: [{ signal: 'ownership', dimension: 'ownership', level: 2, finding: '多用“我们”', evidence_from_actual_speech: '我们团队一起做的', action: '换成你本人的动作' }] },
      delivery: { metrics: { answer_duration_s: 40, time_to_conclusion_s: 16, fillers: 3, timing_estimated: false }, advice: ['结论在约 16 秒后才出现；做一次 15 秒结论训练。'] },
    }} />)
    const content = screen.getByRole('region', { name: '内容' })
    const delivery = screen.getByRole('region', { name: '表达' })
    expect(within(content).getByText(/我们团队一起做的/)).toBeInTheDocument()
    expect(within(delivery).getByText(/15 秒结论训练/)).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/分数|score/i)
  })
})
