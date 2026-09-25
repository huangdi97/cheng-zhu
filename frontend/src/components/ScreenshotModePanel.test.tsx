import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ScreenshotModePanel from './ScreenshotModePanel'
import { useInterviewStore } from '@/stores/configStore'

vi.mock('./AnswerPanel', () => ({ default: () => <div>answer-panel</div> }))

describe('ScreenshotModePanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useInterviewStore.setState({
      config: { active_model: 0, models: [{ name: 'DeepSeek', supports_vision: false }] } as any,
    })
  })

  it('shows vision warning when current model lacks vision', () => {
    render(<ScreenshotModePanel serverScreenLoading={false} onAsk={() => {}} />)
    expect(screen.getByText('截图模式')).toBeTruthy()
    expect(screen.getByText(/不支持识图/)).toBeTruthy()
  })

  it('hides warning and enables button with a vision model', () => {
    useInterviewStore.setState({
      config: { active_model: 0, models: [{ name: 'GPT-4o', supports_vision: true }] } as any,
    })
    render(<ScreenshotModePanel serverScreenLoading={false} onAsk={() => {}} />)
    expect(screen.queryByText(/不支持识图/)).toBeNull()
    expect((screen.getByText('截图审题') as HTMLButtonElement).disabled).toBe(false)
  })

  it('calls onAsk when clicked', () => {
    useInterviewStore.setState({
      config: { active_model: 0, models: [{ name: 'GPT-4o', supports_vision: true }] } as any,
    })
    const onAsk = vi.fn()
    render(<ScreenshotModePanel serverScreenLoading={false} onAsk={onAsk} />)
    fireEvent.click(screen.getByText('截图审题'))
    expect(onAsk).toHaveBeenCalledTimes(1)
  })
})