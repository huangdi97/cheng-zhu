import { describe, expect, it } from 'vitest'
import { captureViewState, latestVisibleGuidance } from './liveViewState'

describe('Conversation Live capture presentation truth', () => {
  const active = { status: 'ACTIVE', capture_mode: 'TRANSCRIPT' }

  it('never advertises listening for Notes Only or ended Sessions', () => {
    expect(captureViewState({ status: 'ACTIVE', capture_mode: 'NOTES_ONLY' }, null))
      .toEqual({ label: '仅笔记 · 未采集音频', listening: false })
    expect(captureViewState({ status: 'ENDED', capture_mode: 'TRANSCRIPT' }, {
      active: true, owns_requested_session: true, paused: false,
    })).toEqual({ label: '会话已结束', listening: false })
  })

  it('requires active ownership and no pause before indicating capture', () => {
    expect(captureViewState(active, null)).toEqual({ label: '正在确认音频状态', listening: false })
    expect(captureViewState(active, { active: false, owns_requested_session: false }))
      .toEqual({ label: '转写未启动', listening: false })
    expect(captureViewState(active, { active: true, owns_requested_session: false }))
      .toEqual({ label: '其他会话正在使用音频', listening: false })
    expect(captureViewState(active, { active: true, owns_requested_session: true, paused: true }))
      .toEqual({ label: '转写已暂停', listening: false })
    expect(captureViewState(active, { active: true, owns_requested_session: true, paused: false }))
      .toEqual({ label: '正在采集并转写', listening: true })
  })
})

describe('Conversation Guidance selection', () => {
  const older = { id: 'g1', status: 'SHOWN', user_action: 'NONE' }

  it('only displays the newest event, preventing old cards from reviving after SILENT', () => {
    expect(latestVisibleGuidance([older])).toEqual(older)
    expect(latestVisibleGuidance([{ id: 'g2', status: 'SUPPRESSED', user_action: 'NONE' }, older])).toBeNull()
    expect(latestVisibleGuidance([{ id: 'g2', status: 'SHOWN', user_action: 'CANCELLED_BY_DIRECT_QUESTION' }, older])).toBeNull()
  })

  it('keeps dismissed/snoozed/used Guidance out of the primary card', () => {
    for (const action of ['DISMISSED', 'SNOOZED', 'USED']) {
      expect(latestVisibleGuidance([{ ...older, user_action: action }])).toBeNull()
    }
    expect(latestVisibleGuidance([{ ...older, user_action: 'PINNED' }])).toEqual({ ...older, user_action: 'PINNED' })
    expect(latestVisibleGuidance([])).toBeNull()
  })
})
