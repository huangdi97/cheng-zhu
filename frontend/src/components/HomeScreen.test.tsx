import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import HomeScreen from './HomeScreen'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'

describe('HomeScreen', () => {
  beforeEach(() => {
    useUiPrefsStore.setState({ appMode: 'home' })
  })

  it('shows the two entry cards', () => {
    render(<HomeScreen />)
    expect(screen.getByText('演练')).toBeTruthy()
    expect(screen.getByText('上场')).toBeTruthy()
    expect(screen.getByText('先准备，再上场 —— 一个工作台，覆盖准备 → 实战 → 复盘全流程')).toBeTruthy()
  })

  it('clicking prep card switches to prep mode', () => {
    render(<HomeScreen />)
    fireEvent.click(screen.getByText('演练'))
    expect(useUiPrefsStore.getState().appMode).toBe('prep')
  })

  it('clicking assist card switches to assist mode', () => {
    render(<HomeScreen />)
    fireEvent.click(screen.getByText('上场'))
    expect(useUiPrefsStore.getState().appMode).toBe('assist')
  })
})