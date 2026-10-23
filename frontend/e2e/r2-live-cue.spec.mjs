import { expect, test } from '@playwright/test'

import { COMMON_WS_BOOTSTRAP, installMocks } from './fixtures/setup.mjs'

// R2 Stage K/V/E: the Fast Cue is visible before any deep token, every cue
// shows its source, risk is shown, and an unsourced spoken claim raises a
// private correction prompt with the three same-session actions.
test.describe('R2 live cue-first', () => {
  test('guidance_fast renders cue + sources before the deep answer, and session claim warning offers corrections', async ({ context, page }) => {
    await installMocks(context, {
      messages: [
        ...COMMON_WS_BOOTSTRAP,
        { type: 'answer_start', delay: 40, id: 'qa-r2-1', question: '你实际用过 Redis Cluster 吗？', source: 'asr', model_name: 'GPT-4.1 Mini' },
        {
          type: 'guidance_fast',
          delay: 80,
          id: 'qa-r2-1',
          question_raw: '你实际用过 Redis Cluster 吗？',
          resolved_question: '你实际用过 Redis Cluster 吗？',
          direction: '先说边界，再讲理解与落地做法',
          cues: [
            { text: '先说边界：材料里没有「Redis Cluster」的直接经历', source: 'PERSONAL_EVIDENCE', provenance: 'NO_EVIDENCE' },
            { text: '可衔接：我用 Redis 管理 session state', source: 'PERSONAL_EVIDENCE', provenance: 'DIRECT_EVIDENCE' },
            { text: 'Cluster 通过槽位分片实现水平扩展', source: 'KB_KNOWLEDGE' },
          ],
          evidence_anchors: [],
          knowledge_sources: [],
          cautions: ['没有来源支持，不要说成“我做过/我负责”'],
          response_mode: 'EXPERIENCE_BOUNDARY_KNOWLEDGE',
          dialogue_act: 'NEW_QUESTION',
          content_type: 'EXPERIENCE',
          truth_requirement: 'PERSONAL_FACT_REQUIRED',
          source: 'AI',
          ttfug_user_ms: 920,
          ttfug_internal_ms: 310,
        },
        {
          type: 'answer_chunk',
          delay: 120,
          id: 'qa-r2-1',
          chunk: '完整回答正文：我没有 Redis Cluster 的生产经历，但可以说明它的槽位分片与高可用设计。',
        },
        {
          type: 'answer_done',
          delay: 150,
          id: 'qa-r2-1',
          question: '你实际用过 Redis Cluster 吗？',
          answer: '完整回答正文：我没有 Redis Cluster 的生产经历，但可以说明它的槽位分片与高可用设计。',
          think: '',
          model_name: 'GPT-4.1 Mini',
          first_token_ms: 120,
          total_ms: 150,
        },
        {
          type: 'session_claim_warning',
          delay: 60,
          id: 'sc-1',
          qa_id: 'qa-r2-1',
          text: '我们后来用了 Redis Cluster',
          message: '你刚才提到“我们后来用了 Redis Cluster”。当前 Interview Pack 没有材料支持这一陈述。',
          actions: [
            { id: 'slip', label: '这是口误' },
            { id: 'continue_no_expand', label: '继续，但不要扩展细节' },
            { id: 'later', label: '稍后确认' },
          ],
          private: true,
        },
      ],
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: 'assist' },
    })

    await page.goto('/')
    const cue = page.getByTestId('fast-cue').first()
    await expect(cue).toBeVisible({ timeout: 8000 })
    await expect(cue.getByText('先说边界：材料里没有「Redis Cluster」的直接经历')).toBeVisible()
    await expect(cue.getByText('个人来源').first()).toBeVisible()
    await expect(cue.getByText('资料')).toBeVisible()
    await expect(cue.getByText('没有来源支持，不要说成“我做过/我负责”')).toBeVisible()
    await expect(cue.getByText('提示 920ms（自说完）')).toBeVisible()

    // v1.3 hierarchy: the Fast Cue remains the first useful layer even after
    // the Deep Answer exists. Deep is opt-in, never dumped under the cue.
    const deepToggle = page.getByRole('button', { name: '展开完整回答' }).first()
    await expect(deepToggle).toBeVisible()
    await expect(page.getByText(/完整回答正文：/)).toHaveCount(0)
    await deepToggle.click()
    await expect(page.getByText(/完整回答正文：我没有 Redis Cluster/)).toBeVisible()

    const warning = page.getByTestId('session-claim-warning')
    await expect(warning).toBeVisible()
    await expect(warning.getByRole('button', { name: '这是口误' })).toBeVisible()
    await expect(warning.getByRole('button', { name: '继续，但不要扩展细节' })).toBeVisible()
    await expect(warning.getByRole('button', { name: '稍后确认' })).toBeVisible()

    // Unfrozen session: user language exposes the action, not pack internals.
    await expect(page.getByTestId('live-pack-bar')).toContainText('本场资料还没冻结')
  })

  test('share privacy defaults OFF and human assistance defaults to practice only in settings', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: 'home' },
      apiOverrides: {
        'GET /api/product/settings/layers': {
          items: {
            share_privacy_mode: {
              value: 'OFF', origin: 'SYSTEM', origin_label: '系统默认', label: '共享隐私', group: 'privacy',
              goal_value: null, session_value: null, global_value: 'OFF',
            },
            speech_adoption_analytics_live: {
              value: false, origin: 'SYSTEM', origin_label: '系统默认', label: 'Live 表达分析', group: 'privacy',
              goal_value: null, session_value: null, global_value: false,
            },
            ai_policy_mode: {
              value: 'AI_ALLOWED', origin: 'SYSTEM', origin_label: '系统默认', label: 'AI 辅助', group: 'live',
              goal_value: null, session_value: null, global_value: 'AI_ALLOWED',
            },
            human_assistance_policy: {
              value: 'HUMAN_PRACTICE_ONLY', origin: 'SYSTEM', origin_label: '系统默认', label: '人工协助策略', group: 'live',
              goal_value: null, session_value: null, global_value: 'HUMAN_PRACTICE_ONLY',
            },
            proactive_guidance_enabled: {
              value: true, origin: 'SYSTEM', origin_label: '系统默认', label: '主动提示', group: 'live',
              goal_value: null, session_value: null, global_value: true,
            },
          },
          origin_labels: {},
        },
      },
    })
    await page.goto('/#/settings/privacy')
    await expect(page.getByLabel('共享隐私', { exact: true })).toHaveValue(JSON.stringify('OFF'))
    await expect(page.getByText(/不是安全.*不可检测.*保证/).first()).toBeVisible()
    await expect(page.getByText(/MIT License/)).toBeVisible()

    await page.goto('/#/settings/live')
    await expect(page.getByLabel('人工协助策略', { exact: true })).toHaveValue(JSON.stringify('HUMAN_PRACTICE_ONLY'))
  })
})

