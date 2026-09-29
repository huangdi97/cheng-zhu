import { Info, ShieldCheck } from 'lucide-react'
import Switch from '@/components/Switch'
import { useInterviewStore } from '@/stores/configStore'
import { updateConfigAndRefresh } from '@/lib/configSync'
import { Field, Section } from './shared'

declare const __APP_VERSION__: string

// R2 Stage R/T/Y：三个互相独立的维度 + Live 语速/采纳分析 opt-in。
// 这里设置的是默认值；每场冻结 Interview Pack 时可单独覆盖，并随 Pack 固定。

const AI_OPTIONS: Array<[string, string]> = [
  ['AI_ALLOWED', 'AI 允许'],
  ['AI_EXPECTED', 'AI 鼓励'],
  ['AI_LIMITED', 'AI 受限（关闭自动回答）'],
  ['AI_FORBIDDEN', 'AI 禁止（关闭实时引导）'],
]
const HUMAN_OPTIONS: Array<[string, string]> = [
  ['HUMAN_PRACTICE_ONLY', '仅练习（默认）'],
  ['HUMAN_FORBIDDEN', '禁止'],
  ['HUMAN_ALLOWED', '允许（需面试方明确允许外部协助）'],
]

export const SHARE_PRIVACY_COPY =
  '用于减少成竹中的私人资料意外出现在受支持的屏幕共享或录制路径中。不同系统和捕获方式行为不同，这不是安全或“不可检测”保证。'

export default function PolicyPrivacySection() {
  const config = useInterviewStore((s) => s.config)
  const save = (patch: Record<string, unknown>) => { void updateConfigAndRefresh(patch) }
  const selectCls = 'w-full rounded-lg border border-bg-hover bg-bg-secondary px-2 py-1.5 text-xs text-text-primary'
  const version = typeof __APP_VERSION__ === 'string' ? __APP_VERSION__ : 'dev'

  return (
    <>
      <Section title="隐私与策略" icon={<ShieldCheck className="w-3.5 h-3.5" />} keywords="policy 策略 隐私 共享 人工 协助 ai share privacy human">
        <Field label="AI 使用策略（默认）" hint="服务端强制执行；AI 禁止时实时引导关闭，准备/演练/复盘不受影响。">
          <select aria-label="AI 使用策略" className={selectCls} value={config?.ai_policy_mode ?? 'AI_ALLOWED'}
            onChange={(e) => save({ ai_policy_mode: e.target.value })}>
            {AI_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <Field label="人工协助策略（默认）" hint="与 AI 策略独立：AI 允许不等于人工协助允许。默认只在演练/练习中可用。">
          <select aria-label="人工协助策略" className={selectCls} value={config?.human_assistance_policy ?? 'HUMAN_PRACTICE_ONLY'}
            onChange={(e) => save({ human_assistance_policy: e.target.value })}>
            {HUMAN_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </Field>
        <Field label="共享隐私（默认）" hint={SHARE_PRIVACY_COPY}>
          <select aria-label="共享隐私" className={selectCls} value={config?.share_privacy_mode ?? 'OFF'}
            onChange={(e) => save({ share_privacy_mode: e.target.value })}>
            <option value="OFF">关闭（默认）</option>
            <option value="PRIVATE_OVERLAY">私有悬浮窗</option>
          </select>
        </Field>
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-medium text-text-secondary">正式场次的语速 / cue 采纳分析</p>
            <p className="text-[10px] text-text-muted">默认关闭。开启后仅在本机分析，不上传，不用于“作弊检测”或“通过概率”。演练中默认开启。</p>
          </div>
          <Switch
            checked={Boolean(config?.speech_adoption_analytics_live)}
            onChange={(v: boolean) => save({ speech_adoption_analytics_live: v })}
            label="正式场次语速与采纳分析"
          />
        </div>
      </Section>

      <Section title="关于" icon={<Info className="w-3.5 h-3.5" />} keywords="about 关于 版本 license 许可 mit">
        <dl className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs">
          <dt className="text-text-muted">版本</dt>
          <dd className="text-text-primary font-mono">{version}</dd>
          <dt className="text-text-muted">许可证</dt>
          <dd className="text-text-primary">MIT License · 第三方组件保留各自许可（见 THIRD_PARTY_NOTICES.md）</dd>
          <dt className="text-text-muted">源码</dt>
          <dd className="text-text-primary">github.com/huangdi97/cheng-zhu</dd>
        </dl>
      </Section>
    </>
  )
}
