import { expect, test } from '@playwright/test'

import { COMMON_WS_BOOTSTRAP, installMocks } from './fixtures/setup.mjs'

const GOAL = {
  id: 'goal-1',
  title: '示例科技 · 高级后端开发工程师',
  company: '示例科技',
  role: '高级后端开发工程师',
  jd: '任职要求：熟悉 Redis、Kafka；熟悉 Kubernetes',
  status: 'ACTIVE',
  stage: '技术面',
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
  role_family: 'SOFTWARE_ENGINEER',
  legacy_prep_space_id: null,
  application_id: null,
  last_opened_at: null,
  created_at: 1,
  updated_at: 1,
  interviews: [],
  offer: { goal_id: 'goal-1', status: 'NONE', comp: '', deadline: null, notes: '', updated_at: null },
  next_focus: [],
  sessions: [],
}

const PREPARE = {
  goal_id: GOAL.id,
  next_focus: [],
  gap_map: [
    { topic: 'RAG 评估', status: 'REVIEW_WEAKNESS', source: 'review', priority: 'high', reason: '复盘中暴露的薄弱点（出现 2 次）' },
    { topic: 'Kubernetes', status: 'KNOWLEDGE_MATCH', source: 'job_alignment', priority: 'medium', reason: '可以讲通用知识，但没有个人经历来源' },
  ],
  attack_surface: [
    {
      claim_id: 'cl-a',
      text: '订单系统：负责整体架构设计，使用 Redis 做缓存，支撑日均 3 万 QPS',
      risks: ['指标会被追问口径与来源', '与岗位要求直接相关'],
      probes: ['整体架构是怎么设计的？', '缓存的一致性是怎么保证的？'],
    },
  ],
  question_graph: [
    { id: 'q1', text: '谈谈你对「Kubernetes」的理解？', kind: 'KNOWLEDGE', source: 'job_alignment', parent_id: '' },
    { id: 'q2', text: '你实际做过「Kubernetes」相关的事情吗？', kind: 'EXPERIENCE_BOUNDARY', source: 'job_alignment', parent_id: 'q1' },
    { id: 'q3', text: '如果让你来落地「Kubernetes」，你会怎么做？', kind: 'OPEN_DESIGN', source: 'job_alignment', parent_id: 'q2' },
  ],
  stories: {
    items: [],
    prompts: [{ competency: '团队协作', hint: '从真实经历整理', candidate_sources: [] }],
    coverage: {
      categories: [{ key: 'Collaboration', label: '团队协作', story_ids: [] }],
      missing: [{ key: 'Collaboration', label: '团队协作' }],
    },
  },
  has_jd: true,
  materials: { included: [], skipped: [], selected_ids: [] },
  pack_preview: { quick_notes: [], materials: [], legacy_prep_space_id: null },
}

async function openPrepare(context, page) {
  await installMocks(context, {
    messages: COMMON_WS_BOOTSTRAP,
    localStorage: { 'ia-color-scheme': 'vscode-light-plus' },
    apiOverrides: {
      'GET /api/product/goals/goal-1': GOAL,
      'GET /api/product/goals/goal-1/prepare': PREPARE,
      'GET /api/product/materials': { items: [] },
      'GET /api/product/quick-notes': { items: [] },
    },
  })
  await page.goto('/#/goals/goal-1/prepare')
  await expect(page.getByTestId('goal-room')).toBeVisible()
  await expect(page.getByRole('tab', { name: '准备' })).toHaveAttribute('aria-selected', 'true')
  await expect(page.getByRole('heading', { name: 'Gap Map' })).toBeVisible()
}

test.describe('Goal Prepare workspace', () => {
  test('shows gap map, attack surface, story gap and the question graph', async ({ context, page }) => {
    await openPrepare(context, page)

    await expect(page.getByText('RAG 评估')).toBeVisible()
    await expect(page.getByText('指标会被追问口径与来源 · 与岗位要求直接相关')).toBeVisible()
    await expect(page.getByText(/还没有「团队协作」故事/)).toBeVisible()
    await expect(page.getByRole('tree', { name: 'Question Graph' })).toBeVisible()
    await expect(page.getByText('如果让你来落地「Kubernetes」，你会怎么做？')).toBeVisible()
  })

  test('fits a phone-width viewport without horizontal overflow', async ({ context, page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openPrepare(context, page)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })
})