const ONBOARDING_DIAGNOSTICS = {
  packaged: true,
  data_home: 'C:/Users/u/AppData/Roaming/Chengzhu',
  data_dir: 'x',
  logs_dir: 'y',
  data_writable: true,
  models: [{ index: 0, name: 'M', model: 'm', has_key: true, enabled: true }],
  has_usable_model: true,
  stt_provider: 'whisper',
  audio: { devices: [{ id: 1, name: 'Mic', is_loopback: false }, { id: 20000, name: 'Speakers (loopback)', is_loopback: true }] },
  has_microphone: true,
  has_system_audio: false,
  onboarding_completed: false,
}

const ONBOARDING_GOAL = {
  id: 'goal-onboarding',
  title: 'MindRank · AIDD Agent Engineer',
  company: 'MindRank',
  role: 'AIDD Agent Engineer',
  jd: 'Agent / RAG',
  status: 'ACTIVE',
  stage: '准备中',
  next_interview_at: null,
  interview_round: '',
  goal_notes: '',
  selected_resume_id: null,
  selected_material_ids: [],
  selected_kb_ids: [],
  selected_quick_note_ids: [],
  active_question_bank_ids: [],
  next_focus_id: '',
  offer_state: 'NONE',
  role_family: 'AI_ML_ENGINEER',
  legacy_prep_space_id: null,
  application_id: null,
  last_opened_at: null,
  created_at: 1,
  updated_at: 1,
  interviews: [],
  offer: { goal_id: 'goal-onboarding', status: 'NONE', comp: '', deadline: null, notes: '', updated_at: null },
  next_focus: [],
  sessions: [],
}

