import { beforeEach, describe, expect, it } from 'vitest'
import { useInterviewStore } from './configStore'

// v1.2-R2 latency closure: the Fast Cue renders when it arrives, not when the
// deep answer's answer_start (after the late-constraint grace) creates the card.
describe('Fast Cue renders on arrival', () => {
  beforeEach(() => {
    useInterviewStore.setState({
      qaPairs: [],
      streamingIds: [],
      currentStreamingId: null,
    } as any)
  })

  it('creates the card from a cue that carries its question', () => {
    useInterviewStore.getState().setFastCue('qa-p1', { question: 'Redis 的持久化机制有哪些？', provisional: true })
    const qa = useInterviewStore.getState().qaPairs[0]
    expect(qa.id).toBe('qa-p1')
    expect(qa.question).toBe('Redis 的持久化机制有哪些？')
    expect(qa.fastCue).toMatchObject({ provisional: true })
    expect(useInterviewStore.getState().streamingIds).toEqual([])
  })

  it('answer_start fills the same card and keeps the cue', () => {
    const store = useInterviewStore.getState()
    store.setFastCue('qa-p1', { question: '消息队列怎么保证不丢消息？' })
    store.startAnswer('qa-p1', '消息队列怎么保证不丢消息？')
    const state = useInterviewStore.getState()
    expect(state.qaPairs).toHaveLength(1)
    expect(state.streamingIds).toEqual(['qa-p1'])
    expect(state.qaPairs[0].fastCue).toMatchObject({ question: '消息队列怎么保证不丢消息？' })
  })

  it('a reconciled cue replaces question and cue in place (no second card)', () => {
    const store = useInterviewStore.getState()
    store.setFastCue('qa-p1', { question: '如果数据扩大一百倍会怎么样？', provisional: true })
    store.setFastCue('qa-p1', { question: '如果数据扩大一百倍，你会怎么设计缓存？', reconciled: 'corrected' })
    const state = useInterviewStore.getState()
    expect(state.qaPairs).toHaveLength(1)
    expect(state.qaPairs[0].question).toBe('如果数据扩大一百倍，你会怎么设计缓存？')
    expect(state.qaPairs[0].fastCue).toMatchObject({ reconciled: 'corrected' })
  })

  it('retract removes a cue-only card but never a card whose answer started', () => {
    const store = useInterviewStore.getState()
    store.setFastCue('qa-p1', { question: '讲讲你的项目。' })
    store.setFastCue('qa-p2', { question: '为什么选择 Kafka？' })
    store.startAnswer('qa-p2', '为什么选择 Kafka？')
    store.retractFastCue('qa-p1')
    store.retractFastCue('qa-p2')
    expect(useInterviewStore.getState().qaPairs.map((qa) => qa.id)).toEqual(['qa-p2'])
  })

  it('a legacy cue without a question still waits for answer_start', () => {
    const store = useInterviewStore.getState()
    store.setFastCue('qa-1', { direction: 'x' })
    expect(useInterviewStore.getState().qaPairs).toHaveLength(0)
    store.startAnswer('qa-1', 'q')
    expect(useInterviewStore.getState().qaPairs[0].fastCue).toMatchObject({ direction: 'x' })
  })
})
