#!/usr/bin/env node
/**
 * Chengzhu UI v2 — Human Visual Acceptance harness.
 *
 * The product owner's visual judgement is subjective and made by a human. This
 * harness makes every rule that *can* be stated objectively executable instead
 * of guessed at: it renders the real built product against deterministic API +
 * WebSocket fixtures, drives the real interaction states, measures the live
 * DOM and the resulting pixels, writes screenshot evidence, and fails the run
 * when a frozen UI v2 rule is broken.
 *
 * What it checks (see README in docs/product/CHENGZHU_UI_V2_VISUAL_FREEZE_R2.md):
 *   - no document-level horizontal scroll at any accepted viewport;
 *   - primary CTA reachable inside the first viewport at 1280x720;
 *   - dialogs fully inside the viewport at 1280x720;
 *   - a stable typographic scale (<= 6 distinct text sizes per Studio surface);
 *   - radii > 12px only on dialogs/overlays or status pills;
 *   - shadows only on dialogs/popovers/overlays;
 *   - no blank / error-only screenshots (ink coverage);
 *   - brand-green pixel budget stays restrained;
 *   - heading order, accessible names, focus-visible, reduced-motion;
 *   - product invariants: cue <= 3 bullets, transcript collapsed, compact Live,
 *     Goal Prepare order, primary nav, evidence-boundary labels, and no
 *     offer-probability / readiness-percentage / stealth copy anywhere.
 *
 * Usage:
 *   node scripts/ui-v2-hva.mjs                 # measure + assert (exit 1 on violation)
 *   node scripts/ui-v2-hva.mjs --sheet         # also rebuild the contact sheet
 *   HVA_OUT=../.runtime/ui-v2-hva/00-baseline node scripts/ui-v2-hva.mjs
 *
 * Evidence lands in HVA_OUT (default ../.runtime/ui-v2-hva/15-final).
 * This harness never writes into the repository tree.
 */
import { chromium } from 'playwright'
import { createServer } from 'node:http'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { PNG } from 'pngjs'
import { resolveApiPayload } from '../e2e/fixtures/sample-data.mjs'
import { mockWsInitScript } from '../e2e/fixtures/mock-ws.mjs'

import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const AXE_PATH = require.resolve('axe-core/axe.min.js')

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HERE, '..')
const REPO = path.resolve(FRONTEND, '..')
const DIST = path.join(FRONTEND, 'dist')
const OUT = path.resolve(process.env.HVA_OUT ?? path.join(REPO, '.runtime', 'ui-v2-hva', '15-final'))
const PORT = Number(process.env.HVA_PORT ?? 4188)
const BASE = `http://127.0.0.1:${PORT}`

const VIEWPORTS = [
  { id: '1440x900', width: 1440, height: 900 },
  { id: '1280x720', width: 1280, height: 720 },
  { id: '1920x1080', width: 1920, height: 1080 },
  { id: '768x1024', width: 768, height: 1024 },
  { id: '390x844', width: 390, height: 844 },
]
const PRIMARY_VIEWPORT = '1440x900'

// Measured on the fixture run (18 surfaces): DOM <= 414, LCP <= 280 ms, long-task
// total <= 53 ms, heap ~10 MB. The ceilings sit well above that — enough headroom
// for the richer real-data states, tight enough that a runaway list, a rerender
// loop or a leak trips them. LCP is recorded but not enforced: a shared CI runner
// changes that number far more than the code does.
const RUNTIME_BUDGET = { domNodes: 700, longTaskMs: 250, heapMb: 60 }

const RESPONSIVE_VIEWPORTS = ['1280x720', '1920x1080', '768x1024', '390x844']

// ---------------------------------------------------------------- fixtures --
const T = 1_800_000_000
const GOAL_ID = 'goal-ui-v2'

const FOCUS = {
  id: 'focus-ui-1',
  goal_id: GOAL_ID,
  type: 'INTERVIEW_GAP',
  title: '把 AI 产品判断讲到可验证',
  reason: '二面最容易继续追问：为什么这样设计、如何验证、失败时怎么回退。',
  source_kind: 'DERIVED',
  source_ref: 'reflection-902',
  actions: [{ key: 'practice', label: '练这个' }],
  priority: 1,
  status: 'ACTIVE',
  origin: 'DERIVED',
}

const RECENT_SESSION = {
  key: 'review:902',
  type: 'REAL',
  guided: false,
  reflection_ref: { session_kind: 'REVIEW', session_ref: '902' },
  review_session_id: 902,
  goal_id: GOAL_ID,
  goal_title: '字节跳动 · AI 产品经理',
  round: 'PRODUCT_CASE',
  title: 'AI 产品经理 · 一面',
  panel: false,
  started_at: T - 86_400,
  ended_at: T - 82_800,
  has_reflection: true,
  turn_count: 7,
}

const GOAL = {
  id: GOAL_ID,
  title: '字节跳动 · AI 产品经理',
  company: '字节跳动',
  role: 'AI 产品经理',
  jd: '负责 AI 产品规划、Agent 场景设计、评测体系与跨团队落地。\n要求能把业务问题转化为可验证的产品假设。',
  status: 'ACTIVE',
  stage: '二面',
  next_interview_at: T + 172_800,
  interview_round: 'PRODUCT_CASE',
  goal_notes: '二面会重点追问产品判断、评测设计和实际落地。',
  selected_resume_id: 3,
  selected_material_ids: [],
  selected_kb_ids: [],
  selected_quick_note_ids: [],
  active_question_bank_ids: [],
  next_focus_id: FOCUS.id,
  offer_state: 'NONE',
  role_family: 'PRODUCT',
  legacy_prep_space_id: null,
  application_id: null,
  last_opened_at: T - 300,
  created_at: T - 1_209_600,
  updated_at: T - 300,
}

const GOAL_DETAIL = {
  ...GOAL,
  interviews: [{
    id: 'interview-ui-2',
    goal_id: GOAL_ID,
    round: 'PRODUCT_CASE',
    kind: 'REAL',
    status: 'UPCOMING',
    scheduled_at: T + 172_800,
    notes: '产品负责人二面',
  }],
  offer: { goal_id: GOAL_ID, status: 'NONE', comp: '', deadline: null, notes: '', updated_at: null },
  next_focus: [
    FOCUS,
    {
      ...FOCUS,
      id: 'focus-ui-2',
      type: 'STORY_GAP',
      title: '准备一个失败后改方案的案例',
      reason: '当前素材里成功案例多，但缺少一次有取舍、有回退的完整故事。',
      source_ref: 'story-gap',
      priority: 2,
    },
  ],
  sessions: [RECENT_SESSION],
}