test.describe('v2 first-run orientation', () => {
  test('first run asks three questions instead of walking a setup wizard', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: 'home' },
      apiOverrides: async (pathname, method) => {
        if (pathname === '/api/config' && method === 'GET') {
          const { resolveApiPayload } = await import('./fixtures/sample-data.mjs')
          return { ...resolveApiPayload('/api/config', 'GET'), onboarding_completed: false }
        }
        if (pathname === '/api/intelligence/diagnostics') return ONBOARDING_DIAGNOSTICS
        return undefined
      },
    })
    await page.goto('/')
    const wizard = page.getByTestId('onboarding')
    await expect(wizard).toBeVisible({ timeout: 8000 })

    // 01 理解 — the product explains itself, it does not configure the machine.
    await expect(wizard.getByText('FIRST RUN · 1 / 3')).toBeVisible()
    await expect(wizard.getByRole('heading', { name: '成竹围绕一个目标工作' })).toBeVisible()
    await expect(wizard.getByText('理解', { exact: false }).first()).toBeVisible()
    await expect(wizard.getByRole('button', { name: '测试连接' })).toHaveCount(0)
    await expect(wizard.getByLabel('选择麦克风')).toHaveCount(0)
    await expect(wizard.getByText('打开模型设置')).toHaveCount(0)

    // 02 创建目标 — only what is needed to say which interview this is.
    await wizard.getByTestId('onboarding-next').click()
    await expect(wizard.getByRole('heading', { name: '你下一场在准备什么？' })).toBeVisible()
    await expect(wizard.getByTestId('onboarding-goal-company')).toBeVisible()
    await expect(wizard.getByTestId('onboarding-goal-role')).toBeVisible()
    await expect(wizard.getByTestId('onboarding-goal-jd')).toBeVisible()
    await expect(wizard.getByText('下一轮信息（可选）')).toBeVisible()

    // 03 就绪 — machine status is reported honestly and never gates entry.
    await expect(wizard.getByTestId('onboarding-finish')).toHaveCount(0)
    await wizard.getByTestId('onboarding-goal-role').fill('AIDD Agent Engineer')
    await wizard.getByTestId('onboarding-next').click()
    await expect(wizard.getByTestId('onboarding-complete-step')).toBeVisible()
    await expect(wizard.getByText('这台电脑')).toBeVisible()
    await expect(wizard.getByText('未就绪')).toBeVisible()
    await expect(wizard.getByText('上场前还会再检查一次，缺什么就在那一步修。')).toBeVisible()
    await expect(wizard.getByTestId('onboarding-finish')).toBeEnabled()
  })

  test('the first Goal created here leads into its Goal Room', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: async (pathname, method) => {
        if (pathname === '/api/config' && method === 'GET') {
          const { resolveApiPayload } = await import('./fixtures/sample-data.mjs')
          return { ...resolveApiPayload('/api/config', 'GET'), onboarding_completed: false }
        }
        if (pathname === '/api/intelligence/diagnostics') return ONBOARDING_DIAGNOSTICS
        if (pathname === '/api/product/goals' && method === 'POST') return ONBOARDING_GOAL
        if (pathname === '/api/product/goals/goal-onboarding' && method === 'GET') return ONBOARDING_GOAL
        if (pathname === '/api/product/goals/goal-onboarding/prepare' && method === 'GET') {
          return { goal_id: 'goal-onboarding', next_focus: [], gap_map: [], attack_surface: [], question_graph: [], stories: { items: [], prompts: [], coverage: { categories: [], missing: [] } }, has_jd: true, materials: { included: [], skipped: [], selected_ids: [] }, pack_preview: { quick_notes: [], materials: [], legacy_prep_space_id: null } }
        }
        return undefined
      },
    })
    await page.goto('/')
    const wizard = page.getByTestId('onboarding')
    await expect(wizard).toBeVisible({ timeout: 8000 })
    await wizard.getByTestId('onboarding-next').click()
    await wizard.getByTestId('onboarding-goal-company').fill('MindRank')
    await wizard.getByTestId('onboarding-goal-role').fill('AIDD Agent Engineer')
    await wizard.getByTestId('onboarding-goal-jd').fill('Agent / RAG')
    await wizard.getByTestId('onboarding-next').click()
    await expect(wizard.getByTestId('onboarding-complete-step')).toBeVisible()
    await expect(wizard.getByText('目标已建立。', { exact: false })).toBeVisible()
    await wizard.getByTestId('onboarding-finish').click()
    await expect(page).toHaveURL(/#\/goals\/goal-onboarding/)
    await expect(page.getByTestId('goal-room')).toBeVisible()
  })
})

