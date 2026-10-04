import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, CircleAlert, Loader2 } from 'lucide-react'
import { api, getErrorMessage } from '@/lib/api'
import { updateConfigAndRefresh } from '@/lib/configSync'
import { useInterviewStore } from '@/stores/configStore'
import { SHARE_PRIVACY_COPY } from '@/components/settings/PolicyPrivacySection'
import { productApi } from '@/lib/productApi'
import GuidedFirstPractice from './GuidedFirstPractice'

// v1.3 首次运行引导。前十步配置真实环境，第十一步只有在跑通一次
// Guided First Practice 后才允许正常完成；用户仍可显式「跳过引导」。
// 1 欢迎 2 本地数据 3 模型 4 语音识别 5 麦克风 6 系统音频
// 7 共享隐私 8 简历 9 第一个目标 10 第一次演练 11 完成

interface Diagnostics {
  packaged: boolean
  data_home: string
  data_dir: string
  logs_dir: string
  data_writable: boolean
  models: Array<{ index: number; name: string; model: string; has_key: boolean; enabled: boolean }>
  has_usable_model: boolean
  stt_provider: string
  audio: { devices: Array<{ id: number; name: string; is_loopback: boolean }>; error?: string; explain?: Explained; platform?: { instructions?: string } }
  has_microphone: boolean
  has_system_audio: boolean
}

interface Explained {
  kind: string
  cause: string
  action: string
}

const STEPS = ['欢迎', '本地数据', '模型', '语音识别', '麦克风', '系统音频', '共享隐私', '简历', '第一个目标', '第一次演练', '完成'] as const

function Status({ ok, label, explain }: { ok: boolean | null; label: string; explain?: Explained | null }) {
  return (
    <div className="rounded-xl border border-bg-hover/60 bg-bg-tertiary/20 p-3 text-sm">
      <div className="flex items-center gap-2">
        {ok === null ? <Loader2 className="w-4 h-4 animate-spin text-text-muted" aria-hidden />
          : ok ? <CheckCircle2 className="w-4 h-4 text-status-direct" aria-hidden />
            : <CircleAlert className="w-4 h-4 text-status-risk" aria-hidden />}
        <span className={ok === false ? 'text-status-risk font-medium' : 'text-text-primary'}>{label}</span>
      </div>
      {explain && (
        <p className="mt-1 pl-6 text-xs text-text-secondary">原因：{explain.cause}。下一步：{explain.action}</p>
      )}
    </div>
  )
}

async function explain(detail: string): Promise<Explained | null> {
  try {
    return await api.intelExplainError(detail)
  } catch {
    return null
  }
}