const GOAL_PREPARE = {
  goal_id: GOAL_ID,
  next_focus: GOAL_DETAIL.next_focus,
  gap_map: [
    {
      topic: 'AI 产品判断与验证',
      status: 'REVIEW_WEAKNESS',
      source: 'review',
      priority: 'high',
      reason: '上一轮两次先讲实现，再补为什么值得做；二面需要先给判断和验证标准。',
    },
    {
      topic: '失败后的回退与止损',
      status: 'GAP',
      source: 'story',
      priority: 'high',
      reason: '现有材料能说明成功路径，但缺一个主动停止、回退或改方案的完整真实案例。',
    },
    {
      topic: 'Agent 评测方法',
      status: 'KNOWLEDGE_MATCH',
      source: 'job_alignment',
      priority: 'medium',
      reason: '技术知识足够，但还需要明确哪些评测指标是你实际定义、验证或推动落地的。',
    },
  ],
  attack_surface: [
    {
      claim_id: 'claim-prepare-1',
      text: '我设计了 Chengzhu 的评测闭环，并推动从离线指标收敛到可验证的用户任务。',
      risks: ['“设计”会被追问你本人具体负责的边界', '评测闭环需要给出指标、样本和失败回退'],
      probes: ['你本人定义了哪些指标？', '为什么这些指标能代表真实用户价值？', '如果线上结果和离线评测冲突，你怎么处理？'],
    },
    {
      claim_id: 'claim-prepare-2',
      text: 'WenNian 第一版主动缩小范围，只验证核心 Healthspan 链路。',
      risks: ['会被追问为什么砍掉原方案', '需要说明判断依据而不是事后合理化'],
      probes: ['你砍掉了什么？', '当时有哪些数据支持这个取舍？'],
    },
  ],
  question_graph: [
    { id: 'prep-q1', text: '你怎么判断一个 AI 功能真的值得上线？', kind: 'PRODUCT_JUDGMENT', source: 'review', parent_id: '' },
    { id: 'prep-q2', text: '具体用哪些用户信号和业务指标验证？', kind: 'EVIDENCE', source: 'review', parent_id: 'prep-q1' },
    { id: 'prep-q3', text: '如果离线指标很好但用户还是回退呢？', kind: 'PRESSURE', source: 'review', parent_id: 'prep-q2' },
    { id: 'prep-q4', text: '讲一次你主动停止一个方向并承担取舍的经历。', kind: 'STORY', source: 'story_gap', parent_id: '' },
  ],
  stories: {
    items: [
      { id: 'story-prepare-1', title: '从错误方向切回最小可验证产品', tags: ['Trade-off'] },
      { id: 'story-prepare-2', title: '跨团队推动一次高风险改版', tags: ['Collaboration'] },
    ],
    prompts: [{ competency: '失败与反思', hint: '从真实经历整理，不补造结果' }],
    coverage: { categories: [{ key: 'Trade-off', label: '取舍', story_ids: ['story-prepare-1'] }], missing: [{ key: 'Failure', label: '失败与反思' }] },
  },
  has_jd: true,
  materials: {
    included: [
      { material_id: 'mat-ui-1', version_id: 'mv-1', version: 3, title: 'WenNian 产品设计与上线记录', kind: 'PROJECT', usage: 'FACTS', is_personal_evidence: true, lifecycle: { state: 'READY', active_version: 3 } },
      { material_id: 'mat-ui-3', version_id: 'mv-3', version: 2, title: 'Chengzhu 设计复盘与评测记录', kind: 'PROJECT', usage: 'BOTH', is_personal_evidence: true, lifecycle: { state: 'READY', active_version: 2 } },
    ],
    skipped: [{ material_id: 'mat-ui-2', title: 'Agent 评测方法与指标参考', reason: '只作为技术参考，不进入个人事实包' }],
    selected_ids: ['mat-ui-1', 'mat-ui-2', 'mat-ui-3'],
  },
  pack_preview: {
    quick_notes: [
      { id: 'note-prepare-1', title: '反问面试官', content: '问清楚团队当前 Agent 评测是离线指标还是线上用户任务闭环。' },
      { id: 'note-prepare-2', title: '别忘了这个数字', content: 'WenNian 第一版只验证核心链路，不把尚未上线的指标说成线上结果。' },
    ],
    materials: [
      { material_id: 'mat-ui-1', version_id: 'mv-1', version: 3, title: 'WenNian 产品设计与上线记录', kind: 'PROJECT', usage: 'FACTS', is_personal_evidence: true, lifecycle: { state: 'READY', active_version: 3 } },
      { material_id: 'mat-ui-3', version_id: 'mv-3', version: 2, title: 'Chengzhu 设计复盘与评测记录', kind: 'PROJECT', usage: 'BOTH', is_personal_evidence: true, lifecycle: { state: 'READY', active_version: 2 } },
    ],
    legacy_prep_space_id: null,
  },
}

