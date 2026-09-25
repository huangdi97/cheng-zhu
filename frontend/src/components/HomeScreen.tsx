import { useEffect, useState } from 'react'
import {
  BookOpenCheck,
  Radio,
  ArrowRight,
  ClipboardList,
  BrainCircuit,
  FileText,
  Kanban,
  Layers,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Briefcase,
  Mic,
} from 'lucide-react'
import { useUiPrefsStore } from '@/stores/uiPrefsStore'
import { useInterviewStore } from '@/stores/configStore'
import { useKbStore } from '@/stores/kbStore'
import { api } from '@/lib/api'

interface ModuleDef {
  mode: 'assist' | 'prep' | 'review' | 'knowledge' | 'resume-opt' | 'job-tracker'
  icon: typeof Radio
  title: string
  desc: string
  accent: string
  tile: string
  ring: string
}

const MODULES: ModuleDef[] = [
  {
    mode: 'assist',
    icon: Radio,
    title: '实时辅助',
    desc: '对方声音实时转录 · AI 自动回答 · 滚动备忘',
    accent: 'text-container-on-secondary',
    tile: 'bg-container-secondary',
    ring: 'hover:border-accent-green/50',
  },
  {
    mode: 'prep',
    icon: BookOpenCheck,
    title: '面试准备',
    desc: '技能卡 · 真题预测 · 模拟面试',
    accent: 'text-container-on-primary',
    tile: 'bg-container-primary',
    ring: 'hover:border-accent-blue/50',
  },
  {
    mode: 'review',
    icon: ClipboardList,
    title: '面试复盘',
    desc: '逐轮亮点/风险 · 整体评价 · 导出 MD/JSON',
    accent: 'text-container-on-tertiary',
    tile: 'bg-container-tertiary',
    ring: 'hover:border-accent-amber/50',
  },
  {
    mode: 'knowledge',
    icon: BrainCircuit,
    title: '能力分析',
    desc: '知识地图 · 薄弱点可视化',
    accent: 'text-container-on-primary',
    tile: 'bg-container-primary',
    ring: 'hover:border-accent-blue/50',
  },
  {
    mode: 'resume-opt',
    icon: FileText,
    title: '简历优化',
    desc: '对照 JD 命中/缺失分析 · 逐条建议',
    accent: 'text-container-on-secondary',
    tile: 'bg-container-secondary',
    ring: 'hover:border-accent-green/50',
  },
  {
    mode: 'job-tracker',
    icon: Kanban,
    title: '求职看板',
    desc: '投递进度 · Offer 对比 · 复盘串联',
    accent: 'text-container-on-tertiary',
    tile: 'bg-container-tertiary',
    ring: 'hover:border-accent-amber/50',
  },
]

