/**
 * Spoken practice answers through the existing local listen endpoints
 * (/api/prep/listen/*). Returns the transcript plus the measured duration so
 * the Delivery Coach can work with real timing instead of an estimate.
 * Audio stays on this machine.
 */
import { useCallback, useEffect, useState } from 'react'
import { api } from '@/lib/api'

export interface VoiceResult {
  text: string
  durationMs: number
}

export function useVoiceAnswer() {
  const [devices, setDevices] = useState<Array<{ id: number; name: string }>>([])
  const [deviceId, setDeviceId] = useState(0)
  const [recording, setRecording] = useState(false)
  const [liveText, setLiveText] = useState('')
  const [level, setLevel] = useState(0)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    api.getDevices().then((res: { devices?: Array<{ id: number; name: string; is_loopback?: boolean }> }) => {
      const inputs = (res?.devices ?? []).filter((d) => !d?.is_loopback)
      if (inputs.length) {
        setDevices(inputs)
        setDeviceId(Number(inputs[0].id))
      }
    }).catch(() => undefined)
  }, [])

  const record = useCallback(async (maxSeconds = 90): Promise<VoiceResult | null> => {
    if (recording) return null
    setRecording(true)
    setLiveText('')
    setMessage('正在听…（停顿 1–2 秒自动结束）')
    const started = performance.now()
    try {
      await api.prepListenStart(deviceId, maxSeconds)
      let done = false
      while (!done) {
        await new Promise((r) => setTimeout(r, 250))
        const st = await api.prepListenStatus()
        setLiveText(st.partial_text || st.final_text || '')
        setLevel(st.level ?? 0)
        if (st.done || !st.active) done = true
      }
      const res = await api.prepListenStop()
      const durationMs = Math.round(performance.now() - started)
      if (res.text) {
        setMessage('已识别，可以修改后提交')
        return { text: res.text, durationMs }
      }
      setMessage(res.heard_speech ? '没有识别出内容，请重试' : '没有听到声音：请确认麦克风设备后重试')
      return null
    } catch (e) {
      setMessage(e instanceof Error ? e.message : '录音失败')
      return null
    } finally {
      setRecording(false)
    }
  }, [deviceId, recording])

  return { devices, deviceId, setDeviceId, recording, liveText, level, message, record }
}
