import { useState } from 'react'

import { api } from '@/lib/api'

type ExpoReport = Awaited<ReturnType<typeof api.privacyExposure>>

// 本机暴露自检：直接把磁盘上还明文的产物列出来，而不是替用户猜。
// 结果只描述这一刻的事实；磁盘加密状态读不到时显示"未知"，不当作通过。
export default function ExposureCheck() {
  const [status, setStatus] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [report, setReport] = useState<ExpoReport | null>(null)
  const [error, setError] = useState('')

  const run = async () => {
    setStatus('loading')
    setError('')
    try {
      setReport(await api.privacyExposure())
      setStatus('done')
    } catch (e) {
      setError(e instanceof Error ? e.message : '自检失败')
      setStatus('error')
    }
  }

  const disk = report?.disk_encryption.protected
  const diskLabel = disk === true ? '磁盘加密已开' : disk === false ? '磁盘加密未开' : '磁盘加密未知'
  const summary = report
    ? `${report.resume_uploads.protected}/${report.resume_uploads.total} 份原件已加密 · ${report.resume_rows.protected}/${report.resume_rows.total} 条文本已加密 · ${diskLabel}`
    : ''

  return (
    <div className="rounded-lg border border-bg-hover/60 bg-bg-primary/40 px-3 py-2">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium text-text-secondary">本机暴露自检</p>
          <p className="mt-1 text-[10px] leading-4 text-text-muted" data-testid="exposure-summary">
            {status === 'idle' && '尚未检查。检查会读取本地数据目录，不会上传任何内容。'}
            {status === 'loading' && '检查中…'}
            {status === 'error' && error}
            {status === 'done' && report && (report.gaps.length ? report.gaps.join(' · ') : '未发现明文简历产物')}
            {status === 'done' && report ? `　${summary}` : ''}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void run()}
          disabled={status === 'loading'}
          data-testid="exposure-check"
          className="shrink-0 rounded-lg border border-bg-hover px-2.5 py-1 text-[11px] font-medium text-text-secondary hover:bg-bg-hover/60 disabled:opacity-40"
        >
          {status === 'loading' ? '检查中' : '自检'}
        </button>
      </div>
    </div>
  )
}