const PREFLIGHT = {
  goal: { id: GOAL_ID, title: GOAL.title },
  items: [
    { key: 'goal', label: '目标', value: GOAL.title, origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'resume', label: '简历', value: '当前简历', origin: 'PERSON', origin_label: '我的成竹', ok: true, hint: '' },
    { key: 'ai_policy_mode', label: 'AI 辅助', value: 'AI_ALLOWED', origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'human_assistance_policy', label: '真人辅助', value: 'HUMAN_PRACTICE_ONLY', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'share_privacy_mode', label: '共享隐私', value: 'OFF', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
  ],
  blockers: [],
  share_privacy_note: '共享隐私默认关闭；本场设置只影响当前会话。',
}

const PREFLIGHT_BLOCKED = {
  goal: { id: GOAL_ID, title: GOAL.title },
  items: [
    { key: 'goal', label: '目标', value: GOAL.title, origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'resume', label: '简历', value: '郝磊-简历.pdf', origin: 'PERSON', origin_label: '我的成竹', ok: true, hint: '' },
    { key: 'skill_cards', label: '技能卡', value: 4, origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'stories', label: 'Stories', value: 3, origin: 'PERSON', origin_label: '我的成竹', ok: true, hint: '' },
    { key: 'knowledge', label: '知识参考', value: '已启用', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'materials', label: '项目资料', value: 2, origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'quick_notes', label: '速记', value: 1, origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '速记只是提醒，不是个人经历证据。' },
    { key: 'answer_language', label: '回答语言', value: 'FOLLOW_INTERVIEW', origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'whisper_language', label: '识别语言', value: 'auto', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'language', label: '界面语言', value: '中文', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'technical_term_policy', label: '技术术语', value: '保留英文', origin: 'PERSON', origin_label: '我的成竹', ok: true, hint: '' },
    { key: 'active_model', label: '模型', value: 'GPT-4.1 Mini', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'audio', label: '会议音频', value: '未就绪', origin: 'SYSTEM', origin_label: '系统检查', ok: false, hint: '没有检测到可用的系统音频输入；请在设置里完成测试后重试。' },
    { key: 'stt', label: '语音识别', value: 'Whisper · 就绪', origin: 'SYSTEM', origin_label: '系统检查', ok: true, hint: '' },
    { key: 'screen_context', label: '屏幕上下文', value: '关闭', origin: 'SYSTEM', origin_label: '系统检查', ok: true, hint: '' },
    { key: 'ai_policy_mode', label: 'AI 辅助', value: 'AI_ALLOWED', origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'human_assistance_policy', label: '真人辅助', value: 'HUMAN_PRACTICE_ONLY', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'share_privacy_mode', label: '共享隐私', value: 'OFF', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
  ],
  blockers: [
    { key: 'audio', label: '会议音频', value: '未就绪', origin: 'SYSTEM', origin_label: '系统检查', ok: false, hint: '没有检测到可用的系统音频输入；请在设置里完成测试后重试。' },
  ],
  share_privacy_note: '共享隐私默认关闭；它不是安全或“不可检测”保证。',
}

const FROZEN_PACK = {
  id: 'pack-ui-1',
  session_id: 'live-ui-1',
  revision: 1,
  frozen: true,
  content_hash: 'ui-v2-visual-freeze',
  parent_id: '',
  job: { id: GOAL_ID, title: 'AI 产品经理', company: '字节跳动' },
  counts: { claims: 8, evidence: 6, skill_cards: 4, stories: 3 },
  policies: {
    ai_policy: 'AI_ALLOWED',
    human_assistance_policy: 'HUMAN_PRACTICE_ONLY',
    share_privacy_policy: 'OFF',
    screen_context_policy: 'OFF',
  },
}

const COMMON_WS_BOOTSTRAP = [
  { type: 'stt_status', loaded: true, loading: false, delay: 20 },
  { type: 'model_health', index: 0, status: 'ok', delay: 30 },
  { type: 'model_health', index: 1, status: 'ok', delay: 35 },
  { type: 'model_health', index: 2, status: 'error', delay: 40 },
]

const LIVE_WS = [
  ...COMMON_WS_BOOTSTRAP,
  {
    type: 'init',
    delay: 30,
    session_id: 'live-ui-1',
    active_id: 'live-ui-1',
    transcriptions: ['你怎么判断这个 Agent 功能真的值得上线？'],
    qa_pairs: [{
      id: 'qa-live-ui',
      question: '你怎么判断这个 Agent 功能真的值得上线？',
      answer: '先给判断：不是看模型能力，而是看用户任务是否被更稳定地完成。\n\n## 证据\n先看任务完成率与人工回退，再看留存和业务指标。',
      thinkContent: '',
      timestamp: T,
      source: 'manual_text',
      model_name: 'GPT-4.1 Mini',
      fastCue: {
        direction: '先讲用户任务是否被稳定完成',
        cues: [
          { text: '任务完成率：用户是否真正完成目标', source: 'WORLD_KNOWLEDGE' },
          { text: '人工回退率：失败是否可控', source: 'WORLD_KNOWLEDGE' },
          { text: '留存与业务指标：确认不是一次性新鲜感', source: 'WORLD_KNOWLEDGE' },
        ],
        cautions: [],
      },
    }],
    is_recording: true,
    is_paused: false,
    stt_loaded: true,
  },
]

const DIAGNOSTICS = {
  packaged: true,
  data_home: 'C:/Users/kaiser/AppData/Roaming/Chengzhu',
  data_dir: 'C:/Users/kaiser/AppData/Roaming/Chengzhu/data',
  logs_dir: 'C:/Users/kaiser/AppData/Roaming/Chengzhu/logs',
  data_writable: true,
  models: [{ index: 0, name: 'Primary', model: 'gpt-4.1-mini', has_key: true, enabled: true }],
  has_usable_model: true,
  stt_provider: 'whisper',
  audio: {
    devices: [
      { id: 1, name: 'Pixel Buds Microphone', is_loopback: false },
      { id: 20000, name: 'Speakers (loopback)', is_loopback: true },
    ],
  },
  has_microphone: true,
  has_system_audio: true,
}

const FORBIDDEN_TEXT = [
  { re: /录用率/, why: '禁止出现录用率' },
  { re: /通过概率/, why: '禁止出现通过概率' },
  { re: /offer\s*probability/i, why: '禁止出现 offer probability' },
  { re: /候选人百分位/, why: '禁止出现候选人百分位' },
  { re: /readiness\s*score/i, why: '禁止出现 readiness score' },
  { re: /准备度\s*\d+\s*%/, why: '禁止出现准备度百分比' },
  { re: /隐身|不被发现/, why: '禁止 stealth 叙事' },
  { re: /undetectable/i, why: '禁止 stealth 叙事' },
]

// ------------------------------------------------------------------ states --
const HOME = {
  state: 'ACTIVE',
  primary_action: { key: 'continue_prepare', label: '继续准备', goal_id: GOAL_ID },
  next_interview: {
    goal_id: GOAL_ID,
    interview_id: 'interview-ui-2',
    title: '字节跳动 · AI 产品经理',
    company: '字节跳动',
    role: 'AI 产品经理',
    round: 'PRODUCT_CASE',
    scheduled_at: T + 172_800,
    actions: [],
  },
  focus_goal: { id: GOAL_ID, title: GOAL.title },
  next_focus: GOAL_DETAIL.next_focus,
  needs_attention: [],
  recent_session: RECENT_SESSION,
  active_goal_count: 2,
}

const goalMocks = (pathname, method) => {
  if (method === 'GET' && pathname === '/api/product/home') return HOME
  if (method === 'GET' && pathname === '/api/product/goals') return { items: [GOAL] }
  if (method === 'GET' && pathname === `/api/product/goals/${GOAL_ID}`) return GOAL_DETAIL
  if (method === 'GET' && pathname === `/api/product/goals/${GOAL_ID}/prepare`) return GOAL_PREPARE
  return undefined
}

const STATES = [
  {
    id: 'onboarding-understand',
    dir: '01-first-run',
    label: 'First Run · 理解',
    url: '/#/home',
    kind: 'setup',
    dialog: true,
    messages: COMMON_WS_BOOTSTRAP,
    mocks: (pathname, method) => {
      if (pathname === '/api/config' && method === 'GET') return { ...resolveApiPayload('/api/config', 'GET'), onboarding_completed: false }
      if (pathname === '/api/intelligence/diagnostics') return DIAGNOSTICS
      return undefined
    },
    ready: async (page) => {
      await page.getByTestId('onboarding').waitFor({ state: 'visible', timeout: 15000 })
    },
  },
  {
    id: 'onboarding-goal',
    dir: '01-first-run',
    label: 'First Run · 创建目标',
    url: '/#/home',
    kind: 'setup',
    dialog: true,
    messages: COMMON_WS_BOOTSTRAP,
    mocks: (pathname, method) => {
      if (pathname === '/api/config' && method === 'GET') return { ...resolveApiPayload('/api/config', 'GET'), onboarding_completed: false }
      if (pathname === '/api/intelligence/diagnostics') return DIAGNOSTICS
      if (pathname === '/api/product/goals' && method === 'POST') return GOAL
      if (method === 'GET' && pathname.startsWith('/api/product/goals/')) return goalMocks(pathname, method)
      return goalMocks(pathname, method)
    },
    ready: async (page) => {
      const wizard = page.getByTestId('onboarding')
      await wizard.waitFor({ state: 'visible', timeout: 15000 })
      for (let i = 0; i < 8; i += 1) {
        const company = wizard.getByTestId('onboarding-goal-company')
        if (await company.count()) break
        const next = wizard.getByTestId('onboarding-next')
        if (!(await next.count()) || await next.isDisabled()) break
        await next.click()
        await page.waitForTimeout(120)
      }
      await wizard.getByTestId('onboarding-goal-company').waitFor({ state: 'visible' })
    },
  },
  {
    id: 'onboarding-ready',
    dir: '01-first-run',
    label: 'First Run · 就绪',
    url: '/#/home',
    kind: 'setup',
    dialog: true,
    messages: COMMON_WS_BOOTSTRAP,
    mocks: (pathname, method) => {
      if (pathname === '/api/config' && method === 'GET') return { ...resolveApiPayload('/api/config', 'GET'), onboarding_completed: false }
      if (pathname === '/api/intelligence/diagnostics') return DIAGNOSTICS
      if (pathname === '/api/product/goals' && method === 'POST') return GOAL
      if (method === 'GET' && pathname.startsWith('/api/product/goals/')) return goalMocks(pathname, method)
      return goalMocks(pathname, method)
    },
    ready: async (page) => {
      const wizard = page.getByTestId('onboarding')
      await wizard.waitFor({ state: 'visible', timeout: 15000 })
      const finish = wizard.getByTestId('onboarding-finish')
      for (let i = 0; i < 10; i += 1) {
        if (await finish.count()) break
        const company = wizard.getByTestId('onboarding-goal-company')
        if (await company.count()) {
          await company.fill('字节跳动')
          await wizard.getByTestId('onboarding-goal-role').fill('AI 产品经理')
        }
        const next = wizard.getByTestId('onboarding-next')
        if (!(await next.count()) || await next.isDisabled()) break
        await next.click()
        await page.waitForTimeout(150)
      }
      await finish.waitFor({ state: 'visible' })
    },
  },
  {
    id: 'create-goal',
    dir: '01-first-run',
    label: 'Create Goal',
    url: '/#/goals',
    kind: 'setup',
    dialog: true,
    messages: COMMON_WS_BOOTSTRAP,
    mocks: (pathname, method) => {
      if (method === 'GET' && pathname === '/api/product/goals') return { items: [GOAL] }
      return undefined
    },
    ready: async (page) => {
      await page.getByRole('heading', { name: '求职目标' }).first().waitFor({ state: 'visible', timeout: 15000 })
      await page.getByRole('button', { name: /新建|创建目标|建一个目标/ }).first().click()
      await page.getByRole('dialog').waitFor({ state: 'visible' })
    },
  },
  {
    id: 'home',
    dir: '02-home',
    label: 'Home',
    url: '/#/home',
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page, viewport) => {
      await waitForStudio(page, viewport)
      await page.getByRole('button', { name: '继续准备' }).first().waitFor({ state: 'visible', timeout: 15000 })
    },
    primaryCta: '[data-testid="home-next-action"], button:has-text("继续准备")',
    nav: true,
  },
  {
    id: 'goals',
    dir: '03-goals',
    label: 'Goals',
    url: '/#/goals',
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page) => {
      await page.getByRole('heading', { name: '求职目标' }).first().waitFor({ state: 'visible', timeout: 15000 })
    },
    primaryCta: 'button:has-text("新建")',
    nav: true,
  },
  {
    id: 'goal-room',
    dir: '04-goal-room',
    label: 'Goal Room',
    url: `/#/goals/${GOAL_ID}`,
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page) => {
      await page.getByTestId('goal-room').waitFor({ state: 'visible', timeout: 15000 })
    },
    primaryCta: '[data-testid="goal-go-live"]',
    nav: true,
  },
  {
    id: 'goal-prepare',
    dir: '05-prepare',
    label: 'Goal Prepare',
    url: `/#/goals/${GOAL_ID}/prepare`,
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page) => {
      await page.getByTestId('goal-prepare-workspace').waitFor({ state: 'visible', timeout: 15000 })
    },
    primaryCta: '[data-testid="goal-go-live"]',
    prepareOrder: true,
    nav: true,
  },
  {
    id: 'practice-setup',
    dir: '06-practice',
    label: 'Practice Setup',
    url: '/#/practice?goal=goal-ui-v2',
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page) => {
      await page.getByTestId('practice-setup').waitFor({ state: 'visible', timeout: 15000 })
    },
    primaryCta: '[data-testid="practice-start"]',
    nav: true,
  },
  {
    id: 'preflight-ready',
    dir: '07-preflight',
    label: 'Preflight · Ready',
    url: `/#/goals/${GOAL_ID}`,
    kind: 'setup',
    mocks: (pathname, method) => {
      if (method === 'POST' && pathname === '/api/product/live/preflight') return PREFLIGHT
      return goalMocks(pathname, method)
    },
    ready: async (page) => {
      await page.getByTestId('goal-room').waitFor({ state: 'visible', timeout: 15000 })
      await page.getByTestId('goal-go-live').click()
      await page.getByTestId('preflight').waitFor({ state: 'visible' })
      await page.getByTestId('preflight-start').waitFor({ state: 'visible' })
    },
    primaryCta: '[data-testid="preflight-start"]',
    dialog: true,
  },
  {
    id: 'preflight-blocked',
    dir: '07-preflight',
    label: 'Preflight · Blocked',
    url: `/#/goals/${GOAL_ID}`,
    kind: 'setup',
    mocks: (pathname, method) => {
      if (method === 'POST' && pathname === '/api/product/live/preflight') return PREFLIGHT_BLOCKED
      return goalMocks(pathname, method)
    },
    ready: async (page) => {
      await page.getByTestId('goal-room').waitFor({ state: 'visible', timeout: 15000 })
      await page.getByTestId('goal-go-live').click()
      await page.getByTestId('preflight').waitFor({ state: 'visible' })
      await page.getByText('开始前需要处理').waitFor({ state: 'visible' })
    },
    dialog: true,
    blocked: true,
    blockingCta: '[data-testid="preflight-start"]',
  },
  {
    id: 'live-cue',
    allowNestedCards: true,
    dir: '08-live',
    label: 'Live · Cue',
    url: `/#/goals/${GOAL_ID}`,
    kind: 'live',
    messages: LIVE_WS,
    surface: 'live',
    localStorage: {
      'ia-color-scheme': 'vscode-dark-plus',
      'ia_app_mode': 'assist',
      'ia-assist-transcript-collapsed': '1',
    },
    mocks: (pathname, method) => {
      if (method === 'POST' && pathname === '/api/product/live/preflight') return PREFLIGHT
      if (method === 'POST' && pathname === '/api/product/live/start') return { session_id: 'live-ui-1', goal_id: GOAL_ID, pack: FROZEN_PACK }
      if (method === 'GET' && pathname === '/api/intelligence/pack') return { session_id: 'live-ui-1', frozen: true, pack: FROZEN_PACK, revisions: [] }
      if (method === 'GET' && pathname === '/api/intelligence/session-claims') return []
      return goalMocks(pathname, method)
    },
    ready: async (page) => {
      await enterLive(page)
      await page.locator('[data-testid="fast-cue"]:visible').first().waitFor({ state: 'visible', timeout: 15000 })
    },
    allowShadow: true,
    cueRules: true,
  },
  {
    id: 'live-deep',
    allowNestedCards: true,
    dir: '08-live',
    label: 'Live · Deep',
    url: `/#/goals/${GOAL_ID}`,
    kind: 'live',
    messages: LIVE_WS,
    surface: 'live',
    localStorage: {
      'ia-color-scheme': 'vscode-dark-plus',
      'ia_app_mode': 'assist',
      'ia-assist-transcript-collapsed': '1',
    },
    mocks: (pathname, method) => {
      if (method === 'POST' && pathname === '/api/product/live/preflight') return PREFLIGHT
      if (method === 'POST' && pathname === '/api/product/live/start') return { session_id: 'live-ui-1', goal_id: GOAL_ID, pack: FROZEN_PACK }
      if (method === 'GET' && pathname === '/api/intelligence/pack') return { session_id: 'live-ui-1', frozen: true, pack: FROZEN_PACK, revisions: [] }
      if (method === 'GET' && pathname === '/api/intelligence/session-claims') return []
      return goalMocks(pathname, method)
    },
    ready: async (page) => {
      await enterLive(page)
      const disclosure = page.getByTestId('deep-answer-disclosure').first()
      await disclosure.waitFor({ state: 'visible', timeout: 15000 })
      const toggle = disclosure.getByRole('button').first()
      if ((await toggle.getAttribute('aria-expanded')) !== 'true') await toggle.click()
      await page.waitForTimeout(200)
    },
    allowShadow: true,
    cueRules: true,
  },
  {
    id: 'reflection',
    dir: '09-reflection',
    label: 'Reflection',
    url: '/#/reflection/review/902',
    kind: 'studio',
    mocks: (pathname, method) => {
      if (method === 'GET' && pathname === '/api/product/reviews/902') return REFLECTION
      if (method === 'GET' && pathname === '/api/product/reflection/review/902') return REFLECTION
      if (method === 'GET' && pathname === '/api/product/reviews/902/reflection') return REFLECTION
      return goalMocks(pathname, method)
    },
    ready: async (page, viewport) => {
      await waitForStudio(page, viewport)
    },
    nav: true,
  },
  {
    id: 'history',
    dir: '10-history',
    label: 'History',
    url: '/#/history',
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page, viewport) => {
      await waitForStudio(page, viewport)
    },
    nav: true,
  },
  {
    id: 'me',
    dir: '11-me',
    label: 'My Chengzhu',
    url: '/#/me',
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page, viewport) => {
      await waitForStudio(page, viewport)
    },
    nav: true,
    expectText: ['有直接证据', '你已确认', '暂无证据'],
  },
  {
    id: 'library',
    dir: '12-library',
    label: 'Library · Materials',
    url: '/#/library',
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page, viewport) => {
      await waitForStudio(page, viewport)
    },
    nav: true,
    expectText: ['项目资料', '知识库', '速记', '题库'],
  },
  {
    id: 'settings',
    dir: '13-settings',
    label: 'Settings · General',
    url: '/#/settings/general',
    kind: 'studio',
    mocks: goalMocks,
    ready: async (page, viewport) => {
      await waitForStudio(page, viewport)
    },
    nav: true,
  },
]

