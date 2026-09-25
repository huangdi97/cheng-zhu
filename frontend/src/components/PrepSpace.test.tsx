import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PrepSpace from './PrepSpace'

const apiMock = vi.hoisted(() => ({
  prepListSpaces: vi.fn(),
  prepCreateSpace: vi.fn(),
  prepGetSpace: vi.fn(),
  prepDeleteSpace: vi.fn(),
  prepGenerate: vi.fn(),
  prepActivateLaunchPack: vi.fn(),
  resumeHistory: vi.fn(),
  resumeHistoryDetail: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: apiMock,
}))

vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}))

function makeSpace(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    title: '后端准备空间',
    role: '后端开发',
    company: '某公司',
    jd_text: 'JD',
    resume_text: '简历',
    resume_history_id: null,
    insight_markdown: '### 岗位考察重点\n- 高并发',
    insight_status: 'done',
    insight_error: '',
    questions: [{ question: '介绍一下你的项目', type: 'project', why: '考察项目深挖' }],
    questions_status: 'done',
    questions_error: '',
    skill_cards: [
      {
        id: 1,
        space_id: 1,
        project_name: '缓存优化',
        card: { name: '缓存优化', my_role: '核心开发', tech_decisions: ['Kafka 削峰'], metrics: [], tradeoffs: [], likely_follow_ups: [] },
        status: 'done',
        error: '',
        created_at: 0,
        updated_at: 0,
      },
    ],
    created_at: 0,
    updated_at: 0,
    ...overrides,
  }
}

describe('PrepSpace', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.prepListSpaces.mockResolvedValue({ items: [] })
    apiMock.prepGetSpace.mockResolvedValue(makeSpace())
    apiMock.prepCreateSpace.mockResolvedValue(makeSpace())
    apiMock.prepDeleteSpace.mockResolvedValue({ ok: true })
    apiMock.prepGenerate.mockResolvedValue(makeSpace())
    apiMock.prepActivateLaunchPack.mockResolvedValue({
      ok: true,
      strategy_ready: true,
      strategy_generated: true,
      pack: {
        space_id: 1, title: '后端准备空间', role: '后端开发', company: '某公司',
        briefing: ['高并发'],
        project_anchors: [{ name: '缓存优化', anchors: ['核心开发'], likely_followups: [] }],
        question_groups: { project: ['介绍一下你的项目'] },
        risk_prompts: ['为什么选择 Kafka？'],
        readiness: { has_jd: true, has_resume: true, project_count: 1, question_count: 1 },
      },
    })
    apiMock.resumeHistory.mockResolvedValue({ items: [] })
    apiMock.resumeHistoryDetail.mockResolvedValue({ summary: '历史简历全文' })
  })

  it('shows empty state when no spaces', async () => {
    render(<PrepSpace />)
    expect(await screen.findByText('还没有准备空间，点击右上角"新建准备空间"开始')).toBeTruthy()
    expect(apiMock.prepListSpaces).toHaveBeenCalledTimes(1)
  })

  it('creates a space and shows detail', async () => {
    render(<PrepSpace />)
    fireEvent.click(await screen.findByText('新建准备空间'))
    fireEvent.change(screen.getByPlaceholderText('例如：后端开发工程师'), { target: { value: '后端开发' } })
    fireEvent.change(screen.getByPlaceholderText('粘贴目标岗位的职位描述…'), { target: { value: 'JD 内容' } })
    fireEvent.change(screen.getByPlaceholderText('粘贴你的简历正文 / 项目经历…'), { target: { value: '简历内容' } })
    fireEvent.click(screen.getByText('创建准备空间'))

    await waitFor(() => expect(apiMock.prepCreateSpace).toHaveBeenCalledTimes(1))
    expect(apiMock.prepCreateSpace).toHaveBeenCalledWith({
      role: '后端开发',
      company: undefined,
      jd_text: 'JD 内容',
      resume_text: '简历内容',
      resume_history_id: undefined,
    })
    expect(await screen.findByText('后端准备空间')).toBeTruthy()
  })

  it('renders insight, questions and skill cards in detail', async () => {
    apiMock.prepListSpaces.mockResolvedValue({
      items: [{ id: 1, title: '后端准备空间', role: '后端开发', company: '某公司', insight_status: 'done', questions_status: 'done', skill_card_count: 1, updated_at: 0 }],
    })
    render(<PrepSpace />)
    fireEvent.click(await screen.findByText('后端准备空间'))
    expect(await screen.findByText('岗位对齐洞察')).toBeTruthy()
    expect(await screen.findByText('预测真题（1）')).toBeTruthy()
    expect(await screen.findByText('介绍一下你的项目')).toBeTruthy()
    expect(await screen.findByText('项目技能卡（1）')).toBeTruthy()
    expect(await screen.findByText('缓存优化')).toBeTruthy()
  })

  it('activates a launch pack for the current interview', async () => {
    apiMock.prepListSpaces.mockResolvedValue({
      items: [{ id: 1, title: '后端准备空间', role: '后端开发', company: '某公司', insight_status: 'done', questions_status: 'done', skill_card_count: 1, updated_at: 0 }],
    })
    render(<PrepSpace />)
    fireEvent.click(await screen.findByText('后端准备空间'))
    fireEvent.click(await screen.findByRole('button', { name: '用于本场面试' }))

    await waitFor(() => expect(apiMock.prepActivateLaunchPack).toHaveBeenCalledWith(1))
    expect(await screen.findByText('本场上场包已启用')).toBeInTheDocument()
    expect(screen.getByText(/为什么选择 Kafka/)).toBeInTheDocument()
  })
})
