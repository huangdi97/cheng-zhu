/** Settings 3.0 catalog: ten groups + a searchable index of what lives where. */
export type SettingsGroup =
  | 'general'
  | 'models'
  | 'speech'
  | 'language'
  | 'live'
  | 'privacy'
  | 'knowledge'
  | 'shortcuts'
  | 'data'
  | 'diagnostics'

export const SETTINGS_GROUPS: Array<[SettingsGroup, string]> = [
  ['general', 'General'],
  ['models', 'Models'],
  ['speech', 'Speech & Audio'],
  ['language', 'Language'],
  ['live', 'Live & Overlay'],
  ['privacy', 'Privacy'],
  ['knowledge', 'Knowledge'],
  ['shortcuts', 'Shortcuts'],
  ['data', 'Data & Export'],
  ['diagnostics', 'Diagnostics'],
]

export const GROUP_LABEL_ZH: Record<SettingsGroup, string> = {
  general: '通用', models: '模型', speech: '语音与音频', language: '语言', live: '上场与浮窗',
  privacy: '隐私', knowledge: '知识库', shortcuts: '快捷键', data: '数据与导出', diagnostics: '诊断',
}

export interface CatalogEntry {
  key: string
  label: string
  group: SettingsGroup
  keywords: string[]
  layered?: boolean
}

export const CATALOG: CatalogEntry[] = [
  { key: 'color_scheme', label: '主题与配色', group: 'general', keywords: ['外观', '深色', '浅色', 'dark', 'light', 'theme', '字体'] },
  { key: 'answer_layout', label: '回答布局', group: 'general', keywords: ['卡片', '流式', 'layout'] },
  { key: 'onboarding', label: '重新运行引导', group: 'general', keywords: ['引导', 'onboarding', '首次'] },
  { key: 'models', label: '回答模型与 API Key', group: 'models', keywords: ['模型', 'api key', 'openai', 'deepseek', 'qwen', '优先'], layered: true },
  { key: 'fast_cue_model', label: 'Fast Cue 模型', group: 'models', keywords: ['cue', '快速提示', '延迟'] },
  { key: 'stt', label: '语音识别引擎', group: 'speech', keywords: ['stt', 'asr', 'whisper', '豆包', '识别'] },
  { key: 'devices', label: '麦克风与系统音频', group: 'speech', keywords: ['麦克风', '音频', '设备', 'loopback', '声音'] },
  { key: 'vad', label: '断句与 VAD', group: 'speech', keywords: ['vad', '静音', '断句', '合并'] },
  { key: 'ui_language', label: '界面语言', group: 'language', keywords: ['ui', '界面', 'english', '中文'] },
  { key: 'whisper_language', label: '面试语言（识别）', group: 'language', keywords: ['面试语言', '识别语言', 'asr'], layered: true },
  { key: 'answer_language', label: '回答语言', group: 'language', keywords: ['回答语言', '跟随', 'english'], layered: true },
  { key: 'language', label: '编程语言', group: 'language', keywords: ['python', 'java', 'go', '编程'], layered: true },
  { key: 'technical_term_policy', label: '技术术语', group: 'language', keywords: ['术语', '英文', '翻译', '双语'], layered: true },
  { key: 'ai_policy_mode', label: 'AI 辅助', group: 'live', keywords: ['ai', '辅助', '策略'], layered: true },
  { key: 'human_assistance_policy', label: '真人辅助', group: 'live', keywords: ['教练', 'coach', '真人'], layered: true },
  { key: 'proactive_guidance_enabled', label: '主动提示（Nudge）', group: 'live', keywords: ['nudge', '提示', '主动'], layered: true },
  { key: 'overlay', label: '浮窗（停靠 / 交互 / 大小）', group: 'live', keywords: ['浮窗', 'overlay', 'compact', 'focus', '停靠'] },
  { key: 'share_privacy_mode', label: '共享隐私', group: 'privacy', keywords: ['共享', '录屏', '隐私', 'share'], layered: true },
  { key: 'speech_adoption_analytics_live', label: 'Live 表达分析', group: 'privacy', keywords: ['表达', '分析', 'delivery'], layered: true },
  { key: 'practice_delivery_analytics_enabled', label: '练习本地表达分析', group: 'privacy', keywords: ['练习', '表达', '语速'] },
  { key: 'remote_telemetry_opt_in', label: '远程遥测（默认关闭）', group: 'privacy', keywords: ['遥测', 'telemetry', '统计'] },
  { key: 'local_analytics', label: '本地产品分析', group: 'privacy', keywords: ['分析', '事件', 'analytics'] },
  { key: 'kb_enabled', label: '知识库检索', group: 'knowledge', keywords: ['知识库', 'kb', '检索', '引用'], layered: true },
  { key: 'shortcuts', label: '全局快捷键', group: 'shortcuts', keywords: ['快捷键', 'ctrl', 'shortcut', '热键'] },
  { key: 'export', label: '导出数据', group: 'data', keywords: ['导出', '备份', 'export', '删除'] },
  { key: 'integrity', label: '数据完整性检查', group: 'data', keywords: ['完整性', '修复', 'integrity'] },
  { key: 'system_status', label: '系统状态（模型 / 知识库 / 简历 / CPU）', group: 'diagnostics', keywords: ['状态', 'cpu', '诊断', '日志'] },
  { key: 'validation', label: '产品循环验证（v1.4）', group: 'diagnostics', keywords: ['验证', 'validation', '指标'] },
]

export function searchCatalog(query: string): CatalogEntry[] {
  const q = query.trim().toLowerCase()
  if (!q) return []
  return CATALOG.filter((e) => [e.key, e.label, GROUP_LABEL_ZH[e.group], e.group, ...e.keywords].join(' ').toLowerCase().includes(q))
}