const REFLECTION = {
  session_kind: 'REVIEW',
  session_ref: '902',
  goal_id: GOAL_ID,
  title: '字节跳动 · AI 产品经理 · 一面',
  first_screen: {
    next_step: {
      kind: 'FINDING',
      title: '把“为什么这样设计”提前到答案第一句',
      reason: '你两次先讲实现，再补产品判断；下一轮最值得练的是先给结论和验证标准。',
      finding_id: 'finding-1',
      goal_id: GOAL_ID,
    },
    pinned_moments: [{
      id: 'pin-ui-1',
      session_kind: 'LIVE',
      session_id: 'live-ui-1',
      turn_id: 'turn-3',
      goal_id: GOAL_ID,
      tag: 'IMPORTANT',
      tag_label: '重要',
      question: '你怎么判断这个 Agent 功能真的值得上线？',
      transcript_excerpt: '我会先看用户是否真的需要，再做灰度。',
      note: '这里被连续追问了两次验证指标。',
      ts: T - 84_000,
    }],
    went_well: [{
      dimension: 'structure',
      dimension_label: '结构',
      question: '讲一个你主导的 AI 产品。',
      actual_speech: '我先定义了用户问题，再拆出最小可验证路径和上线后的反馈闭环。',
    }],
    to_improve: [{
      id: 'finding-1',
      kind: 'CONTENT',
      kind_label: '产品判断',
      dimension: 'product_judgment',
      dimension_label: '产品判断',
      finding: '结论出现得偏晚，验证标准没有在第一层说清楚。',
      action_hint: '先给判断，再用用户信号、业务指标和失败回退支撑。',
      turn_id: 'turn-3',
      question: '你怎么判断这个 Agent 功能真的值得上线？',
      actual_speech: '我会先做出来看效果，然后结合用户反馈继续优化。',
      occurrences: 2,
    }],
    fact_checks: [{
      id: 'fact-ui-1',
      kind: 'FACT',
      kind_label: '事实核对',
      finding: '“核心指标提升 30%”需要补原始来源。',
      question: '这个项目最后效果怎么样？',
      actual_speech: '上线之后核心指标大概提升了 30%。',
      claim_id: 'claim-ui-1',
    }],
    story_opportunities: [],
  },
  delivery: ['结论平均出现在回答第 8 秒，下一轮尽量压到前 5 秒。'],
  timeline: [],
  actions: ['PRACTICE_THIS', 'SET_NEXT_FOCUS', 'ADD_SOURCE'],
  ask_cue_feedback: false,
}

