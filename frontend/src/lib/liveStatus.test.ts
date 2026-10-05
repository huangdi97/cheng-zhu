import { describe, expect, it } from 'vitest'
import { deriveLiveStatus, LIVE_STATUS_LABELS } from './guidanceViewModel'
import { effectiveOverlaySize } from '@/stores/overlayLayoutStore'

const cue = { direction: '先给结论', cues: [{ text: 'RAG 更适合频繁更新的知识', source: 'WORLD_KNOWLEDGE' }] }

describe('single Live status (Main UI and Overlay share it)', () => {
  it('walks Listening → Question detected → Preparing → Cue ready → Answering', () => {
    const base = { isRecording: true, wsConnected: true }
    expect(deriveLiveStatus({ ...base, qa: null, streaming: false })).toBe('LISTENING')
    expect(deriveLiveStatus({ ...base, qa: { answer: '' }, streaming: true, questionAgeMs: 300 })).toBe('QUESTION_DETECTED')
    expect(deriveLiveStatus({ ...base, qa: { answer: '' }, streaming: true, questionAgeMs: 4000 })).toBe('PREPARING')
    expect(deriveLiveStatus({ ...base, qa: { answer: '', fastCue: cue }, streaming: true })).toBe('CUE_READY')
    expect(deriveLiveStatus({ ...base, qa: { answer: '结论是…', fastCue: cue }, streaming: true })).toBe('ANSWERING')
  })

  it('reports reconnecting and idle, and never exposes pipeline internals', () => {
    expect(deriveLiveStatus({ isRecording: true, wsConnected: false, qa: null, streaming: false })).toBe('RECONNECTING')
    expect(deriveLiveStatus({ isRecording: false, wsConnected: true, qa: null, streaming: false })).toBe('IDLE')
    const labels = Object.values(LIVE_STATUS_LABELS).join(' ')
    for (const internal of ['ASR', 'Retrieval', 'Compiler', 'LLM']) expect(labels).not.toContain(internal)
  })
})

describe('Overlay 3.0 effective size', () => {
  const layout = { dock: 'TOP' as const, interaction: 'PASSIVE' as const, size: 'STANDARD' as const, autoCompact: true }
  it('idles compact, expands when a cue arrives', () => {
    expect(effectiveOverlaySize(layout, false)).toBe('COMPACT')
    expect(effectiveOverlaySize(layout, true)).toBe('STANDARD')
    expect(effectiveOverlaySize({ ...layout, size: 'FOCUS' }, true)).toBe('FOCUS')
    expect(effectiveOverlaySize({ ...layout, autoCompact: false }, false)).toBe('STANDARD')
    expect(effectiveOverlaySize({ ...layout, size: 'COMPACT' }, true)).toBe('STANDARD')
  })
})
