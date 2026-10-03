import { expect, test } from '@playwright/test'

import { COMMON_WS_BOOTSTRAP, installMocks } from './fixtures/setup.mjs'

const GOAL = {
  id: 'goal-mm',
  title: 'MiniMax · AI 产品工程师',
  company: 'MiniMax',
  role: 'AI 产品工程师',
  jd: '负责 AI 产品与 Agent 工作流，能够拆解真实业务问题。',
  status: 'ACTIVE',
  stage: '技术二面',
  next_interview_at: null,
  interview_round: 'TECHNICAL',
  goal_notes: '',
  selected_resume_id: 3,
  selected_material_ids: [],
  selected_kb_ids: [],
  selected_quick_note_ids: [],
  active_question_bank_ids: [],
  next_focus_id: '',
  offer_state: 'NONE',
  role_family: 'AI_PRODUCT_MANAGER',
  legacy_prep_space_id: null,
  application_id: 1,
  last_opened_at: null,
  created_at: 1,
  updated_at: 1,
}

const SESSION = {
  key: 'review:902',
  type: 'REAL',
  guided: false,
  reflection_ref: { session_kind: 'REVIEW', session_ref: '902' },
  review_session_id: 902,
  goal_id: GOAL.id,
  goal_title: GOAL.title,
  round: 'TECHNICAL',
  title: '二面复盘',
  panel: false,
  started_at: 1_790_000_000,
  ended_at: 1_790_000_900,
  turn_count: 6,
  has_reflection_actions: true,
}

const DETAIL = {
  ...GOAL,
  interviews: [],
  offer: { goal_id: GOAL.id, status: 'NONE', comp: '', deadline: null, notes: '', updated_at: null },
  next_focus: [],
  sessions: [SESSION],
}

function productMocks() {
  return {
    'GET /api/product/goals': { items: [GOAL] },
    'GET /api/product/goals/goal-mm': DETAIL,
    'GET /api/product/history': { items: [SESSION] },
  }
}

test.describe('Goal and History linkage', () => {
  test('phone-width Goal Room keeps the linked session visible without horizontal overflow', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: productMocks(),
    })

    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/#/goals')
    await page.getByRole('button', { name: /MiniMax · AI 产品工程师/ }).click()
    await expect(page.getByTestId('goal-room')).toBeVisible()
    await page.getByRole('tab', { name: /面试/ }).click()

    const realSection = page.getByRole('heading', { name: /真实面试 · 1/ })
    await expect(realSection).toBeVisible()
    await expect(page.getByRole('button', { name: /真实面试 · 技术面/ })).toBeVisible()

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })

  test('Goal Room and History expose the same linked session and open the same Reflection', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
      apiOverrides: productMocks(),
    })

    await page.goto('/#/goals/goal-mm/interviews')
    const goalSession = page.getByRole('button', { name: /真实面试 · 技术面/ })
    await expect(goalSession).toBeVisible()
    await goalSession.click()
    await expect(page).toHaveURL(/#\/reflection\/review\/902/)

    await page.goto('/#/history')
    const historySession = page.getByRole('button', { name: /真实面试 · 技术面 · MiniMax · AI 产品工程师/ })
    await expect(historySession).toBeVisible()
    await historySession.click()
    await expect(page).toHaveURL(/#\/reflection\/review\/902/)
  })
})