function StatusCard({ ok, label, sub, icon: Icon }: { ok: boolean; label: string; sub?: string; icon: typeof Radio }) {
  return (
    <div
      className={`flex items-center gap-3 rounded-2xl px-3.5 py-3 transition-shadow ${
        ok ? 'bg-bg-secondary shadow-sm' : 'bg-bg-tertiary/45'
      }`}
    >
      <div
        className={`flex items-center justify-center w-9 h-9 rounded-xl flex-shrink-0 ${
          ok ? 'bg-container-primary text-container-on-primary' : 'bg-bg-tertiary/80 text-text-muted'
        }`}
      >
        <Icon className="w-4 h-4" />
      </div>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <span className={`text-xs font-semibold truncate ${ok ? 'text-text-primary' : 'text-text-muted'}`}>{label}</span>
          {ok && <CheckCircle2 className="w-3.5 h-3.5 text-accent-green flex-shrink-0" />}
        </div>
        {sub && <div className="text-[11px] text-text-muted truncate mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

export default function HomeScreen() {
  const setAppMode = useUiPrefsStore((s) => s.setAppMode)
  const config = useInterviewStore((s) => s.config)
  const sessions = useInterviewStore((s) => s.sessions)
  const activeSessionId = useInterviewStore((s) => s.activeSessionId)
  const kbStatus = useKbStore((s) => s.status)
  const [recentSpace, setRecentSpace] = useState<{ id: number; title: string; role: string; company: string; updated_at: number } | null>(null)

  useEffect(() => {
    let cancelled = false
    try {
      api.prepListSpaces()
        .then((res) => {
          if (cancelled || !res.items?.length) return
          const first = res.items[0]
          setRecentSpace({
            id: first.id,
            title: first.title || first.role || '未命名准备空间',
            role: first.role || '',
            company: first.company || '',
            updated_at: first.updated_at ?? 0,
          })
        })
        .catch(() => {})
    } catch {
      /* fetch unavailable (e.g. unit tests) */
    }
    return () => { cancelled = true }
  }, [])

  const activeSession = sessions.find((x) => x.id === activeSessionId || x.is_active)
  const jdLoaded = Boolean((config?.jd_text ?? '').trim())
  const kbDocs = kbStatus?.total_docs ?? 0

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8">
      <div className="max-w-5xl mx-auto">
        {/* Hero */}
        <div className="mb-8">
          <div className="flex items-center gap-4">
            <div className="sig-tile w-12 h-12 rounded-2xl flex-shrink-0">
              <Radio className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h2 className="text-2xl md:text-3xl font-bold text-text-primary tracking-tight">成竹 · 面试工作台</h2>
              <p className="text-sm text-text-muted mt-1.5 leading-relaxed">先准备，再上场 —— 一个工作台，覆盖准备 → 实战 → 复盘全流程</p>
            </div>
          </div>
        </div>

        {/* 状态条 · 大卡 */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-8">
          <StatusCard ok={Boolean(activeSession)} icon={Layers} label="当前会话" sub={activeSession?.label || '默认会话'} />
          <StatusCard ok={Boolean(config?.has_resume)} icon={FileText} label="简历" sub={config?.has_resume ? '已载入' : '未上传'} />
          <StatusCard ok={jdLoaded} icon={Briefcase} label="岗位 JD" sub={jdLoaded ? '已配置' : '未配置'} />
          <StatusCard ok={kbDocs > 0} icon={Database} label="知识库" sub={kbDocs > 0 ? `${kbDocs} 篇文档` : config?.kb_enabled ? '已开启，暂无文档' : '未开启'} />
          <StatusCard ok={Boolean(config?.model_name)} icon={Cpu} label="答题模型" sub={config?.model_name || '未配置'} />
        </div>

        {/* 继续上次 */}
        {recentSpace && (
          <button
            type="button"
            onClick={() => setAppMode('prep')}
            className="mb-6 group w-full text-left rounded-2xl border border-accent-blue/20 bg-gradient-to-r from-accent-blue/[0.07] via-bg-secondary/50 to-transparent p-4 md:p-5 card-lift transition-all hover:border-accent-blue/45 hover:shadow-lg hover:shadow-accent-blue/5"
          >
            <div className="flex items-center gap-3.5">
              <div className="bg-container-primary text-container-on-primary flex items-center justify-center w-10 h-10 rounded-xl flex-shrink-0">
                <Clock className="w-4 h-4" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-accent-blue">继续上次准备</div>
                <div className="text-sm font-medium text-text-primary truncate mt-0.5">
                  {recentSpace.title}
                  {(recentSpace.company || recentSpace.role) && (
                    <span className="text-text-muted font-normal"> · {[recentSpace.company, recentSpace.role].filter(Boolean).join(' · ')}</span>
                  )}
                </div>
              </div>
              <ArrowRight className="w-4 h-4 text-text-muted group-hover:text-accent-blue transition-colors" />
            </div>
          </button>
        )}

        {/* 模块卡片 */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {MODULES.map((mod) => {
            const Icon = mod.icon
            return (
              <button
                key={mod.mode}
                type="button"
                onClick={() => setAppMode(mod.mode)}
                className={`group text-left rounded-2xl bg-bg-secondary shadow-sm p-6 card-lift hover:shadow-md ${mod.ring}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3.5">
                    <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${mod.tile} ${mod.accent}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-base font-bold text-text-primary">{mod.title}</div>
                      <div className="text-xs text-text-muted mt-1 leading-snug">{mod.desc}</div>
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-text-muted/50 group-hover:text-text-primary transition-colors flex-shrink-0 mt-1" />
                </div>
              </button>
            )
          })}
        </div>

        <p className="text-xs text-text-muted mt-8 leading-relaxed">
          提示：面试前在「面试准备」里准备好岗位和技能卡；面试中用「实时辅助」抓对方问题，系统音频（★扬声器）→ 实时转录 → AI 自动回答；结束后去「面试复盘」生成分析。
        </p>
      </div>

      {/* MD FAB：一键进入实时面试 */}
      <button
        type="button"
        onClick={() => setAppMode('assist')}
        aria-label="开始面试"
        title="进入实时辅助"
        className="fixed bottom-8 right-8 z-30 inline-flex items-center gap-2 rounded-full bg-accent-blue text-white pl-4 pr-5 py-3 text-sm font-semibold shadow-lg shadow-accent-blue/30 transition-all hover:brightness-110 active:scale-[0.98]"
      >
        <Mic className="w-4 h-4" aria-hidden />
        开始面试
      </button>
    </div>
  )
}
