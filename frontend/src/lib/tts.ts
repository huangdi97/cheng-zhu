/**
 * TTS 语音播报：基于浏览器 SpeechSynthesis（Windows 自带中文语音，零依赖）。
 * 设置项存 localStorage（ia-tts-enabled / ia-tts-rate），避免后端改动。
 */
const ENABLED_KEY = 'ia-tts-enabled'
const RATE_KEY = 'ia-tts-rate'

export function isTtsEnabled(): boolean {
  try {
    return localStorage.getItem(ENABLED_KEY) === '1'
  } catch {
    return false
  }
}

export function setTtsEnabled(v: boolean): void {
  try {
    localStorage.setItem(ENABLED_KEY, v ? '1' : '0')
  } catch {
    /* ignore */
  }
}

export function getTtsRate(): number {
  try {
    const v = Number(localStorage.getItem(RATE_KEY) || 1)
    return Number.isFinite(v) && v >= 0.5 && v <= 2 ? v : 1
  } catch {
    return 1
  }
}

export function setTtsRate(v: number): void {
  try {
    localStorage.setItem(RATE_KEY, String(v))
  } catch {
    /* ignore */
  }
}

let _current: SpeechSynthesisUtterance | null = null

function pickVoice(): SpeechSynthesisVoice | null {
  if (typeof speechSynthesis === 'undefined') return null
  const voices = speechSynthesis.getVoices()
  if (!voices.length) return null
  const zh = voices.find((v) => v.lang?.toLowerCase().startsWith('zh'))
  return zh ?? null
}

export function speak(text: string): void {
  if (typeof speechSynthesis === 'undefined' || !text || !isTtsEnabled()) return
  try {
    speechSynthesis.cancel()
    const clean = text.replace(/[#*`>\[\]]+/g, ' ').replace(/\s+/g, ' ').trim()
    if (!clean) return
    const u = new SpeechSynthesisUtterance(clean.slice(0, 1200))
    const voice = pickVoice()
    if (voice) u.voice = voice
    u.lang = voice?.lang || 'zh-CN'
    u.rate = getTtsRate()
    _current = u
    speechSynthesis.speak(u)
  } catch {
    /* ignore */
  }
}

export function stopSpeaking(): void {
  if (typeof speechSynthesis === 'undefined') return
  try {
    speechSynthesis.cancel()
  } catch {
    /* ignore */
  }
  _current = null
}
