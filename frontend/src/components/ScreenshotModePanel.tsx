import { useState } from 'react'
import { MonitorSmartphone, AlertTriangle, Crop } from 'lucide-react'
import { useInterviewStore } from '@/stores/configStore'
import { useShallow } from 'zustand/react/shallow'
import { api, getErrorMessage } from '@/lib/api'
import AnswerPanel from './AnswerPanel'

interface Props {
  serverScreenLoading: boolean
  onAsk: () => void
}

export default function ScreenshotModePanel({ serverScreenLoading, onAsk }: Props) {
  const activeModel = useInterviewStore(
    useShallow((s) => {
      const m = s.config?.models?.[s.config?.active_model ?? 0]
      return m
    }),
  )
  const hasVision = activeModel?.supports_vision === true
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [regionLoading, setRegionLoading] = useState(false)

  const handleRegionAsk = async () => {
    if (!window.electronAPI?.captureRegion) {
      pushToast('框选截图仅在桌面端可用', 'warn')
      return
    }
    setRegionLoading(true)
    try {
      const region = await window.electronAPI.captureRegion()
      if (!region) return
      await api.askFromServerScreenRegion(region)
      pushToast('已按框选区域提交截图审题', 'success')
    } catch (err) {
      pushToast(getErrorMessage(err, '框选截图失败'), 'error')
    } finally {
      setRegionLoading(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <div className="max-w-3xl mx-auto space-y-4">
          <div className="rounded-2xl border border-bg-hover/50 bg-bg-secondary p-5">
            <div className="flex items-center gap-2 mb-2">
              <MonitorSmartphone className="h-5 w-5 text-accent-blue" />
              <h3 className="text-base font-bold text-text-primary">截图模式</h3>
            </div>
            <p className="text-sm text-text-secondary leading-relaxed">
              适用于笔试、机考、代码/架构图题：截取题目后，AI 识别题意并给出结构化解法
              （题目理解 → 方案 → 复杂度 → 测试用例）。
            </p>

            {!hasVision && (
              <div className="mt-3 flex items-start gap-2 rounded-xl bg-accent-red/10 border border-accent-red/30 p-3 text-[13px] text-accent-red">
                <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <span>当前模型不支持识图。请在「设置 → 模型」添加支持视觉的模型（如 qwen-vl、GPT-4o），并设为优先，截图解题才能真正识别图片。</span>
              </div>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={serverScreenLoading || !hasVision}
                onClick={onAsk}
                className="inline-flex items-center gap-2 rounded-xl bg-accent-blue px-5 py-2.5 text-sm font-semibold text-white shadow-sm shadow-accent-blue/20 hover:bg-accent-blue/90 disabled:opacity-50"
              >
                <MonitorSmartphone className="h-4 w-4" />
                {serverScreenLoading ? '截图审题提交中…' : '截图审题'}
              </button>
              <button
                type="button"
                disabled={regionLoading || !hasVision}
                onClick={() => void handleRegionAsk()}
                className="inline-flex items-center gap-2 rounded-xl border border-accent-blue/40 bg-accent-blue/10 px-5 py-2.5 text-sm font-semibold text-accent-blue hover:bg-accent-blue/20 disabled:opacity-50"
              >
                <Crop className="h-4 w-4" />
                {regionLoading ? '框选中…' : '框选截图'}
              </button>
            </div>
            <p className="text-[11px] text-text-muted mt-2 leading-snug">
              「截图审题」按配置的区域截取主屏；「框选截图」（桌面端）会弹出透明遮罩，按住左键拖选题目区域后自动提交。
              需先配置识图模型与屏幕录制权限。
            </p>
          </div>

          <AnswerPanel />
        </div>
      </div>
    </div>
  )
}
