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
        { type: 'answer_start', delay: 80, id: 'qa-r2-1', question: '你实际用过 Redis Cluster 吗？', source: 'asr', model_name: 'GPT-4.1 Mini' },
        {
          type: 'guidance_fast',
          delay: 40,
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

    const warning = page.getByTestId('session-claim-warning')
    await expect(warning).toBeVisible()
    await expect(warning.getByRole('button', { name: '这是口误' })).toBeVisible()
    await expect(warning.getByRole('button', { name: '继续，但不要扩展细节' })).toBeVisible()
    await expect(warning.getByRole('button', { name: '稍后确认' })).toBeVisible()

    // Unfrozen session: the pack bar says so and offers the freeze path.
    await expect(page.getByTestId('live-pack-bar')).toContainText('Interview Pack 未冻结')
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
