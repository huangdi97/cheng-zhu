const INTERVIEW_ROUND_LABELS: Record<string, string> = {
  TECHNICAL: '技术面',
  PROJECT_DEEP_DIVE: '项目深挖',
  SYSTEM_DESIGN: '系统设计',
  HIRING_MANAGER: 'Hiring Manager',
  HR: 'HR',
  BEHAVIORAL: '行为面',
  PRODUCT_CASE: '产品 / Case',
}

export function formatInterviewRound(value?: string | null): string {
  if (!value) return ''
  return INTERVIEW_ROUND_LABELS[value] ?? value.replaceAll('_', ' ')
}