// ------------------------------------------------------------------ server --
function startServer() {
  const types = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
    '.ico': 'image/x-icon',
    '.webp': 'image/webp',
  }
  const server = createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', BASE)
    let file = path.join(DIST, decodeURIComponent(url.pathname))
    if (!existsSync(file) || !path.extname(file)) file = path.join(DIST, 'index.html')
    try {
      const body = await readFile(file)
      res.writeHead(200, { 'content-type': types[path.extname(file)] ?? 'application/octet-stream' })
      res.end(body)
    } catch {
      res.writeHead(404).end('not found')
    }
  })
  return new Promise((resolve) => server.listen(PORT, '127.0.0.1', () => resolve(server)))
}

// ----------------------------------------------------------------- harness --
async function waitForStudio(page, viewport) {
  const width = viewport?.width ?? page.viewportSize()?.width ?? 1440
  if (width >= 768) {
    await page.getByRole('navigation', { name: '主导航' }).waitFor({ state: 'visible', timeout: 15000 })
    return
  }
  await page.locator('#root').waitFor({ state: 'visible', timeout: 15000 })
  await page.waitForTimeout(400)
}
async function enterLive(page) {
  await page.getByTestId('goal-room').waitFor({ state: 'visible', timeout: 15000 })
  await page.getByTestId('goal-go-live').click()
  await page.getByTestId('preflight').waitFor({ state: 'visible' })
  await page.getByTestId('preflight-start').click()
  await page.waitForURL(/#\/live\//, { timeout: 15000 })
  await page.getByTestId('live-status-line').waitFor({ state: 'visible' })
}

// Runtime probe: registered before the app boots, because LCP and long tasks are
// only observable through a PerformanceObserver that exists while they happen.
function runtimeProbeInit() {
  window.__perf = { lcp: 0, longTaskMs: 0, longTasks: 0 }
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) window.__perf.lcp = Math.max(window.__perf.lcp, entry.startTime)
    }).observe({ type: 'largest-contentful-paint', buffered: true })
  } catch { /* not supported in this engine */ }
  try {
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        window.__perf.longTaskMs += entry.duration
        window.__perf.longTasks += 1
      }
    }).observe({ type: 'longtask', buffered: true })
  } catch { /* not supported in this engine */ }
}

async function measureRuntime(page) {
  return page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0]
    const fcp = performance.getEntriesByName('first-contentful-paint')[0]
    const perf = window.__perf || { lcp: 0, longTaskMs: 0, longTasks: 0 }
    const memory = performance.memory
    return {
      domNodes: document.querySelectorAll('*').length,
      fcpMs: fcp ? Math.round(fcp.startTime) : null,
      lcpMs: perf.lcp ? Math.round(perf.lcp) : null,
      dclMs: nav ? Math.round(nav.domContentLoadedEventEnd) : null,
      longTasks: perf.longTasks,
      longTaskMs: Math.round(perf.longTaskMs),
      heapMb: memory ? Math.round(memory.usedJSHeapSize / 1048576) : null,
    }
  })
}
async function measure(page) {
  return page.evaluate(() => {
    const round = (n) => Math.round(n * 10) / 10
    const parseColor = (value) => {
      const m = /rgba?\(([^)]+)\)/.exec(value || '')
      if (!m) return null
      const parts = m[1].split(',').map((p) => Number.parseFloat(p.trim()))
      return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 }
    }
    const luminance = ({ r, g, b }) => {
      const f = (c) => {
        const s = c / 255
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
      }
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
    }
    const contrast = (a, b) => {
      const la = luminance(a)
      const lb = luminance(b)
      return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
    }
    const visible = (el) => {
      const cs = getComputedStyle(el)
      if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) < 0.05) return false
      const r = el.getBoundingClientRect()
      return r.width > 0 && r.height > 0
    }
    const all = Array.from(document.querySelectorAll('body *')).filter(visible)
    const inViewport = (el) => {
      const r = el.getBoundingClientRect()
      return r.top >= -1 && r.left >= -1 && r.bottom <= window.innerHeight + 1 && r.right <= window.innerWidth + 1
    }
    const accessibleName = (el) => {
      const aria = el.getAttribute('aria-label')
      if (aria && aria.trim()) return aria.trim()
      const labelledBy = el.getAttribute('aria-labelledby')
      if (labelledBy) {
        const text = labelledBy.split(/\s+/).map((id) => document.getElementById(id)?.textContent ?? '').join(' ').trim()
        if (text) return text
      }
      if (el.labels && el.labels.length > 0) {
        const labelText = el.labels[0].textContent ?? ''
        if (labelText.trim()) return labelText.trim()
      }
      const text = (el.textContent ?? '').trim()
      if (text) return text
      return (el.getAttribute('title') || el.getAttribute('placeholder') || el.getAttribute('alt') || el.getAttribute('value') || '').trim()
    }
    const directText = (el) => Array.from(el.childNodes).some((n) => n.nodeType === 3 && (n.textContent ?? '').trim().length > 0)

    const fontSizes = {}
    const fontSamples = {}
    const radii = {}
    const radiusSamples = []
    const shadows = []
    const pills = []
    const cards = []
    const contrastIssues = []
    let unnamed = 0
    const unnamedSamples = []

    for (const el of all) {
      const cs = getComputedStyle(el)
      const rect = el.getBoundingClientRect()

      const inShell = Boolean(el.closest('header, nav'))
      const negligible = el.getBoundingClientRect().width <= 1 || el.getBoundingClientRect().height <= 1
      if (directText(el) && !inShell && !negligible) {
        const size = round(Number.parseFloat(cs.fontSize))
        fontSizes[size] = (fontSizes[size] ?? 0) + 1
        if (!fontSamples[size]) fontSamples[size] = []
        if (fontSamples[size].length < 2) {
          const sample = (el.textContent ?? '').trim().slice(0, 18)
          const cls = String(el.className ?? '').split(/\s+/).slice(0, 2).join('.')
          fontSamples[size].push(`${sample}${cls ? ` [${cls}]` : ''}`)
        }
        const fg = parseColor(cs.color)
        let bgEl = el
        let bg = null
        while (bgEl && !bg) {
          const candidate = parseColor(getComputedStyle(bgEl).backgroundColor)
          if (candidate && candidate.a > 0.6) bg = candidate
          bgEl = bgEl.parentElement
        }
        if (fg && bg && fg.a > 0.5) {
          const ratio = contrast(fg, bg)
          const large = size >= 24 || (size >= 18.66 && Number(cs.fontWeight) >= 600)
          if (ratio < (large ? 3 : 4.5)) {
            contrastIssues.push({ text: (el.textContent ?? '').trim().slice(0, 24), size, ratio: round(ratio) })
          }
        }
      }
      const radius = cs.borderRadius.includes(' ')
        ? Math.max(...cs.borderRadius.split('/')[0].trim().split(' ').map((v) => Number.parseFloat(v) || 0))
        : Number.parseFloat(cs.borderRadius) || 0
      if (radius > 12 && radius < 900 && radiusSamples.length < 6) {
        radiusSamples.push(`${round(radius)}px ${el.tagName}.${String(el.className ?? '').split(/\s+/)[0] ?? ''} :: ${el.outerHTML.slice(0, 90).replace(/\s+/g, ' ')}`)
      }
      const hasPaint = (cs.backgroundColor && parseColor(cs.backgroundColor)?.a > 0.05) || Number.parseFloat(cs.borderTopWidth) > 0 || cs.boxShadow !== 'none'
      if (hasPaint && radius > 0) {
        const key = round(radius)
        radii[key] = (radii[key] ?? 0) + 1
        if (radius >= 900 && rect.height <= 40) pills.push({ text: (el.textContent ?? '').trim().slice(0, 16), radius: round(radius) })
      }
      if (cs.boxShadow && cs.boxShadow !== 'none') {
        const fixed = cs.position === 'fixed' || cs.position === 'absolute'
        const inDialog = Boolean(el.closest('[role="dialog"]'))
        const cls = String(el.className ?? '').split(/\s+/).slice(0, 3).join('.')
        const ringOnly = /^inset\s/.test(cs.boxShadow) || /^0px 0px 0px/.test(cs.boxShadow.replace(/rgba?\([^)]*\)/g, '').trim())
        shadows.push({ tag: el.tagName, cls, fixed, inDialog, ring: ringOnly, w: Math.round(rect.width), h: Math.round(rect.height), shadow: cs.boxShadow.slice(0, 40) })
      }
      const area = rect.width * rect.height
      if (radius >= 8 && area >= 8000 && hasPaint) {
        cards.push({
          area: Math.round(area),
          radius: round(radius),
          border: Number.parseFloat(cs.borderTopWidth) > 0,
          shadow: cs.boxShadow !== 'none',
          nested: false,
          text: (el.textContent ?? '').trim().slice(0, 20),
        })
      }
      if (el.matches('button, a[href], input, select, textarea, [role="button"], [tabindex="0"]')) {
        if (!accessibleName(el)) {
          unnamed += 1
          if (unnamedSamples.length < 5) unnamedSamples.push(el.tagName + (el.className ? '.' + String(el.className).split(' ')[0] : ''))
        }
      }
    }

    // nested card detection: a card that contains another card
    // A nested card is a defect only when a decorative container encloses
    // another decorative container. Cards that exist because they are an
    // interactive object (option, tab, button) may live inside a section —
    // that boundary carries meaning, it is not decoration.
    const cardEls = all.filter((el) => {
      const cs = getComputedStyle(el)
      const rect = el.getBoundingClientRect()
      const radius = Number.parseFloat(cs.borderRadius) || 0
      const bg = parseColor(cs.backgroundColor)
      if (el.closest('[role="dialog"]')) return false
      return radius >= 8 && rect.width * rect.height >= 8000 && ((bg && bg.a > 0.05) || cs.boxShadow !== 'none')
    })
    const isInteractiveCard = (el) => Boolean(el.closest('button, a[href], [role="button"], [role="tab"], [role="option"], label'))
    for (const el of cardEls) {
      const nestedOffender = cardEls.some((other) => other !== el && el.contains(other) && !isInteractiveCard(other))
      if (nestedOffender) {
        const idx = cardEls.indexOf(el)
        if (idx >= 0) cards[idx] = { ...cards[idx], nested: true }
      }
    }
    const nestedCardSamples = cards.filter((c) => c.nested).slice(0, 4).map((c) => `${c.text}|${c.radius}px`)

    const headings = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).filter(visible)
      .map((h) => ({ level: Number(h.tagName[1]), text: (h.textContent ?? '').trim().slice(0, 30) }))
    const headingSkips = []
    let prev = 0
    for (const h of headings) {
      if (prev && h.level > prev + 1) headingSkips.push(`${prev}->${h.level} (${h.text})`)
      prev = h.level
    }

    const animations = all.filter((el) => {
      const cs = getComputedStyle(el)
      return cs.animationName && cs.animationName !== 'none' && Number.parseFloat(cs.animationDuration) > 0.05
    }).length

    // Neutral ramp audit: "warm neutral" is a measured property, not an opinion.
    // A green/teal cast usually hides in the *neutrals* (text, borders, hovers)
    // while the saturated accent stays inside its budget, so read the tokens.
    const oklchOf = (triple) => {
      const parts = String(triple ?? '').trim().split(/\s+/).map((value) => Number.parseFloat(value))
      if (parts.length < 3 || parts.some((value) => !Number.isFinite(value))) return null
      const lin = parts.slice(0, 3).map((channel) => {
        const s = channel / 255
        return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
      })
      const l = 0.4122214708 * lin[0] + 0.5363325363 * lin[1] + 0.0514459929 * lin[2]
      const m = 0.2119034982 * lin[0] + 0.6806995451 * lin[1] + 0.1073969566 * lin[2]
      const s = 0.0883024619 * lin[0] + 0.2817188376 * lin[1] + 0.6299787005 * lin[2]
      const l_ = Math.cbrt(l); const m_ = Math.cbrt(m); const s_ = Math.cbrt(s)
      const A = 1.9779984951 * l_ - 2.428592205 * m_ + 0.4505937099 * s_
      const B = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.808675766 * s_
      let hue = (Math.atan2(B, A) * 180) / Math.PI
      if (hue < 0) hue += 360
      return { chroma: Number(Math.hypot(A, B).toFixed(4)), hue: Math.round(hue) }
    }
    const rootStyle = getComputedStyle(document.documentElement)
    const neutralTokens = ['--c-bg-primary', '--c-bg-tertiary', '--c-bg-hover', '--c-text-primary', '--c-text-secondary', '--c-text-muted', '--c-outline-variant', '--c-border-subtle']
    const neutralTint = {}
    for (const token of neutralTokens) {
      const value = rootStyle.getPropertyValue(token)
      if (!value.trim()) continue
      const measured = oklchOf(value)
      if (measured) neutralTint[token.replace('--c-', '')] = measured
    }
    const accentTint = oklchOf(rootStyle.getPropertyValue('--c-accent-blue'))
    const doc = document.documentElement
    const bodyText = document.body.innerText
    const cue = document.querySelector('[data-testid="fast-cue"]')
    const cueBullets = cue ? Array.from(cue.querySelectorAll('li')).filter(visible).length : null
    const secondaryTools = document.getElementById('live-secondary-tools')
    const transcriptCollapsed = secondaryTools ? !visible(secondaryTools) : null
    const nav = document.querySelector('nav[aria-label="主导航"]')
    const navLabels = nav ? Array.from(nav.querySelectorAll('button')).map((b) => (b.textContent ?? '').trim()).filter(Boolean) : null
    const statusLine = document.querySelector('[data-testid="live-status-line"]')
    const preflightDialog = document.querySelector('[data-testid="preflight"]')?.closest('[role="dialog"]')

    const rectOf = (el) => {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), inViewport: inViewport(el) }
    }

    return {
      doc: {
        scrollWidth: doc.scrollWidth,
        clientWidth: doc.clientWidth,
        scrollHeight: doc.scrollHeight,
        clientHeight: doc.clientHeight,
        overflowX: doc.scrollWidth - doc.clientWidth,
      },
      fontSizes,
      distinctFontSizes: Object.keys(fontSizes).length,
      fontSamples,
      radiusSamples,
      radii,
      shadows,
      pills: pills.length,
      cards: cards.length,
      nestedCards: cards.filter((c) => c.nested).length,
      nestedCardSamples,
      unnamedInteractive: unnamed,
      unnamedSamples,
      contrastIssues: contrastIssues.slice(0, 10),
      contrastIssueCount: contrastIssues.length,
      headings,
      headingSkips,
      animations,
      cueBullets,
      transcriptCollapsed,
      navLabels,
      neutralTint,
      accentTint,
      bodyTextLength: bodyText.length,
      bodyTextSample: bodyText.slice(0, 1200),
      live: {
        statusLine: rectOf(statusLine),
        cue: rectOf(cue),
      },
      preflight: preflightDialog ? { inViewport: inViewport(preflightDialog), rect: rectOf(preflightDialog) } : null,
      primaryCta: null,
    }
  })
}

