import { describe, expect, it } from 'vitest'
import { buildGuidanceViewModel, EMPTY_GUIDANCE_VIEW_MODEL, isGlanceReady } from './guidanceViewModel'

// 与后端 answer_done 事件负载同构：question/answer + 延迟指标 + guidance 子对象。
const FULL_ANSWER_DONE_PAYLOAD = {
  question: '介绍一下 Redis 的持久化机制',
  answer: 'Redis 提供两种持久化方式：RDB 与 AOF……',
  think: '',
  model_name: 'Lite Ark',
  first_token_ms: 420,
  total_ms: 3100,
  guidance: {
    core_ideas: ['RDB 快照', 'AOF 追加日志', '混合持久化'],
    evidence: ['简历写过的缓存项目', 'JD 明确要求高并发经验'],
    mode: 'deep',
    intent: ['project_dig', 'followup'],
    resolved_question: 'Redis 的 RDB 与 AOF 两种持久化机制的取舍',
    state_context: '面试中段，已聊过项目缓存模块',
  },
}

describe('buildGuidanceViewModel', () => {
  it('maps a full answer_done payload into the view model fields', () => {
    const vm = buildGuidanceViewModel(FULL_ANSWER_DONE_PAYLOAD)
    expect(vm.question).toBe('介绍一下 Redis 的持久化机制')
    expect(vm.resolvedQuestion).toBe('Redis 的 RDB 与 AOF 两种持久化机制的取舍')
    expect(vm.coreIdeas).toEqual(['RDB 快照', 'AOF 追加日志', '混合持久化'])
    expect(vm.evidence).toEqual(['简历写过的缓存项目', 'JD 明确要求高并发经验'])
    expect(vm.mode).toBe('deep')
    expect(vm.intent).toEqual(['project_dig', 'followup'])
    expect(vm.stateContext).toBe('面试中段，已聊过项目缓存模块')
    expect(vm.firstTokenMs).toBe(420)
    expect(vm.totalMs).toBe(3100)
    expect(vm.hasAnswer).toBe(true)
  })

  it('keeps hasAnswer from the answer when guidance is missing or undefined', () => {
    const withoutGuidance = buildGuidanceViewModel({ question: 'Q1', answer: 'A1' })
    expect(withoutGuidance.coreIdeas).toEqual([])
    expect(withoutGuidance.evidence).toEqual([])
    expect(withoutGuidance.intent).toEqual([])
    expect(withoutGuidance.resolvedQuestion).toBe('')
    expect(withoutGuidance.mode).toBe('')
    expect(withoutGuidance.stateContext).toBe('')
    expect(withoutGuidance.hasAnswer).toBe(true)

    const undefinedGuidance = buildGuidanceViewModel({
      question: 'Q2',
      answer: '',
      guidance: undefined,
    })
    expect(undefinedGuidance.hasAnswer).toBe(false)
  })

  it('treats malformed guidance as absent while keeping top-level fields', () => {
    const vm = buildGuidanceViewModel({
      question: 'Q3',
      answer: 'A3',
      guidance: ['not', 'a', 'record'],
    })
    expect(vm.question).toBe('Q3')
    expect(vm.hasAnswer).toBe(true)
    expect(vm.coreIdeas).toEqual([])
    expect(vm.evidence).toEqual([])
  })

  it('returns an EMPTY-like model for malformed payloads without throwing', () => {
    for (const malformed of [null, undefined, 42, 'oops', ['x'], true]) {
      expect(buildGuidanceViewModel(malformed)).toEqual(EMPTY_GUIDANCE_VIEW_MODEL)
    }
  })

  it('filters non-string core_ideas entries and caps the list at 8', () => {
    const vm = buildGuidanceViewModel({
      question: 'Q',
      answer: 'A',
      guidance: {
        core_ideas: [
          'idea 1',
          42,
          null,
          { text: 'nope' },
          'idea 2',
          'idea 3',
          'idea 4',
          'idea 5',
          'idea 6',
          'idea 7',
          'idea 8',
          'idea 9 dropped',
        ],
      },
    })
    expect(vm.coreIdeas).toEqual([
      'idea 1',
      'idea 2',
      'idea 3',
      'idea 4',
      'idea 5',
      'idea 6',
      'idea 7',
      'idea 8',
    ])
    expect(vm.coreIdeas).toHaveLength(8)
  })

  it('caps evidence at 4 entries', () => {
    const vm = buildGuidanceViewModel({
      question: 'Q',
      answer: 'A',
      guidance: { evidence: ['e1', 'e2', 'e3', 'e4', 'e5 dropped'] },
    })
    expect(vm.evidence).toEqual(['e1', 'e2', 'e3', 'e4'])
  })

  it('nulls latency fields for non-finite or non-number values', () => {
    for (const bad of [NaN, Infinity, -Infinity, '420', null]) {
      const vm = buildGuidanceViewModel({ question: 'Q', answer: 'A', first_token_ms: bad, total_ms: bad })
      expect(vm.firstTokenMs).toBeNull()
      expect(vm.totalMs).toBeNull()
    }
  })

  it('treats blank answers as no answer', () => {
    expect(buildGuidanceViewModel({ question: 'Q', answer: '   ' }).hasAnswer).toBe(false)
    expect(buildGuidanceViewModel({ question: 'Q' }).hasAnswer).toBe(false)
  })
})

describe('isGlanceReady', () => {
  it('is false for the empty view model', () => {
    expect(isGlanceReady(EMPTY_GUIDANCE_VIEW_MODEL)).toBe(false)
  })

  it('is true when a question is present', () => {
    expect(isGlanceReady({ ...EMPTY_GUIDANCE_VIEW_MODEL, question: '当前问题' })).toBe(true)
  })

  it('is true with only core ideas and no question', () => {
    expect(isGlanceReady({ ...EMPTY_GUIDANCE_VIEW_MODEL, coreIdeas: ['核心思路'] })).toBe(true)
  })
})
