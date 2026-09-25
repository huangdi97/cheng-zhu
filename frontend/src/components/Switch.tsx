interface SwitchProps {
  checked: boolean
  onChange: (v: boolean) => void
  label?: string
  disabled?: boolean
}

/** 统一开关：36x20 圆角轨道 + 白圆钮；开启=语义绿+微光；role=switch 键盘可达。 */
export default function Switch({ checked, onChange, label, disabled }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex w-9 h-5 items-center rounded-full transition-colors duration-200 disabled:opacity-50 focus-visible:outline-none ${
        checked
          ? 'bg-accent-green shadow-[0_0_10px_-2px] shadow-accent-green/50'
          : 'bg-bg-hover'
      }`}
    >
      <span
        className={`absolute top-[2px] left-[2px] h-4 w-4 rounded-full bg-white shadow-sm transition-transform duration-200 ${checked ? 'translate-x-4' : ''}`}
        aria-hidden
      />
    </button>
  )
}
