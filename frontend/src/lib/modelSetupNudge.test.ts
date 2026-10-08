import { describe, expect, it } from 'vitest'
import { shouldPromptForInterviewModel } from './modelSetupNudge'

describe('Interview model-setup nudge does not obscure Conversation Beta', () => {
  it('does not prompt on Conversation deep links when no model is configured', () => {
    const config = { api_key_set: false }
    for (const route of ['conversation-home', 'conversation-onboarding', 'conversations', 'conversation', 'conversation-live']) {
      expect(shouldPromptForInterviewModel(config, 'conversation', route)).toBe(false)
      // Before profile sync, localStorage can still say Interview.
      expect(shouldPromptForInterviewModel(config, 'interview', route)).toBe(false)
    }
  })

  it('retains guided setup for Interview while respecting an existing model', () => {
    expect(shouldPromptForInterviewModel({ api_key_set: false }, 'interview', 'home')).toBe(true)
    expect(shouldPromptForInterviewModel({ api_key_set: false }, 'interview', 'live')).toBe(true)
    expect(shouldPromptForInterviewModel({ api_key_set: false }, 'conversation', 'settings')).toBe(false)
    expect(shouldPromptForInterviewModel({ api_key_set: true }, 'interview', 'home')).toBe(false)
    expect(shouldPromptForInterviewModel(null, 'interview', 'home')).toBe(false)
  })
})