test.describe('R2 human coach', () => {
  test('coach cue shows as advice, not as a source', async ({ context, page }) => {
    await installMocks(context, {
      messages: [
        ...COMMON_WS_BOOTSTRAP,
        { type: 'coach_cue', delay: 80, id: 'cc-1', coach_session_id: 'coach-1', text: '先说边界，再讲你做过的 Redis', voice_url: '', source: 'HUMAN_COACH', is_evidence: false, created_at: 1 },
      ],
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: 'assist' },
    })
    await page.goto('/')
    const cues = page.getByTestId('coach-cues')
    await expect(cues).toBeVisible({ timeout: 8000 })
    await expect(cues.getByText('教练建议')).toBeVisible()
    await expect(cues.getByText('（建议，不是事实来源）')).toBeVisible()
    await expect(cues.getByText('先说边界，再讲你做过的 Redis')).toBeVisible()
  })

  test('practice setup offers a Human Coach panel when explicitly enabled', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: {
        'GET /api/product/goals': { items: [] },
        'GET /api/product/practice/options': {
          rounds: [{ key: 'TECHNICAL', label: '技术一面' }],
          demeanors: [{ key: 'NEUTRAL', label: '中性' }],
          difficulties: [{ key: 'STANDARD', label: '标准' }],
          sources: [{ key: 'ROLE_BANK', label: '岗位题库' }],
          personas: [{ key: 'TECH_LEAD', label: 'Tech Lead', concern: '技术深度', followup_style: '深挖', demeanor: 'NEUTRAL' }],
          defaults: { round: 'TECHNICAL', focus: null, demeanor: 'NEUTRAL', difficulty: 'STANDARD', sources: ['ROLE_BANK'] },
        },
      },
    })
    await page.goto('/#/practice')
    await expect(page.getByTestId('practice-setup')).toBeVisible()

    await page.getByRole('checkbox', { name: '邀请真人教练一起练' }).check()
    const panel = page.getByTestId('coach-panel')
    await expect(panel).toBeVisible({ timeout: 8000 })
    await expect(panel.getByText('人工教练（练习）')).toBeVisible()
    await expect(panel.getByRole('checkbox', { name: '转写' })).toBeChecked()
    await expect(panel.getByRole('checkbox', { name: 'AI Cue' })).not.toBeChecked()
  })
})