async function analysePng(file) {
  const png = PNG.sync.read(await readFile(file))
  const { width, height, data } = png
  const histogram = new Map()
  const total = width * height
  let green = 0
  let dark = 0
  let ink = 0
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i]
    const g = data[i + 1]
    const b = data[i + 2]
    const key = (r >> 3) << 10 | (g >> 3) << 5 | (b >> 3)
    histogram.set(key, (histogram.get(key) ?? 0) + 1)
    if (Math.abs(r - 47) <= 40 && Math.abs(g - 107) <= 40 && Math.abs(b - 87) <= 40) green += 1
    if (r + g + b < 180) dark += 1
  }
  let dominant = 0
  for (const count of histogram.values()) if (count > dominant) dominant = count
  ink = 1 - dominant / total
  return {
    width,
    height,
    inkCoverage: Math.round(ink * 1000) / 1000,
    greenRatio: Math.round((green / total) * 10000) / 10000,
    darkRatio: Math.round((dark / total) * 10000) / 10000,
    uniqueColors: histogram.size,
  }
}

function ruleFailures(state, viewport, metrics, png, opts) {
  const failures = []
  const push = (rule, detail) => failures.push({ state: state.id, viewport: viewport.id, rule, detail })

  if (metrics.doc.overflowX > 1) push('no-page-horizontal-scroll', `scrollWidth 超出 ${metrics.doc.overflowX}px`)
  if (metrics.unnamedInteractive > 0) push('accessible-names', `${metrics.unnamedInteractive} 个可交互控件无名称: ${metrics.unnamedSamples.join(', ')}`)
  if (metrics.headingSkips.length) push('heading-order', metrics.headingSkips.join('; '))
  if (metrics.contrastIssueCount > 0) push('contrast', `${metrics.contrastIssueCount} 处低于 4.5:1 / 3:1`)
  if (metrics.nestedCards > 0 && !state.allowNestedCards) push('no-nested-cards', `${metrics.nestedCards} 处卡片嵌套`)

  const tooRound = Object.entries(metrics.radii)
    .filter(([radius]) => Number(radius) > 12 && Number(radius) < 900)
    .map(([radius, count]) => `${radius}px x${count}`)
  if (tooRound.length && !(state.dialog || state.allowShadow)) push('radius-scale', `超出 12px 的普通圆角: ${tooRound.join(', ')}`)

  if (!state.allowShadow) {
    const stray = metrics.shadows.filter((s) => !s.fixed && !s.inDialog && !s.ring)
    if (stray.length) push('shadow-discipline', `${stray.length} 处非浮层阴影`)
  }

  if (png.inkCoverage < 0.02) push('not-blank', `ink coverage ${png.inkCoverage}`)
  if (png.greenRatio > 0.06) push('brand-green-budget', `品牌绿占比 ${(png.greenRatio * 100).toFixed(2)}% > 6%`)

  if (viewport.id === '1280x720') {
    if (state.primaryCta) {
      const cta = opts.ctaRect
      if (!cta) push('primary-cta-in-viewport', `未找到主 CTA (${state.primaryCta})`)
      else if (!cta.inViewport) push('primary-cta-in-viewport', `主 CTA 不在 1280x720 首屏内 rect=${JSON.stringify(cta)}`)
    }
    if (metrics.preflight && !metrics.preflight.inViewport) push('dialog-fit-720p', `Preflight dialog 被裁切 rect=${JSON.stringify(metrics.preflight.rect)}`)
    if (state.dialog) {
      const dialog = opts.dialogRect
      if (dialog && !dialog.inViewport) push('dialog-fit-720p', `dialog 超出视口 rect=${JSON.stringify(dialog)}`)
    }
    if (state.blocked && opts.blockingCtaRect && opts.blockingCtaRect.inViewport === false) {
      push('blocked-cta-visible', '阻塞态主按钮不在首屏内')
    }
  }

  if (viewport.id === PRIMARY_VIEWPORT) {
    if (state.kind !== 'live' && metrics.distinctFontSizes > 6) {
      push('typography-scale', `${metrics.distinctFontSizes} 种字号: ${Object.keys(metrics.fontSizes).sort((a, b) => a - b).join(', ')}`)
    }
    if (state.nav) {
      const expected = ['首页', '求职目标', '练习', '历史', '我的成竹']
      const labels = metrics.navLabels ?? []
      const missing = expected.filter((label) => !labels.includes(label))
      if (missing.length) push('primary-nav', `主导航缺少 ${missing.join(', ')} (实际: ${labels.join('/')})`)
      if (labels.includes('资料库')) push('primary-nav', '资料库不应出现在主导航')
    }
    if (state.cueRules) {
      if (metrics.cueBullets != null && metrics.cueBullets > 3) push('cue-max-three-bullets', `Cue 第一层 ${metrics.cueBullets} 条`)
      if (metrics.transcriptCollapsed === false) push('transcript-secondary', 'Transcript 默认未折叠')
      if (metrics.live.cue) {
        const cue = metrics.live.cue
        if (cue.h > 340) push('live-cue-height', `Cue 高度 ${cue.h}px > 340px`)
      }
      if (metrics.live.statusLine && metrics.live.statusLine.h > 56) {
        push('live-compact-status', `状态行高度 ${metrics.live.statusLine.h}px > 56px`)
      }
    }
    if (state.kind === 'studio' || state.kind === 'setup') {
      // "Warm neutral canvas" is contractual (R1/R2). This catches the failure
      // mode a green-pixel budget cannot see: neutrals quietly tinted teal, which
      // makes the whole product read green even with 1% accent coverage.
      const coldNeutrals = Object.entries(metrics.neutralTint ?? {})
        .filter(([, value]) => value.chroma > 0.006 && (value.hue < 45 || value.hue > 125))
      if (coldNeutrals.length) {
        push('neutral-tint', `中性色偏冷/偏青: ${coldNeutrals.map(([name, value]) => `${name}(H${value.hue} C${value.chroma})`).join(', ')}`)
      }
      const accent = metrics.accentTint
      if (accent && (accent.hue < 125 || accent.hue > 160)) {
        push('accent-bamboo', `品牌色相 ${accent.hue}° 不在竹绿区间 125–160`)
      }
    }
    if (opts.runtime) {
      const runtime = opts.runtime
      if (runtime.domNodes > RUNTIME_BUDGET.domNodes) push('runtime-dom', `DOM 节点 ${runtime.domNodes} > ${RUNTIME_BUDGET.domNodes}`)
      if (runtime.longTaskMs > RUNTIME_BUDGET.longTaskMs) push('runtime-longtask', `长任务累计 ${runtime.longTaskMs}ms > ${RUNTIME_BUDGET.longTaskMs}ms`)
      if (runtime.heapMb != null && runtime.heapMb > RUNTIME_BUDGET.heapMb) push('runtime-heap', `JS 堆 ${runtime.heapMb}MB > ${RUNTIME_BUDGET.heapMb}MB`)
    }
    if (opts.a11y) {
      const a11y = opts.a11y
      const serious = (a11y.violations ?? []).filter((violation) => violation.impact === 'serious' || violation.impact === 'critical')
      if (serious.length) {
        push('axe-serious', serious.map((violation) => `${violation.id}(${violation.impact}): ${violation.nodes[0] ?? ''}`).join(' | '))
      }
      if (a11y.focusRingMissing?.length) {
        push('focus-visible', `${a11y.focusRingMissing.length} 个焦点停靠点没有焦点环: ${a11y.focusRingMissing.slice(0, 3).join(', ')}`)
      }
      if (a11y.focusInsideDialog === false) push('dialog-focus', '打开时焦点不在 dialog 内')
      if (a11y.trapEscaped) push('dialog-focus-trap', 'Tab 把焦点移出了 modal')
      if (a11y.escapeCloses === false) push('dialog-escape', 'Escape 没有关闭 dialog')
    }
    if (state.expectText) {
      // Truth boundaries must stay individually readable: a surface may not
      // collapse "direct evidence / user confirmed / no evidence / generic
      // knowledge / quick note" into one generic "verified" label.
      const missing = state.expectText.filter((token) => !metrics.bodyTextSample.includes(token))
      if (missing.length) push('evidence-boundaries', `缺少语义标签: ${missing.join(', ')}`)
    }
    if (state.prepareOrder) {
      const text = metrics.bodyTextSample
      const order = ['下一场', '下一重点', '准备缺口', '深挖', '追问链'].map((token) => ({ token, index: text.indexOf(token) }))
      const present = order.filter((o) => o.index >= 0)
      if (present.length < 2) push('prepare-order', `Goal Prepare 结构标记缺失: ${JSON.stringify(order)}`)
      else if (present.some((o, i) => i > 0 && o.index < present[i - 1].index)) {
        push('prepare-order', `Goal Prepare 顺序错乱: ${present.map((o) => `${o.token}@${o.index}`).join(' ')}`)
      }
    }
  }

  for (const forbidden of FORBIDDEN_TEXT) {
    if (forbidden.re.test(metrics.bodyTextSample)) push('forbidden-copy', `${forbidden.why}: ${forbidden.re}`)
  }
  if (metrics.animations > 0) push('reduced-motion', `${metrics.animations} 个元素在 reduced-motion 下仍有动画`)

  return failures
}

