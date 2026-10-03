/**
 * v1.3 UI Language layer (canonical §16): affects interface text only —
 * never ASR (Interview Language) or answers (Answer Language).
 * Covers the shell (navigation, global actions, page titles); page bodies
 * stay in Chinese until translated.
 */
import { useInterviewStore } from '@/stores/configStore'

export type UiLanguage = 'zh-CN' | 'en-US'

const STRINGS = {
  'nav.home': ['首页', 'Home'],
  'nav.goals': ['求职目标', 'Goals'],
  'nav.me': ['我的成竹', 'Me'],
  'nav.practice': ['练习', 'Practice'],
  'nav.library': ['资料库', 'Library'],
  'nav.history': ['历史', 'History'],
  'nav.settings': ['设置', 'Settings'],
  'nav.label': ['主导航', 'Main navigation'],
  'action.goLive': ['上场', 'Go Live'],
  'action.commands': ['命令面板', 'Command palette'],
  'action.minimize': ['最小化窗口', 'Minimize window'],
  'action.quit': ['退出应用', 'Quit'],
  'action.modules': ['切换功能模块', 'Switch section'],
  'loading': ['加载中…', 'Loading…'],
} as const

export type StringKey = keyof typeof STRINGS

export function translate(key: StringKey, lang: UiLanguage): string {
  const pair = STRINGS[key]
  return lang === 'en-US' ? pair[1] : pair[0]
}

export function useUiLanguage(): UiLanguage {
  return useInterviewStore((s) => (s.config?.ui_language === 'en-US' ? 'en-US' : 'zh-CN'))
}

export function useT(): (key: StringKey) => string {
  const lang = useUiLanguage()
  return (key) => translate(key, lang)
}
