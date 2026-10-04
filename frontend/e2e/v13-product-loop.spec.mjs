import { expect, test } from '@playwright/test'
import { COMMON_WS_BOOTSTRAP, installMocks } from './fixtures/setup.mjs'

const GOAL = {
  id: 'goal-v13', title: 'MindRank · AIDD Agent Engineer', company: 'MindRank', role: 'AIDD Agent Engineer',
  jd: '负责 Agent / RAG / CADD 相关产品与工程落地。', status: 'ACTIVE', stage: '技术二面',
  next_interview_at: 1_800_000_000, interview_round: 'TECHNICAL', goal_notes: '',
  selected_resume_id: 3, selected_material_ids: [], selected_kb_ids: [], selected_quick_note_ids: ['note-1'],
  active_question_bank_ids: ['bank-1'], next_focus_id: 'focus-1', offer_state: 'NONE',
  role_family: 'AI_ML_ENGINEER', legacy_prep_space_id: null, application_id: null,
  last_opened_at: null, created_at: 1, updated_at: 1,
}
const GOAL_DETAIL = {
  ...GOAL, interviews: [],
  offer: { goal_id: GOAL.id, status: 'NONE', comp: '', deadline: null, notes: '', updated_at: null },
  next_focus: [{ id: 'focus-1', goal_id: GOAL.id, type: 'KNOWLEDGE_GAP', title: 'Redis Cluster',
    reason: '岗位要求高可用；当前只有 Redis session state 的个人来源。', source_kind: 'DERIVED',
    source_ref: '', priority: 'HIGH', status: 'ACTIVE' }],
  sessions: [],
}
const PREFLIGHT = {
  goal: { id: GOAL.id, title: GOAL.title },
  items: [
    { key: 'goal', label: '目标', value: GOAL.title, origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'resume', label: '简历', value: '郝磊-简历.pdf', origin: 'PERSON', origin_label: '我的成竹', ok: true, hint: '' },
    { key: 'quick_notes', label: '速记', value: 1, origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'answer_language', label: '回答语言', value: 'FOLLOW_INTERVIEW', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'whisper_language', label: '识别语言', value: 'auto', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'active_model', label: '模型', value: 'Fake', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'audio', label: '音频', value: '就绪', origin: 'SYSTEM', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'stt', label: '语音识别', value: '就绪', origin: 'SYSTEM', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'screen_context', label: '屏幕上下文', value: '关闭', origin: 'SYSTEM', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'ai_policy_mode', label: 'AI 辅助', value: 'AI_ALLOWED', origin: 'GOAL', origin_label: 'Goal 默认', ok: true, hint: '' },
    { key: 'human_assistance_policy', label: '真人辅助', value: 'HUMAN_PRACTICE_ONLY', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
    { key: 'share_privacy_mode', label: '共享隐私', value: 'OFF', origin: 'GLOBAL', origin_label: '系统默认', ok: true, hint: '' },
  ],
  blockers: [], share_privacy_note: '共享隐私默认关闭；它不是不可检测保证。',
}
const PIN = {
  id: 'pin-1', session_kind: 'LIVE', session_id: 'live-1', turn_id: '', goal_id: GOAL.id,
  tag: 'IMPORTANT', tag_label: '重要', question: '', transcript_excerpt: '',
  note: '面试官强调上线后的 Agent eval。', ts: 1_800_000_010,
}
const REFLECTION = {
  session_kind: 'REVIEW', session_ref: '902', goal_id: GOAL.id, title: 'MindRank · 技术二面',
  first_screen: {
    next_step: { kind: 'PIN', title: 'Agent eval', reason: '你把它标记成了重要时刻。', pin_id: PIN.id, goal_id: GOAL.id },
    pinned_moments: [PIN], went_well: [], to_improve: [], fact_checks: [], story_opportunities: [],
  },
  delivery: [], timeline: [], actions: ['SET_NEXT_FOCUS', 'PRACTICE_THIS'], ask_cue_feedback: true,
}
const OPTIONS = {
  rounds: [{ key: 'TECHNICAL', label: '技术一面' }],
  demeanors: [{ key: 'NEUTRAL', label: '中性' }, { key: 'SKEPTICAL', label: '怀疑型' }],
  difficulties: [{ key: 'STANDARD', label: '标准' }, { key: 'PRESSURE', label: '压力' }],
  sources: [{ key: 'GOAL_GRAPH', label: '目标问题图' }, { key: 'ROLE_BANK', label: '岗位题库' }],
  personas: [
    { key: 'TECH_LEAD', label: 'Tech Lead', concern: '技术深度', followup_style: '深挖设计边界', demeanor: 'NEUTRAL' },
    { key: 'HIRING_MANAGER', label: 'Hiring Manager', concern: 'Ownership', followup_style: '追问影响与取舍', demeanor: 'SKEPTICAL' },
    { key: 'PRODUCT_PARTNER', label: 'Product Partner', concern: '产品判断', followup_style: '追问用户价值', demeanor: 'NEUTRAL' },
  ],
  defaults: { round: 'TECHNICAL', focus: null, demeanor: 'NEUTRAL', difficulty: 'STANDARD', sources: ['GOAL_GRAPH', 'ROLE_BANK'] },
}

test.describe('v1.3 Goal-centered product loop', () => {
  test('Goal → Preflight → Live → Pin → Reflection keeps one Goal context', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: (pathname, method) => {
        if (pathname === '/api/product/goals' && method === 'GET') return { items: [GOAL] }
        if (pathname === '/api/product/goals/goal-v13' && method === 'GET') return GOAL_DETAIL
        if (pathname === '/api/product/live/preflight' && method === 'POST') return PREFLIGHT
        if (pathname === '/api/product/live/start' && method === 'POST') return { session_id: 'live-1', goal_id: GOAL.id, pack: { id: 'pack-1' } }
        if (pathname === '/api/product/pins' && method === 'POST') return PIN
        if (pathname === '/api/product/reflection/review/902' && method === 'GET') return REFLECTION
        return undefined
      },
    })

    await page.goto('/#/goals/goal-v13')
    await expect(page.getByTestId('goal-room')).toBeVisible()
    await page.getByTestId('go-live').click()
    await expect(page.getByTestId('preflight')).toBeVisible()
    await expect(page.getByText('Goal 默认').first()).toBeVisible()
    await expect(page.getByText('我的成竹').first()).toBeVisible()
    await expect(page.getByText('共享隐私默认关闭')).toBeVisible()

    await page.getByTestId('preflight-start').click()
    await expect(page).toHaveURL(/#\/live\/live-1/)
    await expect(page.getByTestId('live-status-line')).toContainText('MindRank')

    await page.keyboard.press('Control+P')
    await expect(page.getByTestId('pin-dialog')).toBeVisible()
    await page.getByRole('radio', { name: '重要' }).click()
    await page.getByLabel('备注（可选）').fill(PIN.note)
    await page.getByTestId('pin-dialog').getByRole('button', { name: '标记', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('已标记')

    await page.goto('/#/reflection/review/902')
    await expect(page.getByTestId('reflection-page')).toBeVisible()
    await expect(page.getByText(PIN.note)).toBeVisible()
    await expect(page.getByText('Agent eval').first()).toBeVisible()
  })

  test('Panel Practice separates personas and Content vs Delivery feedback', async ({ context, page }) => {
    let startBody = null
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: async (pathname, method, request) => {
        if (pathname === '/api/product/goals' && method === 'GET') return { items: [GOAL] }
        if (pathname === '/api/product/practice/options' && method === 'GET') return OPTIONS
        if (pathname === '/api/product/practice' && method === 'POST') {
          startBody = request.postDataJSON()
          return {
            practice_id: 'practice-1', config: startBody,
            question: { id: 'q1', seq: 1, question: '你会怎么设计 Agent eval？', move: 'OPEN', source: 'GOAL_GRAPH', persona_id: 'TECH_LEAD', persona_label: 'Tech Lead' },
            panel: { personas: OPTIONS.personas.slice(0, 2).map((p) => ({ id: p.key, label: p.label, concern: p.concern, followup_style: p.followup_style, demeanor: p.demeanor })),
              current_speaker: 'TECH_LEAD', next_speaker: 'HIRING_MANAGER', shared_topic: 'Agent eval', is_panel: true },
            pool_size: 6, total: 2,
          }
        }
        if (pathname === '/api/product/practice/practice-1' && method === 'GET') {
          return {
            status: 'ACTIVE', goal_id: GOAL.id, review_session_id: null,
            panel: { personas: OPTIONS.personas.slice(0, 2).map((p) => ({ id: p.key, label: p.label, concern: p.concern, followup_style: p.followup_style, demeanor: p.demeanor })),
              current_speaker: 'TECH_LEAD', next_speaker: 'HIRING_MANAGER', shared_topic: 'Agent eval', is_panel: true },
            turns: [{ id: 'q1', seq: 1, question: '你会怎么设计 Agent eval？', move: 'OPEN', source: 'GOAL_GRAPH', persona_id: 'TECH_LEAD', persona_label: 'Tech Lead', answer: '', content: {}, delivery: {} }],
          }
        }
        if (pathname === '/api/product/practice/practice-1/answer' && method === 'POST') {
          return {
            done: false, answered: 1,
            feedback: {
              content: { signals: { technical_depth: 0.7 }, findings: [{
                signal: 'technical_depth', dimension: 'technical_depth', level: 2,
                finding: '指标体系还缺少线上回归与失败案例。', evidence_from_actual_speech: '我会看成功率和延迟。',
                action: '补充回归集、失败分桶和人工复核闭环。',
              }], strengths: [] },
              delivery: { metrics: { answer_duration_s: 22, time_to_conclusion_s: 8, fillers: 1 }, advice: ['把结论提前到前 5 秒。'] },
            },
            next_question: { id: 'q2', seq: 2, question: '如果业务方质疑离线指标，你怎么处理？', move: 'CHALLENGE', source: 'FOLLOW_UP', persona_id: 'HIRING_MANAGER', persona_label: 'Hiring Manager' },
            panel: { personas: OPTIONS.personas.slice(0, 2).map((p) => ({ id: p.key, label: p.label, concern: p.concern, followup_style: p.followup_style, demeanor: p.demeanor })),
              current_speaker: 'HIRING_MANAGER', next_speaker: 'TECH_LEAD', shared_topic: 'Agent eval', is_panel: true },
          }
        }
        return undefined
      },
    })

    await page.goto('/#/practice')
    await page.getByLabel('求职目标').selectOption(GOAL.id)
    await page.getByText('小组面（2–3 位面试官轮流提问）').click()
    await page.getByText('Tech Lead', { exact: true }).click()
    await page.getByText('Hiring Manager', { exact: true }).click()
    await page.getByTestId('practice-start').click()

    await expect(page).toHaveURL(/#\/practice\/practice-1/)
    await expect(page.getByLabel('面试官')).toContainText('Tech Lead')
    await expect(page.getByLabel('面试官')).toContainText('Hiring Manager')
    expect(startBody?.personas).toEqual(['TECH_LEAD', 'HIRING_MANAGER'])

    await page.getByLabel('你的回答').fill('我会看成功率和延迟。')
    await page.getByTestId('practice-submit').click()
    await expect(page.getByLabel('内容')).toContainText('指标体系还缺少线上回归')
    await expect(page.getByLabel('表达')).toContainText('结论在 8s')
    await expect(page.getByTestId('practice-question')).toContainText('业务方质疑离线指标')
    await expect(page.getByLabel('面试官')).toContainText('Hiring Manager · 正在提问')
  })

  test('Goal trends stay explainable and never turn into an offer-probability score', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: {
        'GET /api/product/goals/goal-v13': GOAL_DETAIL,
        'GET /api/product/trends': {
          goal_id: GOAL.id,
          sessions: 4,
          dimensions: [
            { dimension: 'technical_depth', label: '技术深度', series: [1, 2, 2, 3], direction: 'IMPROVING', text: '最近几次回答的技术深度在改善。' },
            { dimension: 'ownership', label: 'Ownership', series: [2, 2, 1, 1], direction: 'REPEATING', text: '个人职责仍然反复不够清楚。' },
          ],
          delivery: { text: '结论出现得更早。', direction: 'IMPROVING', series: [18, 13, 9] },
          note: '同一 Goal 内的本地趋势，不是候选人排名。',
        },
      },
    })
    await page.goto('/#/goals/goal-v13')
    const trends = page.getByTestId('goal-progress-trends')
    await expect(trends).toBeVisible()
    await expect(trends).toContainText('技术深度')
    await expect(trends).toContainText('在改善')
    await expect(trends).toContainText('Ownership')
    await expect(page.getByText('这些是同一 Goal 内的练习/复盘观察')).toBeVisible()
    // A disclaimer may contain the words “录用概率”; what must never exist is
    // a pseudo-precise probability value presented as a product metric.
    await expect(page.getByText(/录用概率\s*[:：]?\s*\d+\s*%/)).toHaveCount(0)
  })

  test('v1.4 diagnostics renders six product-loop questions without claiming PMF', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: {
        'GET /api/product/goals': { items: [GOAL] },
        'GET /api/product/validation': {
          evidence_level: 'LOCAL_DEVICE_USAGE',
          real_user_validation: 'REAL_USER_VALIDATION_PENDING',
          A_goal_reuse: { goals: 2, goal_reopen_rate: 0.5, sessions_per_goal: 3.5 },
          B_reflection_to_prepare: { next_focus_from_reflection: 3, follow_through_rate: 0.667 },
          C_fast_cue_usefulness: { rendered: 8, usefulness: { speech_after_cue_rate: 0.75 } },
          D_practice_transfer: { measured: 2, improved: 1 },
          E_fact_inbox_burden: { backlog_size: 3, resolution_rate: 0.8 },
          F_quick_notes_and_pins: { quick_notes: { selected_into_pack: 4 }, pins: { next_focus_from_pin: 2 } },
          nudges: { shown: 2, dismissed: 1, actioned: 1, disabled: 0 },
          note: '本地产品分析。',
        },
      },
    })
    await page.goto('/#/settings/diagnostics')
    const summary = page.getByTestId('validation-summary')
    await expect(summary).toBeVisible()
    for (const title of ['Goal 是否持续复用', 'Reflection 是否改变下一步', 'Fast Cue 是否有帮助', 'Practice 是否迁移', 'Fact Inbox 是否成负担', 'Quick Notes / Pin 是否有价值']) {
      await expect(summary.getByText(title)).toBeVisible()
    }
    await expect(summary).toContainText('REAL_USER_VALIDATION_PENDING')
    await expect(summary).toContainText('不能')
    await expect(summary).toContainText('PMF')
  })

  test('Overlay 3.0 persists Dock × Interaction × Size and stays usable at 390px', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-dark-plus' },
      apiOverrides: {
        'GET /api/product/goals': { items: [GOAL] },
        'GET /api/product/settings/layers': { items: {}, origin_labels: {} },
      },
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/#/settings/live')
    await expect(page.getByTestId('overlay-prefs')).toBeVisible()

    await page.getByRole('radio', { name: '顶部' }).click()
    await page.getByRole('radio', { name: '穿透（点击落到下面的会议软件）' }).click()
    await page.getByRole('radio', { name: '紧凑' }).click()
    const saved = await page.evaluate(() => JSON.parse(localStorage.getItem('chengzhu-overlay-layout-v1') || '{}'))
    expect(saved).toMatchObject({ dock: 'TOP', interaction: 'PASSIVE', size: 'COMPACT' })

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })
})
