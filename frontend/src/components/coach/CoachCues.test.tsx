import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import CoachCues from './CoachCues'
import { useInterviewStore } from '@/stores/configStore'

describe('CoachCues', () => {
  beforeEach(() => {
    useInterviewStore.setState({
      coachCues: [
        { id: 'interview', text: 'Interview cue', voiceUrl: '', createdAt: 1, sessionKind: 'live', targetSessionId: 'default' },
        { id: 'conv-a', text: 'Conversation A cue', voiceUrl: '', createdAt: 2, sessionKind: 'conversation', targetSessionId: 'conv-a' },
        { id: 'conv-b', text: 'Conversation B cue', voiceUrl: '', createdAt: 3, sessionKind: 'conversation', targetSessionId: 'conv-b' },
      ],
    } as any)
  })

  afterEach(() => {
    cleanup()
    useInterviewStore.setState({ coachCues: [] } as any)
  })

  it('shows only the current Conversation session cue', () => {
    render(<CoachCues sessionKind="conversation" targetSessionId="conv-a" />)

    expect(screen.getByText('Conversation A cue')).toBeTruthy()
    expect(screen.queryByText('Conversation B cue')).toBeNull()
    expect(screen.queryByText('Interview cue')).toBeNull()
  })

  it('keeps Conversation cues out of Interview surfaces by default', () => {
    render(<CoachCues />)

    expect(screen.getByText('Interview cue')).toBeTruthy()
    expect(screen.queryByText('Conversation A cue')).toBeNull()
    expect(screen.queryByText('Conversation B cue')).toBeNull()
  })
})