function DeviceTest({ devices, kind }: { devices: Diagnostics['audio']['devices']; kind: 'mic' | 'loopback' }) {
  const [deviceId, setDeviceId] = useState<number | null>(devices[0]?.id ?? null)
  const [result, setResult] = useState<{ ok: boolean; text: string; explain?: Explained | null } | null>(null)
  const [busy, setBusy] = useState(false)
  if (!devices.length) {
    return <Status ok={false} label={kind === 'mic' ? '没有检测到麦克风' : '没有检测到系统音频（回环）设备'} explain={{ kind: 'no_device', cause: '没有可用的音频设备', action: kind === 'mic' ? '连接麦克风或耳机后重新打开引导' : '在 Windows 上确认有正在使用的扬声器/耳机输出' }} />
  }
  const run = async () => {
    if (deviceId == null) return
    setBusy(true)
    try {
      const r = await api.audioInputTest(deviceId, 1.5)
      setResult({ ok: r.has_signal, text: r.has_signal ? `检测到信号（峰值 ${r.peak.toFixed(3)}）` : kind === 'mic' ? '没有检测到声音：请对着麦克风说话后重试' : '没有检测到声音：请播放一段音频后重试' })
    } catch (error) {
      const msg = getErrorMessage(error, '测试失败')
      setResult({ ok: false, text: msg, explain: await explain(msg) })
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="space-y-2">
      <select aria-label={kind === 'mic' ? '选择麦克风' : '选择系统音频设备'} value={deviceId ?? ''} onChange={(e) => setDeviceId(Number(e.target.value))}
        className="w-full rounded-lg border border-bg-hover bg-bg-secondary px-2 py-1.5 text-sm text-text-primary">
        {devices.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
      </select>
      <button type="button" onClick={() => void run()} disabled={busy}
        className="rounded-lg border border-bg-hover px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-bg-hover/60 disabled:opacity-50">
        {busy ? '测试中…' : kind === 'mic' ? '测试麦克风（说一句话）' : '测试系统音频（播放声音）'}
      </button>
      {result && <Status ok={result.ok} label={result.text} explain={result.explain} />}
    </div>
  )
}

export default function OnboardingWizard() {
  const config = useInterviewStore((s) => s.config)
  const openModelsDrawer = useInterviewStore((s) => s.openModelsDrawer)
  const toggleSettings = useInterviewStore((s) => s.toggleSettings)
  const setSettingsDrawerTab = useInterviewStore((s) => s.setSettingsDrawerTab)
  const pushToast = useInterviewStore((s) => s.pushToast)
  const [step, setStep] = useState(0)
  const [diag, setDiag] = useState<Diagnostics | null>(null)
  const [modelCheck, setModelCheck] = useState<{ ok: boolean | null; label: string; explain?: Explained | null } | null>(null)
  const [sttCheck, setSttCheck] = useState<{ ok: boolean | null; label: string; explain?: Explained | null } | null>(null)
  const [share, setShare] = useState('OFF')
  const [goalCompany, setGoalCompany] = useState('')
  const [goalRole, setGoalRole] = useState('')
  const [jd, setJd] = useState('')
  const [createdGoalId, setCreatedGoalId] = useState<string | null>(null)
  const [guidedComplete, setGuidedComplete] = useState(false)
  const [resumeName, setResumeName] = useState('')
  const [dismissed, setDismissed] = useState(false)
  const markGuidedComplete = useCallback(() => setGuidedComplete(true), [])

  const open = config?.onboarding_completed === false && !dismissed

  const loadDiag = useCallback(() => {
    api.intelDiagnostics().then((d) => setDiag(d as unknown as Diagnostics)).catch(() => setDiag(null))
  }, [])
  useEffect(() => { if (open) loadDiag() }, [open, loadDiag])

  if (!open) return null

  const finish = async () => {
    try {
      await updateConfigAndRefresh({ onboarding_completed: true })
    } catch (error) {
      pushToast(getErrorMessage(error, '保存失败'), 'error')
    }
    setDismissed(true)
  }

  const testModel = async () => {
    const target = diag?.models.find((m) => m.has_key && m.enabled)
    if (!target) {
      setModelCheck({ ok: false, label: '还没有填写可用的 API Key', explain: { kind: 'auth', cause: '未配置模型', action: '点击「打开模型设置」填写服务商、模型名和 API Key。' } })
      return
    }
    setModelCheck({ ok: null, label: '正在连接…' })
    try {
      await api.checkSingleModelHealth(target.index)
      const h = await api.getModelsHealth()
      const key = String(target.index)
      const status = h.health?.[key] ?? ''
      const detail = h.detail?.[key] ?? ''
      const ok = /ok|available|可用|healthy/i.test(status) && !/不可用|unavailable|error/i.test(status)
      setModelCheck({ ok, label: ok ? `${target.name} 连接正常${h.latency?.[key] != null ? ` · ${h.latency[key]}ms` : ''}` : `${target.name} 不可用`, explain: ok ? null : await explain(`${status} ${detail}`) })
    } catch (error) {
      const msg = getErrorMessage(error, '连接失败')
      setModelCheck({ ok: false, label: msg, explain: await explain(msg) })
    }
  }

  const testStt = async () => {
    setSttCheck({ ok: null, label: '正在测试识别…' })
    try {
      const r = await api.sttTest()
      setSttCheck({ ok: r.ok, label: r.ok ? `识别可用${r.text ? `：「${r.text}」` : ''}` : r.detail || '识别失败', explain: r.ok ? null : await explain(r.detail || '') })
    } catch (error) {
      const msg = getErrorMessage(error, '识别失败')
      setSttCheck({ ok: false, label: msg, explain: await explain(msg) })
    }
  }

  const onResume = async (file: File | undefined) => {
    if (!file) return
    try {
      await api.uploadResume(file)
      setResumeName(file.name)
    } catch (error) {
      pushToast(getErrorMessage(error, '上传失败'), 'error')
    }
  }

  const createGoal = async () => {
    if (!goalCompany.trim() && !goalRole.trim()) return true
    if (!goalRole.trim()) {
      pushToast('请填写目标岗位；公司可以暂时留空', 'warning')
      return false
    }
    try {
      const goal = await productApi.createGoal({
        company: goalCompany.trim(),
        role: goalRole.trim(),
        jd,
        stage: '准备中',
        interview_round: '',
      })
      setCreatedGoalId(goal.id)
      return true
    } catch (error) {
      pushToast(getErrorMessage(error, '创建求职目标失败'), 'error')
      return false
    }
  }

  const next = async () => {
    if (STEPS[step] === '共享隐私') await updateConfigAndRefresh({ share_privacy_mode: share })
    if (STEPS[step] === '第一个目标' && !(await createGoal())) return
    if (STEPS[step] === '第一次演练' && !guidedComplete) return
    setStep((s) => Math.min(STEPS.length - 1, s + 1))
  }

  const mics = (diag?.audio.devices ?? []).filter((d) => !d.is_loopback)
  const loops = (diag?.audio.devices ?? []).filter((d) => d.is_loopback)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="onboarding-title" data-testid="onboarding">
      <div className="w-full max-w-xl rounded-2xl bg-bg-secondary shadow-xl">
        <div className="border-b border-bg-hover/60 px-5 py-4">
          <p className="text-[11px] text-text-muted">第 {step + 1} / {STEPS.length} 步</p>
          <h2 id="onboarding-title" className="text-lg font-semibold text-text-primary">{STEPS[step]}</h2>
          <ol className="mt-2 flex gap-1" aria-hidden>
            {STEPS.map((s, i) => <li key={s} className={`h-1 flex-1 rounded-full ${i <= step ? 'bg-accent-blue' : 'bg-bg-hover'}`} />)}
          </ol>
        </div>
        <div className="max-h-[60vh] overflow-y-auto px-5 py-4 space-y-3 text-sm text-text-secondary">
          {step === 0 && (
            <>
              <p>成竹是一个本机运行的面试准备与实时提示工具：先把你的真实经历整理成有来源的事实，按岗位准备和演练，上场时先给简短 Cue，再按需展开完整回答。</p>
              <p className="text-xs text-text-muted">开源（MIT License）。请只在允许使用辅助工具的场合使用实时提示；演练和复盘不受限制。</p>
            </>
          )}
          {step === 1 && (
            <>
              <p>你的简历、事实、面试记录和配置只保存在这台电脑上，不会上传到成竹的服务器（成竹没有服务器）。调用模型时，问题和必要上下文会发给你自己配置的服务商。</p>
              <Status ok={diag ? diag.data_writable : null} label={diag ? `数据目录：${diag.data_home}` : '检查中…'} />
              {diag && <p className="text-xs text-text-muted">日志：{diag.logs_dir}</p>}
            </>
          )}
          {step === 2 && (
            <>
              <p>成竹使用你自己的模型服务（BYOK）。填写服务商地址、模型名和 API Key 后测试连接。</p>
              <div className="flex gap-2">
                <button type="button" onClick={() => openModelsDrawer()} className="rounded-lg border border-bg-hover px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-bg-hover/60">打开模型设置</button>
                <button type="button" onClick={() => { loadDiag(); void testModel() }} className="rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white">测试连接</button>
              </div>
              {modelCheck && <Status ok={modelCheck.ok} label={modelCheck.label} explain={modelCheck.explain} />}
            </>
          )}
          {step === 3 && (
            <>
              <p>语音识别把面试官的话转成文字。当前引擎：<strong>{diag?.stt_provider || '未知'}</strong>。本地 Whisper 首次使用需要下载模型。</p>
              <div className="flex gap-2">
                <button type="button" onClick={() => { setSettingsDrawerTab('config'); toggleSettings() }} className="rounded-lg border border-bg-hover px-3 py-1.5 text-xs font-medium text-text-secondary hover:bg-bg-hover/60">打开语音设置</button>
                <button type="button" onClick={() => void testStt()} className="rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white">测试识别</button>
              </div>
              {sttCheck && <Status ok={sttCheck.ok} label={sttCheck.label} explain={sttCheck.explain} />}
            </>
          )}
          {step === 4 && (
            <>
              <p>麦克风用来记录你自己的回答（用于复盘和演练）。</p>
              {diag ? <DeviceTest devices={mics} kind="mic" /> : <Status ok={null} label="检测设备中…" />}
              {diag?.audio.error && <Status ok={false} label={diag.audio.error} explain={diag.audio.explain} />}
            </>
          )}
          {step === 5 && (
            <>
              <p>系统音频用来听会议软件里面试官的声音（Windows 通过扬声器回环采集，不需要额外驱动）。</p>
              {diag ? <DeviceTest devices={loops} kind="loopback" /> : <Status ok={null} label="检测设备中…" />}
              {diag?.audio.platform?.instructions && <p className="text-xs text-text-muted whitespace-pre-line">{diag.audio.platform.instructions}</p>}
            </>
          )}
          {step === 6 && (
            <fieldset className="space-y-2">
              <legend className="text-text-primary">共享隐私默认值</legend>
              {[['OFF', '关闭（推荐默认）'], ['PRIVATE_OVERLAY', '私有悬浮窗']].map(([v, l]) => (
                <label key={v} className="flex items-center gap-2 text-text-primary">
                  <input type="radio" name="share" value={v} checked={share === v} onChange={() => setShare(v)} />{l}
                </label>
              ))}
              <p className="text-xs text-text-muted">{SHARE_PRIVACY_COPY}</p>
            </fieldset>
          )}
          {step === 7 && (
            <>
              <p>导入简历后，成竹会抽取事实并标注来源。你可以在「我的成竹 → 待确认」里确认、否认或补来源。</p>
              <input type="file" accept=".pdf,.docx,.txt,.md" aria-label="选择简历文件" onChange={(e) => void onResume(e.target.files?.[0])}
                className="block w-full text-xs text-text-secondary" />
              {resumeName && <Status ok label={`已导入：${resumeName}`} />}
            </>
          )}
          {step === 8 && (
            <>
              <p>建第一个求职目标。之后的准备、练习、上场和复盘都会围绕这个 Goal 连起来。</p>
              <div className="grid gap-2 sm:grid-cols-2">
                <input aria-label="目标公司" value={goalCompany} onChange={(e) => setGoalCompany(e.target.value)} placeholder="例如：MindRank"
                  className="w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1.5 text-sm text-text-primary" />
                <input aria-label="目标岗位" value={goalRole} onChange={(e) => setGoalRole(e.target.value)} placeholder="例如：AIDD Agent Engineer"
                  className="w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1.5 text-sm text-text-primary" />
              </div>
              <textarea aria-label="岗位 JD" rows={4} value={jd} onChange={(e) => setJd(e.target.value)} placeholder="粘贴 JD（可选）"
                className="w-full rounded-lg border border-bg-hover bg-bg-primary px-2 py-1.5 text-sm text-text-primary" />
              {createdGoalId ? <Status ok label="第一个求职目标已创建" /> : null}
            </>
          )}
          {step === 9 && (
            <GuidedFirstPractice goalId={createdGoalId} onCompleted={markGuidedComplete} />
          )}
          {step === 10 && (
            <>
              <p>准备好了。之后只记住一条路径：打开 Goal → 看 Next Focus → 准备或练习 → 上场 → Reflection → 下一步。</p>
              <p className="text-xs text-text-muted">系统的复杂度留在后台；你下一步该做什么应该始终很清楚。所有默认值都可以在「设置」里调整。</p>
            </>
          )}
        </div>
        <div className="flex items-center justify-between border-t border-bg-hover/60 px-5 py-3">
          <button type="button" onClick={() => void finish()} className="text-xs text-text-muted hover:text-text-primary">跳过引导</button>
          <div className="flex gap-2">
            {step > 0 && (
              <button type="button" onClick={() => setStep((s) => s - 1)} className="rounded-lg border border-bg-hover px-3 py-1.5 text-xs font-medium text-text-secondary">上一步</button>
            )}
            {step < STEPS.length - 1 ? (
              <button type="button" onClick={() => void next()} disabled={STEPS[step] === '第一次演练' && !guidedComplete}
                className="rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-40">
                {STEPS[step] === '第一次演练' && !guidedComplete ? '先完成这次演练' : '下一步'}
              </button>
            ) : (
              <button type="button" onClick={() => void finish()} className="rounded-lg bg-accent-blue px-3 py-1.5 text-xs font-medium text-white">进入成竹</button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
