import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SkillBuilderPanel from './SkillBuilderPanel'

const apiMock = vi.hoisted(() => ({
  prepSkillBuilderStart: vi.fn(),
  prepSkillBuilderAnswer: vi.fn(),
  prepSkillBuilderSkip: vi.fn(),
  prepPracticeTranscribe: vi.fn(),
  prepListen: vi.fn(),
  getDevices: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: apiMock,
}))

function startResult() {
  return {
    builder_id: 'b1',
    project: '订单履约中台重构',
    project_index: 0,
    project_total: 2,
    question: '项目背景是什么？',
    question_index: 1,
    question_total: 6,
  }
}

describe('SkillBuilderPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiMock.prepSkillBuilderStart.mockResolvedValue(startResult())
    apiMock.prepSkillBuilderAnswer.mockResolvedValue({
      done: false,
      project: '订单履约中台重构',
      project_index: 0,
      project_total: 2,
      question: '你的角色是什么？',
      question_index: 2,
      question_total: 6,
    })
    apiMock.prepSkillBuilderSkip.mockResolvedValue({ done: true, card_saved: { name: '订单履约中台重构' } })
    apiMock.getDevices.mockResolvedValue({ devices: [{ id: 1, name: '麦克风', is_loopback: false }] })
  })

  it('starts and shows the first question', async () => {
    render(<SkillBuilderPanel spaceId={1} onClose={() => {}} />)
    expect(await screen.findByText('项目背景是什么？')).toBeTruthy()
    expect(screen.getByText('项目 1/2 · 追问 1/6')).toBeTruthy()
  })

  it('submitting an answer moves to next question', async () => {
    render(<SkillBuilderPanel spaceId={1} onClose={() => {}} />)
    await screen.findByText('项目背景是什么？')
    fireEvent.change(screen.getByPlaceholderText(/直接回答这个问题/), { target: { value: '我的回答' } })
    fireEvent.click(screen.getByText('提交回答'))
    await waitFor(() => expect(apiMock.prepSkillBuilderAnswer).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('你的角色是什么？')).toBeTruthy()
  })

  it('skip finishes and shows done card', async () => {
    render(<SkillBuilderPanel spaceId={1} onClose={() => {}} />)
    await screen.findByText('项目背景是什么？')
    fireEvent.change(screen.getByPlaceholderText(/直接回答这个问题/), { target: { value: '答' } })
    fireEvent.click(screen.getByText('提交回答'))
    await waitFor(() => expect(apiMock.prepSkillBuilderAnswer).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByText('跳过本项'))
    expect(await screen.findByText('全部项目已整理完成')).toBeTruthy()
    expect(await screen.findByText('已沉淀技能卡（1）')).toBeTruthy()
  })
})