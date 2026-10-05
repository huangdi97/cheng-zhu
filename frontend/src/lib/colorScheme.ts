/** 参考 VS Code 的配色方案 id（与 index.css / data-theme 一致） */
export const COLOR_SCHEME_IDS = [
  'vscode-light-plus',
  'vscode-dark-plus',
  'vscode-dark-hc',
  'nord',
  'editorial-glass',
  'solarized-dark',
] as const

export type ColorSchemeId = typeof COLOR_SCHEME_IDS[number]

/** localStorage key，与 index.html 内联脚本一致 */
export const COLOR_SCHEME_STORAGE_KEY = 'ia-color-scheme'
export const DEFAULT_COLOR_SCHEME_ID: ColorSchemeId = 'vscode-light-plus'

export const COLOR_SCHEME_OPTIONS: { id: ColorSchemeId; label: string; hint: string }[] = [
  // IDs stay unchanged so existing localStorage/preferences migrate without
  // churn. Labels are product language, not implementation provenance.
  { id: 'vscode-light-plus', label: '成竹 · 浅色', hint: '默认：竹青 / 墨青专业工作台，适合日间准备与复盘' },
  { id: 'vscode-dark-plus', label: '成竹 · 深色', hint: '低亮度竹青深色工作台，适合夜间与长时间使用' },
  { id: 'vscode-dark-hc', label: '高对比', hint: '黑底高对比，面向低视力 / 强光场景' },
  { id: 'nord', label: 'Nord', hint: '北欧冷灰蓝，低饱和长时间作答不累眼' },
  { id: 'editorial-glass', label: 'Editorial Glass', hint: '纸感留白与玻璃层次，适合阅读' },
  { id: 'solarized-dark', label: 'Solarized Dark', hint: '经典暖黄护眼深色，弱蓝光夜间友好' },
]

export function isColorSchemeId(value: unknown): value is ColorSchemeId {
  return typeof value === 'string' && (COLOR_SCHEME_IDS as readonly string[]).includes(value)
}

export function resolveColorSchemeId(value: unknown): ColorSchemeId {
  return isColorSchemeId(value) ? value : DEFAULT_COLOR_SCHEME_ID
}

export function readStoredColorScheme(): ColorSchemeId {
  try {
    return resolveColorSchemeId(localStorage.getItem(COLOR_SCHEME_STORAGE_KEY))
  } catch {
    return DEFAULT_COLOR_SCHEME_ID
  }
}

export function applyColorSchemeToDocument(id: ColorSchemeId) {
  if (typeof document === 'undefined') return
  document.documentElement.setAttribute('data-theme', id)
}

export function applyStoredColorSchemeToDocument(): ColorSchemeId {
  const id = readStoredColorScheme()
  applyColorSchemeToDocument(id)
  return id
}

export function isLightColorScheme(id: ColorSchemeId): boolean {
  return id === 'vscode-light-plus' || id === 'editorial-glass'
}
