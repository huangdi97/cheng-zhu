import { expect, test } from '@playwright/test'

import { COMMON_WS_BOOTSTRAP, installMocks } from './fixtures/setup.mjs'

const SPACE = {
  id: 7,
  title: '示例科技 · 高级后端',
  role: '高级后端开发工程师',
  company: '示例科技',
  jd_text: '任职要求：熟悉 Redis、Kafka；熟悉 Kubernetes',
  resume_text: '订单系统：负责整体架构设计，使用 Redis 做缓存，支撑日均 3 万 QPS',
  resume_history_id: null,
  insight_markdown: '',
  insight_status: 'idle',
  insight_error: '',
  questions: [],
  questions_status: 'idle',
  questions_error: '',
  skill_cards: [],
  skill_card_count: 0,
  created_at: 1,
  updated_at: 1,
}

const WORKSPACE = {
  job_id: 'job-1',
  company: '示例科技',
  title: '高级后端开发工程师',
  level: 'senior',
  technologies: ['Redis', 'Kafka', 'Kubernetes'],
  must_have: ['熟悉 Redis、Kafka', '熟悉 Kubernetes'],
  nice_to_have: [],
  likely_interview_dimensions: ['缓存设计与一致性', '容器化与编排'],
  alignment: {
    requirements: [
      { requirement_text: 'Redis', status: 'STRONG_MATCH', evidence_claim_ids: ['cl-a'], explanation: '简历/材料中有带动作动词的项目证据' },
      { requirement_text: 'Kubernetes', status: 'KNOWLEDGE_MATCH', evidence_claim_ids: [], explanation: '无候选人证据，但属于可由通用知识覆盖的技术域' },
    ],
  },
  workspace: {
    gap_map: [
      { topic: 'RAG 评估', status: 'REVIEW_WEAKNESS', source: 'review', priority: 'high', reason: '复盘中暴露的薄弱点（出现 2 次）' },
      { topic: 'Kubernetes', status: 'KNOWLEDGE_MATCH', source: 'job_alignment', priority: 'medium', reason: '可以用通用知识回答，但没有证据时不能说做过' },
    ],
    attack_surface: [
      {
        claim_id: 'cl-a',
        text: '订单系统：负责整体架构设计，使用 Redis 做缓存，支撑日均 3 万 QPS',
        truth_status: 'SUPPORTED',
        job_aligned: true,
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
      prompts: [{ competency: '团队协作', hint: '从你的真实经历里找一个体现「团队协作」的事件，按 情境/挑战/行动/结果/反思 整理', candidate_sources: [] }],
    },
  },
}

async function openWorkspace(context, page) {
  await installMocks(context, {
    messages: COMMON_WS_BOOTSTRAP,
    localStorage: { 'ia-color-scheme': 'vscode-light-plus', ia_app_mode: 'prep' },
    apiOverrides: {
      'GET /api/prep/spaces': { items: [SPACE] },
      'GET /api/prep/spaces/7': SPACE,
      'POST /api/intelligence/workspace': WORKSPACE,
    },
  })
  await page.goto('/')
  await page.getByText('示例科技 · 高级后端').click()
  await page.getByRole('button', { name: /分析岗位/ }).click()
  await expect(page.getByLabel('Gap Map')).toBeVisible()
}

test.describe('prepare job workspace (Stage L1)', () => {
  test('shows gap map, attack surface, stories and the follow-up tree', async ({ context, page }) => {
    await openWorkspace(context, page)

    await expect(page.getByText('RAG 评估')).toBeVisible()
    await expect(page.getByText('指标会被追问口径与来源 · 与岗位要求直接相关')).toBeVisible()
    await expect(page.getByText(/缺少「团队协作」故事/)).toBeVisible()

    const tree = page.getByRole('button', { name: /追问树（1 条主线）/ })
    await tree.focus()
    await page.keyboard.press('Enter')
    await expect(tree).toHaveAttribute('aria-expanded', 'true')
    await expect(page.getByText('如果让你来落地「Kubernetes」，你会怎么做？')).toBeVisible()
    await page.screenshot({ path: test.info().outputPath('job-workspace-desktop.png'), fullPage: true })
  })

  test('fits a phone-width viewport without horizontal overflow', async ({ context, page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await openWorkspace(context, page)
    await page.getByRole('button', { name: /追问树/ }).click()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
    await page.screenshot({ path: test.info().outputPath('job-workspace-mobile.png'), fullPage: true })
  })
})
