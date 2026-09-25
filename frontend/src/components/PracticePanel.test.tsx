import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PracticePanel from './PracticePanel'

const apiMock = vi.hoisted(() => ({
  prepPracticeStart: vi.fn(),
  prepPracticeAnswer: vi.fn(),
  prepPracticeFinish: vi.fn(),
  prepListen: vi.fn(),
  getDevices: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: apiMock,
}))

vi.mock('react-markdown', () => ({
  default: ({ children }: { children: string }) => <div>{children}</div>,
}))

const Q1 = { question: '介绍一下你的项目', type: 'project', why: '考察项目' }
const Q2 = { question: 'Kafka 分区数怎么定？', type: 'follow_up', why: '基于上一题追问' }

describe('PracticePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.prepPracticeStart.mockResolvedValue({ practice_id: 'p1', rounds: 2, question: Q1 })
    apiMock.prepPracticeAnswer.mockResolvedValue({
      done: false,
      answered: 1,
      feedback: {
        strengths: ['结构清晰'],
        risks: ['深度不足'],
        scorecard: { 准确性: 8, 深度: 6 },
        improvement_advice: '补充一个踩坑',
        follow_up_questions: [],
        tags: ['Redis'],
      },
      next_question: Q2,
    })
    apiMock.getDevices.mockResolvedValue({ devices: [{ id: 1, name: '麦克风', is_loopback: false }] })
    apiMock.prepPracticeFinish.mockResolvedValue({
      done: true,
      report: { review_session_id: 9, summary_markdown: '## 总结', strong_points: ['表达好'], weak_points: ['深度'], turn_count: 1, avg_score: 7 },
    })
  })

  it('starts a session and shows the first question', async () => {
    render(<PracticePanel spaceId={1} onClose={() => {}} />)
    expect(await screen.findByText('介绍一下你的项目')).toBeTruthy()
    expect(screen.getByText('0/2 轮')).toBeTruthy()
  })

  it('submits an answer and shows feedback + next question', async () => {
    render(<PracticePanel spaceId={1} onClose={() => {}} />)
    await screen.findByText('介绍一下你的项目')
    fireEvent.change(screen.getByPlaceholderText(/把你的回答打在这里/), { target: { value: '我的回答' } })
    fireEvent.click(screen.getByText('提交回答'))

    await waitFor(() => expect(apiMock.prepPracticeAnswer).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('Kafka 分区数怎么定？')).toBeTruthy()
    expect(screen.getByText(/结构清晰/)).toBeTruthy()
  })

  it('finishing early shows the report', async () => {
    apiMock.prepPracticeAnswer.mockResolvedValue({
      done: true,
      answered: 1,
      feedback: { strengths: ['s'], risks: [], scorecard: {}, improvement_advice: '', follow_up_questions: [], tags: [] },
      report: { review_session_id: 9, summary_markdown: '## 总结', strong_points: ['表达好'], weak_points: ['深度'], turn_count: 1, avg_score: 7 },
    })
    render(<PracticePanel spaceId={1} onClose={() => {}} />)
    await screen.findByText('介绍一下你的项目')
    fireEvent.change(screen.getByPlaceholderText(/把你的回答打在这里/), { target: { value: '我的回答' } })
    fireEvent.click(screen.getByText('提交回答'))

    expect(await screen.findByText('练习完成 · 整场总结')).toBeTruthy()
    expect(await screen.findByText('整场均分 7')).toBeTruthy()
    expect(apiMock.prepPracticeFinish).not.toHaveBeenCalled()
  })
})