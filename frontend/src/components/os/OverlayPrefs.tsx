/** Overlay 3.0 settings: Dock × Interaction × Size (+ auto compact). */
import { useOverlayLayout, type OverlayDock, type OverlayInteraction, type OverlaySize } from '@/stores/overlayLayoutStore'

function Radio<T extends string>({ legend, value, options, onChange }: { legend: string; value: T; options: Array<[T, string, string?]>; onChange: (v: T) => void }) {
  return (
    <fieldset className="py-2">
      <legend className="text-xs font-medium text-text-secondary">{legend}</legend>
      <div role="radiogroup" aria-label={legend} className="mt-1 flex flex-wrap gap-1.5">
        {options.map(([k, label, hint]) => (
          <button key={k} type="button" role="radio" aria-checked={value === k} title={hint} onClick={() => onChange(k)}
            className={`rounded-full border px-3 py-1 text-xs ${value === k ? 'border-accent-blue/50 bg-container-primary text-container-on-primary font-semibold' : 'border-bg-hover text-text-secondary hover:text-text-primary'}`}>
            {label}
          </button>
        ))}
      </div>
    </fieldset>
  )
}

export default function OverlayPrefs() {
  const layout = useOverlayLayout()
  return (
    <div data-testid="overlay-prefs">
      <h3 className="text-sm font-semibold text-text-primary">浮窗</h3>
      <Radio<OverlayDock> legend="停靠" value={layout.dock} onChange={(v) => layout.setLayout({ dock: v })}
        options={[['TOP', '顶部'], ['LEFT', '左侧'], ['RIGHT', '右侧'], ['FREE', '自由位置']]} />
      <Radio<OverlayInteraction> legend="交互" value={layout.interaction} onChange={(v) => layout.setLayout({ interaction: v })}
        options={[['PASSIVE', '穿透（点击落到下面的会议软件）'], ['INTERACTIVE', '可点击']]} />
      <Radio<OverlaySize> legend="大小" value={layout.size} onChange={(v) => layout.setLayout({ size: v })}
        options={[['COMPACT', '紧凑'], ['STANDARD', '标准'], ['FOCUS', '专注']]} />
      <label className="flex items-center gap-2 py-2 text-xs text-text-primary">
        <input type="checkbox" checked={layout.autoCompact} onChange={(e) => layout.setLayout({ autoCompact: e.target.checked })} />
        空闲时自动收起为一行，出现 Cue 时自动展开
      </label>
      <p className="text-[11px] text-text-muted">按显示器工作区停靠，多屏和高 DPI 下保持在屏幕内。透明度、字号等外观设置在「通用 → 工作模式」。</p>
    </div>
  )
}
