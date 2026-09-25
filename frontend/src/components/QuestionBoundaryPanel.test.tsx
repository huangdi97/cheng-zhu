import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import QuestionBoundaryPanel from './QuestionBoundaryPanel'
import { useInterviewStore } from '@/stores/configStore'

const apiMock = vi.hoisted(() => ({
  questionBoundaryFlush: vi.fn(),
  questionBoundaryDiscard: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: apiMock,
  getErrorMessage: (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback,
}))

describe('QuestionBoundaryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.questionBoundaryFlush.mockResolvedValue({ ok: true, flushed: true })
    apiMock.questionBoundaryDiscard.mockResolvedValue({ ok: true, discarded: true })
    useInterviewStore.setState({ questionParseStatus: null, toastMessage: null } as any)
  })

  it('shows a provisional question and can flush it immediately', async () => {
    useInterviewStore.setState({
      questionParseStatus: { stage: 'assembling', raw_text: 'Redis 为什么快，它有哪些数据结构' },
    } as any)
    render(<QuestionBoundaryPanel />)

    expect(screen.getByText('正在组织问题')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '立即作答' }))
    await waitFor(() => expect(apiMock.questionBoundaryFlush).toHaveBeenCalledTimes(1))
  })

  it('renders independent clusters and subquestion counts', () => {
    useInterviewStore.setState({
      questionParseStatus: {
        stage: 'parsed',
        raw_text: 'Redis 为什么快？另外说一下线程池。',
        clusters: [
          { primary_question: 'Redis 为什么快', question_type: 'technical', subquestions: ['有哪些数据结构'] },
          { primary_question: '线程池参数怎么配置', question_type: 'technical', subquestions: [] },
        ],
      },
    } as any)
    render(<QuestionBoundaryPanel />)

    expect(screen.getByText('2 个独立问题')).toBeInTheDocument()
    expect(screen.getByText(/技术题 · 1 子问/)).toBeInTheDocument()
    expect(screen.getByText('线程池参数怎么配置')).toBeInTheDocument()
  })
})
