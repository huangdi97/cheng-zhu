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
    })
    await page.goto('/')
    await page.getByRole('button', { name: '设置', exact: true }).click()
    await expect(page.getByLabel('共享隐私')).toHaveValue('OFF')
    await expect(page.getByLabel('人工协助策略')).toHaveValue('HUMAN_PRACTICE_ONLY')
    await expect(page.getByText('这不是安全或“不可检测”保证')).toBeVisible()
    await expect(page.getByText(/MIT License/)).toBeVisible()
  })
})

test.describe('v1.3 first-run onboarding', () => {
  test('fresh config shows the 11-step wizard and explains a failing model check', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: 'home' },
      apiOverrides: async (pathname, method) => {
        if (pathname === '/api/config' && method === 'GET') {
          const { resolveApiPayload } = await import('./fixtures/sample-data.mjs')
          return { ...resolveApiPayload('/api/config', 'GET'), onboarding_completed: false }
        }
        if (pathname === '/api/intelligence/diagnostics') {
          return {
            packaged: true, data_home: 'C:/Users/u/AppData/Roaming/Chengzhu', data_dir: 'x', logs_dir: 'y', data_writable: true,
            models: [{ index: 0, name: 'M', model: 'm', has_key: true, enabled: true }], has_usable_model: true, stt_provider: 'whisper',
            audio: { devices: [{ id: 1, name: 'Mic', is_loopback: false }, { id: 20000, name: 'Speakers (loopback)', is_loopback: true }] },
            has_microphone: true, has_system_audio: true, onboarding_completed: false,
          }
        }
        if (pathname === '/api/models/health/0') return { ok: false }
        if (pathname === '/api/models/health') return { health: { 0: '不可用' }, detail: { 0: 'Error code: 401 invalid api key' } }
        if (pathname === '/api/intelligence/diagnostics/explain') return { kind: 'auth', cause: 'API Key 无效或已过期', action: '在「设置 → 模型」里重新填写 API Key。' }
        return undefined
      },
    })
    await page.goto('/')
    const wizard = page.getByTestId('onboarding')
    await expect(wizard).toBeVisible({ timeout: 8000 })
    await expect(wizard.getByText('第 1 / 11 步')).toBeVisible()
    await wizard.getByRole('button', { name: '下一步' }).click()
    await expect(wizard.getByText('数据目录：C:/Users/u/AppData/Roaming/Chengzhu')).toBeVisible()
    await wizard.getByRole('button', { name: '下一步' }).click()
    await wizard.getByRole('button', { name: '测试连接' }).click()
    await expect(wizard.getByText(/原因：API Key 无效或已过期/)).toBeVisible()
    await wizard.getByRole('button', { name: '下一步' }).click()
    await wizard.getByRole('button', { name: '下一步' }).click()
    await expect(wizard.getByLabel('选择麦克风')).toBeVisible()
    await wizard.getByRole('button', { name: '下一步' }).click()
    await expect(wizard.getByLabel('选择系统音频设备')).toBeVisible()
    await wizard.getByRole('button', { name: '下一步' }).click()
    await expect(wizard.getByRole('radio', { name: '关闭（推荐默认）' })).toBeChecked()
  })

  test('first Goal flows into Guided First Practice before onboarding completes', async ({ context, page }) => {
    const GOAL = {
      id: 'goal-onboarding', title: 'MindRank · AIDD Agent Engineer', company: 'MindRank', role: 'AIDD Agent Engineer',
      jd: 'Agent / RAG', status: 'ACTIVE', stage: '准备中', next_interview_at: null, interview_round: '',
      goal_notes: '', selected_resume_id: null, selected_material_ids: [], selected_kb_ids: [],
      selected_quick_note_ids: [], active_question_bank_ids: [], next_focus_id: '', offer_state: 'NONE',
      role_family: 'AI_ML_ENGINEER', legacy_prep_space_id: null, application_id: null,
      last_opened_at: null, created_at: 1, updated_at: 1,
    }
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: async (pathname, method) => {
        if (pathname === '/api/config' && method === 'GET') {
          const { resolveApiPayload } = await import('./fixtures/sample-data.mjs')
          return { ...resolveApiPayload('/api/config', 'GET'), onboarding_completed: false }
        }
        if (pathname === '/api/intelligence/diagnostics') {
          return {
            packaged: true, data_home: 'C:/Users/u/AppData/Roaming/Chengzhu', data_dir: 'x', logs_dir: 'y', data_writable: true,
            models: [{ index: 0, name: 'M', model: 'm', has_key: true, enabled: true }], has_usable_model: true, stt_provider: 'whisper',
            audio: { devices: [{ id: 1, name: 'Mic', is_loopback: false }, { id: 20000, name: 'Speakers (loopback)', is_loopback: true }] },
            has_microphone: true, has_system_audio: true, onboarding_completed: false,
          }
        }
        if (pathname === '/api/product/goals' && method === 'POST') return GOAL
        if (pathname === '/api/product/practice' && method === 'POST') {
          return {
            practice_id: 'guided-1',
            config: { goal_id: GOAL.id, guided: true },
            question: { id: 'gq-1', seq: 1, question: '为什么在这个项目里选择 RAG？', move: 'OPEN', source: 'ROLE_BANK', persona_id: 'TECH_LEAD', persona_label: 'Tech Lead' },
            panel: { personas: [], current_speaker: 'TECH_LEAD', next_speaker: '', shared_topic: 'RAG', is_panel: false },
            pool_size: 1, total: 1,
          }
        }
        if (pathname === '/api/product/practice/guided-1/answer' && method === 'POST') {
          return {
            done: true, answered: 1,
            feedback: {
              content: {
                signals: { did_answer_question: 1 },
                findings: [{ signal: 'structure', dimension: 'structure', level: 2, finding: '结论可以更早。', evidence_from_actual_speech: '因为知识更新快。', action: '第一句直接给选择 RAG 的结论。' }],
                strengths: [],
              },
              delivery: { metrics: { answer_duration_s: 12, time_to_conclusion_s: 5, fillers: 0 }, advice: ['把结论提前到前 3 秒。'] },
            },
            report: { practice_id: 'guided-1', review_session_id: 1, goal_id: GOAL.id, turn_count: 1, went_well: [], to_improve: [], delivery: [] },
          }
        }
        // Exercise the explicitly-labelled fixture fallback. The real
        // guidance_fast transport is covered by the cue-first test above.
        if (pathname === '/api/ask' && method === 'POST') return { detail: 'Not found' }
        return undefined
      },
    })

    await page.goto('/')
    const wizard = page.getByTestId('onboarding')
    await expect(wizard).toBeVisible({ timeout: 8000 })

    // Advance to 第一个目标 without requiring real credentials/hardware.
    for (let i = 0; i < 8; i++) await wizard.getByRole('button', { name: '下一步' }).click()
    await expect(wizard.getByText('第一个目标')).toBeVisible()
    await wizard.getByLabel('目标公司').fill('MindRank')
    await wizard.getByLabel('目标岗位').fill('AIDD Agent Engineer')
    await wizard.getByRole('button', { name: '下一步' }).click()

    await expect(wizard.getByRole('heading', { name: '第一次演练' })).toBeVisible()
    await expect(wizard.getByRole('button', { name: '先完成这次演练' })).toBeDisabled()
    await wizard.getByRole('button', { name: '开始第一次演练' }).click()
    await expect(wizard.getByTestId('guided-question')).toContainText('为什么在这个项目里选择 RAG？')

    await wizard.getByRole('button', { name: '生成快速提示' }).click()
    await expect(wizard.getByRole('alert')).toBeVisible()
    await wizard.getByRole('button', { name: '使用标记明确的示例 Cue 继续' }).click()
    await expect(wizard.getByTestId('guided-fast-cue-fallback')).toContainText('不是实时模型证据')

    await wizard.getByLabel('第一次演练回答').fill('因为知识更新快，而且来源需要可追溯，所以我会优先用 RAG。')
    await wizard.getByRole('button', { name: '提交演练' }).click()
    await expect(wizard.getByTestId('guided-practice-complete')).toBeVisible()
    await expect(wizard.getByRole('button', { name: '下一步' })).toBeEnabled()
    await wizard.getByRole('button', { name: '下一步' }).click()
    await expect(wizard.getByText('准备好了。之后只记住一条路径')).toBeVisible()
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
