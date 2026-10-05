import type { MaterialState } from '@/lib/productApi'
import { StatusBadge } from './ui'

const LABEL: Record<MaterialState, [string, 'busy' | 'ok' | 'risk' | 'info']> = {
  PROCESSING: ['处理中', 'busy'],
  READY: ['就绪', 'ok'],
  FAILED: ['失败', 'risk'],
  REPLACING: ['替换中（旧版仍在用）', 'info'],
}

export function MaterialStateBadge({ state }: { state: MaterialState }) {
  const [label, tone] = LABEL[state]
  return <StatusBadge tone={tone}>{label}</StatusBadge>
}
