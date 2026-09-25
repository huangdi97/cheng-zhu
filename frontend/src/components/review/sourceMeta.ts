export type ReviewSourceMeta = {
  kind: 'assist' | 'manual' | 'written_exam'
  label: string
  detailLabel: string
  unit: string
  answerHeading: string
  emptyAnswer: string
  badgeClassName: string
}

export function isWrittenExamReview(source: string | null | undefined): boolean {
  return String(source || '').trim() === 'written_exam'
}

export function getReviewSourceMeta(source: string | null | undefined): ReviewSourceMeta {
  if (isWrittenExamReview(source)) {
    return {
      kind: 'written_exam',
      label: '笔试练习',
      detailLabel: '截图笔试复盘',
      unit: '题',
      answerHeading: '生成答案',
      emptyAnswer: '(未生成答案)',
      badgeClassName: 'border-accent-blue/25 bg-accent-blue/10 text-accent-blue',
    }
  }
  if (String(source || '').trim() === 'manual') {
    return {
      kind: 'manual',
      label: '手动导入',
      detailLabel: '手动复盘',
      unit: '轮',
      answerHeading: '候选人回答',
      emptyAnswer: '(未录制到回答)',
      badgeClassName: 'border-bg-hover bg-bg-tertiary/45 text-text-secondary',
    }
  }
  return {
    kind: 'assist',
    label: '实时面试',
    detailLabel: '面试复盘',
    unit: '轮',
    answerHeading: '候选人回答',
    emptyAnswer: '(未录制到回答)',
    badgeClassName: 'border-accent-blue/20 bg-accent-blue/10 text-accent-blue',
  }
}
