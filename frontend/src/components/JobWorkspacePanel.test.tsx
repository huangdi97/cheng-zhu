import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import JobWorkspacePanel from './JobWorkspacePanel'

const JOB_RESPONSE = {
  company: '示例科技',
  title: '高级后端工程师',
  level: 'senior',
  technologies: ['Python', 'Redis', 'Kafka'],
  must_have: ['精通 Python', '熟悉分布式基础'],
  nice_to_have: ['有 LLM 应用经验'],
  likely_interview_dimensions: ['缓存设计与一致性', '消息队列与顺序性'],
  alignment: {
    requirements: [
      {
        requirement_text: 'Python',
        status: 'STRONG_MATCH',
        evidence_claim_ids: ['cl-1'],
        explanation: '简历/材料中有带动作动词的项目证据',
      },
      {
        requirement_text: 'Kafka',
        status: 'KNOWLEDGE_MATCH',
        evidence_claim_ids: [],
        explanation: '无候选人证据，但属于可由通用知识覆盖的技术域',
      },
    ],
  },
  workspace: {
    gap_map: [
      { topic: 'Kubernetes', status: 'KNOWLEDGE_MATCH', source: 'job_alignment', priority: 'medium', reason: '可以用通用知识回答，但没有证据时不能说做过' },
      { topic: 'RAG 评估', status: 'REVIEW_WEAKNESS', source: 'review', priority: 'high', reason: '复盘中暴露的薄弱点（出现 2 次）' },
    ],
    attack_surface: [
      { claim_id: 'cl-1', text: '订单系统使用 Redis 支撑 3 万 QPS', truth_status: 'SUPPORTED', job_aligned: true, risks: ['指标会被追问口径与来源'], probes: ['整体架构是怎么设计的？'] },
    ],
    question_graph: [
      { id: 'q1', text: '谈谈你对「Kubernetes」的理解？', kind: 'KNOWLEDGE', source: 'job_alignment', parent_id: '' },
      { id: 'q2', text: '你实际做过「Kubernetes」相关的事情吗？', kind: 'EXPERIENCE_BOUNDARY', source: 'job_alignment', parent_id: 'q1' },
    ],
    stories: {
      items: [],
      prompts: [{ competency: '团队协作', hint: '从你的真实经历里找一个体现「团队协作」的事件', candidate_sources: ['订单系统使用 Redis 支撑 3 万 QPS'] }],
    },
  },
}

describe('JobWorkspacePanel', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the analyze button and shows a hint when JD is empty', () => {
    render(<JobWorkspacePanel jdText="" resumeText="" />)
    expect(screen.getByText('岗位工作台（Job Workspace）')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /分析岗位/ }))
    expect(screen.getByRole('alert')).toHaveTextContent('请先填写 JD 后再分析岗位结构')
  })

  it('renders the structured job payload after a successful analyze', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(JOB_RESPONSE),
    })
    render(<JobWorkspacePanel jdText="高级后端工程师" resumeText="我使用 Python" />)
    fireEvent.click(screen.getByRole('button', { name: /分析岗位/ }))
    await waitFor(() => {
      expect(screen.getByText('高级后端工程师')).toBeInTheDocument()
    })
    expect(screen.getByText('senior')).toBeInTheDocument()
    expect(screen.getAllByText('Python').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/缓存设计与一致性 \/ 消息队列与顺序性/)).toBeInTheDocument()
    expect(screen.getByText(/STRONG_MATCH/)).toBeInTheDocument()
    expect(screen.getByText(/KNOWLEDGE_MATCH/)).toBeInTheDocument()
  })

  it('shows an error notice when the backend rejects the request', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve('server error'),
    })
    render(<JobWorkspacePanel jdText="高级后端工程师" resumeText="" />)
    fireEvent.click(screen.getByRole('button', { name: /分析岗位/ }))
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument()
    })
    expect(screen.getByRole('alert').textContent).toContain('server error')
    expect(screen.queryByText('高级后端工程师')).not.toBeInTheDocument()
  })

  it('keeps the loading state visible while the request is in flight', async () => {
    let resolveRequest: ((value: unknown) => void) | null = null
    global.fetch = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve
        }),
    )
    render(<JobWorkspacePanel jdText="高级后端工程师" resumeText="" />)
    fireEvent.click(screen.getByRole('button', { name: /分析岗位/ }))
    expect(screen.getByText('分析中…')).toBeInTheDocument()
    if (resolveRequest) resolveRequest({ ok: true, json: () => Promise.resolve(JOB_RESPONSE) })
    await waitFor(() => {
      expect(screen.getByText('高级后端工程师')).toBeInTheDocument()
    })
  })

  it('posts JD and resume to the workspace endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(JOB_RESPONSE) })
    global.fetch = fetchMock
    render(<JobWorkspacePanel jdText="JD 文本" resumeText="简历文本" />)
    fireEvent.click(screen.getByRole('button', { name: /分析岗位/ }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toContain('/api/intelligence/workspace')
    expect(JSON.parse(init.body)).toEqual({ jd_text: 'JD 文本', resume_text: '简历文本' })
  })

  it('renders gap map, attack surface, stories and a collapsible question graph', async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(JOB_RESPONSE) })
    render(<JobWorkspacePanel jdText="高级后端工程师" resumeText="" />)
    fireEvent.click(screen.getByRole('button', { name: /分析岗位/ }))
    await waitFor(() => expect(screen.getByLabelText('Gap Map')).toBeInTheDocument())
    expect(screen.getByText('RAG 评估')).toBeInTheDocument()
    expect(screen.getByText('优先')).toBeInTheDocument()
    expect(screen.getByText('订单系统使用 Redis 支撑 3 万 QPS')).toBeInTheDocument()
    expect(screen.getByText('指标会被追问口径与来源')).toBeInTheDocument()
    expect(screen.getByText(/缺少「团队协作」故事/)).toBeInTheDocument()

    const toggle = screen.getByRole('button', { name: /追问树（1 条主线）/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('你实际做过「Kubernetes」相关的事情吗？')).not.toBeInTheDocument()
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('事实边界')).toBeInTheDocument()
    expect(screen.getByText('你实际做过「Kubernetes」相关的事情吗？')).toBeInTheDocument()
  })

  it('renders nothing structured when the payload is malformed', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ unexpected: 'shape' }),
    })
    render(<JobWorkspacePanel jdText="高级后端工程师" resumeText="" />)
    fireEvent.click(screen.getByRole('button', { name: /分析岗位/ }))
    await waitFor(() => {
      expect(screen.getByText('未识别岗位')).toBeInTheDocument()
    })
    expect(screen.queryByText(/STRONG_MATCH/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Gap Map')).not.toBeInTheDocument()
  })
})