async function main() {
  if (!existsSync(path.join(DIST, 'index.html'))) {
    console.error('缺少 frontend/dist/index.html；先运行 npm run build')
    process.exit(2)
  }
  const server = await startServer()
  const browser = await chromium.launch()
  const report = {
    generatedAt: new Date().toISOString(),
    head: process.env.HVA_HEAD ?? '',
    branch: process.env.HVA_BRANCH ?? '',
    out: OUT,
    viewports: VIEWPORTS.map((v) => v.id),
    states: [],
    failures: [],
  }

  const overrideFor = (state) => (pathname, method) => {
    const own = state.mocks ? state.mocks(pathname, method) : undefined
    if (own !== undefined) return own
    return resolveApiPayload(pathname, method)
  }

  const only = (process.env.HVA_ONLY ?? '').split(',').map((item) => item.trim()).filter(Boolean)
  const selectedStates = only.length ? STATES.filter((state) => only.includes(state.id)) : STATES
  for (const state of selectedStates) {
    for (const viewport of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        deviceScaleFactor: 1,
        reducedMotion: 'reduce',
        colorScheme: 'light',
      })
      await context.addInitScript(mockWsInitScript, { messages: state.messages ?? COMMON_WS_BOOTSTRAP })
      await context.addInitScript(runtimeProbeInit)
      if (state.localStorage) {
        await context.addInitScript((entries) => {
          for (const [key, value] of Object.entries(entries)) {
            try { localStorage.setItem(key, value) } catch { /* noop */ }
          }
        }, state.localStorage)
      }
      const override = overrideFor(state)
      await context.route('**/api/**', async (route) => {
        const url = new URL(route.request().url())
        const method = route.request().method()
        let payload
        try {
          payload = override(url.pathname, method)
        } catch {
          payload = undefined
        }
        const resolved = payload === undefined ? resolveApiPayload(url.pathname, method) : payload
        const status = resolved && resolved.detail === 'Not found' ? 404 : 200
        await route.fulfill({ status, contentType: 'application/json; charset=utf-8', body: JSON.stringify(resolved ?? {}) })
      })

      const page = await context.newPage()
      const consoleErrors = []
      const readyWarnings = []
      const pageErrors = []
      page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 300)) })
      page.on('pageerror', (error) => pageErrors.push(String(error).slice(0, 300)))

      let failure = null
      try {
        await page.goto(`${BASE}${state.url}`, { waitUntil: 'domcontentloaded' })
        try {
          await state.ready(page, viewport)
        } catch (readyError) {
          readyWarnings.push(String(readyError).split('\n')[0])
        }
        await page.evaluate(() => document.fonts?.ready)
        await page.waitForTimeout(300)

        const dir = viewport.id === PRIMARY_VIEWPORT ? state.dir : '14-responsive'
        await mkdir(path.join(OUT, dir), { recursive: true })
        const shot = path.join(OUT, dir, `${state.id}-${viewport.id}.png`)
        await page.screenshot({ path: shot, fullPage: false })
        const metrics = await measure(page)
        const runtime = viewport.id === PRIMARY_VIEWPORT ? await measureRuntime(page) : null
        let ctaRect = null
        if (state.primaryCta) {
          const locator = page.locator(state.primaryCta).first()
          if (await locator.count()) {
            const box = await locator.boundingBox()
            const vp = page.viewportSize()
            ctaRect = box && vp ? {
              x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height),
              inViewport: box.x >= -1 && box.y >= -1 && box.x + box.width <= vp.width + 1 && box.y + box.height <= vp.height + 1,
            } : null
          }
        }
        let dialogRect = null
        if (state.dialog) {
          const dialog = page.getByRole('dialog').first()
          if (await dialog.count()) {
            const box = await dialog.boundingBox()
            const vp = page.viewportSize()
            dialogRect = box && vp ? {
              x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height),
              inViewport: box.x >= -1 && box.y >= -1 && box.x + box.width <= vp.width + 1 && box.y + box.height <= vp.height + 1,
            } : null
          }
        }
        let blockingCtaRect = null
        if (state.blockingCta) {
          const locator = page.locator(state.blockingCta).first()
          if (await locator.count()) {
            const box = await locator.boundingBox()
            const vp = page.viewportSize()
            blockingCtaRect = box && vp ? {
              x: Math.round(box.x), y: Math.round(box.y), w: Math.round(box.width), h: Math.round(box.height),
              inViewport: box.x >= -1 && box.y >= -1 && box.x + box.width <= vp.width + 1 && box.y + box.height <= vp.height + 1,
            } : null
          }
        }


        const a11y = viewport.id === PRIMARY_VIEWPORT
          ? await auditAccessibility(page, { dialog: Boolean(state.dialog) })
          : null
        const png = await analysePng(shot)
        const failures = ruleFailures(state, viewport, metrics, png, { ctaRect, dialogRect, blockingCtaRect, a11y, runtime })
        report.states.push({
          id: state.id,
          dir,
          label: state.label,
          viewport: viewport.id,
          screenshot: path.relative(REPO, shot).replace(/\\/g, '/'),
          png,
          metrics,
          ctaRect,
          dialogRect,
          consoleErrors,
          readyWarnings,
          a11y,
          runtime,
          pageErrors,
          failures,
        })
        report.failures.push(...failures)
      } catch (error) {
        failure = String(error).split('\n')[0]
        report.failures.push({ state: state.id, viewport: viewport.id, rule: 'render', detail: failure })
        report.states.push({ id: state.id, viewport: viewport.id, label: state.label, error: failure, consoleErrors, pageErrors })
      } finally {
        await context.close()
      }
    }
  }

  await browser.close()
  server.close()

  await mkdir(OUT, { recursive: true })
  await writeFile(path.join(OUT, 'hva-metrics.json'), JSON.stringify(report, null, 2), 'utf8')

  const statesOk = new Set(report.states.filter((s) => !s.error && s.failures.length === 0).map((s) => s.id))
  console.log(`\nHVA states: ${STATES.length} · viewports: ${VIEWPORTS.length} · screenshots: ${report.states.filter((s) => s.screenshot).length}`)
  for (const state of STATES) {
    const rows = report.states.filter((s) => s.id === state.id)
    const bad = rows.filter((s) => s.error || s.failures.length)
    const primary = rows.find((s) => s.viewport === PRIMARY_VIEWPORT)
    const sizes = primary?.metrics?.distinctFontSizes ?? '?'
    const ink = primary?.png?.inkCoverage ?? '?'
    const status = bad.length ? `FAIL (${bad.length})` : 'PASS'
    console.log(`  ${status.padEnd(9)} ${state.id.padEnd(24)} sizes=${String(sizes).padEnd(3)} ink=${ink}`)
    for (const row of bad) {
      for (const f of row.failures ?? []) console.log(`             - [${row.viewport}] ${f.rule}: ${f.detail}`)
      if (row.error) console.log(`             - [${row.viewport}] render error: ${row.error}`)
      if (row.readyWarnings?.length) console.log(`             ~ [${row.viewport}] not-ready: ${row.readyWarnings[0].slice(0, 160)}`)
    }
  }
  const consoleErr = report.states.filter((s) => (s.consoleErrors?.length ?? 0) > 0)
  if (consoleErr.length) {
    console.log(`\nconsole errors on ${consoleErr.length} states:`)
    for (const s of consoleErr.slice(0, 8)) console.log(`  ${s.id} [${s.viewport}]: ${s.consoleErrors[0]}`)
  }
  console.log(`\nmetrics: ${path.join(OUT, 'hva-metrics.json')}`)

  const runtimeRows = report.states.filter((state) => state.runtime)
  if (runtimeRows.length) {
    const worst = (key) => runtimeRows.reduce((max, state) => Math.max(max, state.runtime[key] ?? 0), 0)
    console.log(`runtime (max over ${runtimeRows.length} surfaces): dom ${worst('domNodes')} nodes · LCP ${worst('lcpMs')}ms · long tasks ${worst('longTaskMs')}ms · heap ${worst('heapMb')}MB`)
  }
  console.log(`failures: ${report.failures.length}`)
  if (report.failures.length) process.exitCode = 1
}

main().catch((error) => {
  console.error(error)
  process.exit(2)
})

async function auditAccessibility(page, { dialog }) {
  await page.addScriptTag({ path: AXE_PATH })
  const violations = await page.evaluate(async () => {
    const results = await window.axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] },
      resultTypes: ['violations'],
    })
    return results.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.slice(0, 3).map((node) => node.target.join(' ')),
    }))
  })

  const focusInsideDialog = dialog
    ? await page.evaluate(() => {
      const dialogEl = document.querySelector('[role="dialog"]')
      return Boolean(dialogEl && document.activeElement && dialogEl.contains(document.activeElement))
    })
    : null

  // Keyboard walk: every stop must show a focus indicator, and a modal must keep
  // focus inside itself for the whole walk.
  const focusRingMissing = []
  let trapEscaped = false
  for (let i = 0; i < 8; i += 1) {
    await page.keyboard.press('Tab')
    const stop = await page.evaluate(() => {
      const el = document.activeElement
      if (!el || el === document.body) return null
      const cs = getComputedStyle(el)
      const outline = cs.outlineStyle !== 'none' && Number.parseFloat(cs.outlineWidth) > 0
      const ring = cs.boxShadow !== 'none'
      const dialogEl = document.querySelector('[role="dialog"]')
      return {
        label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 24) || el.tagName,
        ring: outline || ring,
        inDialog: dialogEl ? dialogEl.contains(el) : null,
      }
    })
    if (!stop) continue
    if (!stop.ring) focusRingMissing.push(stop.label)
    if (dialog && stop.inDialog === false) trapEscaped = true
  }

  let escapeCloses = null
  if (dialog) {
    await page.keyboard.press('Escape')
    await page.waitForTimeout(300)
    escapeCloses = (await page.locator('[role="dialog"]').count()) === 0
  }

  return { violations, focusRingMissing, focusInsideDialog, trapEscaped, escapeCloses }
}
