import { expect, test } from '@playwright/test'
import { COMMON_WS_BOOTSTRAP, installMocks } from './fixtures/setup.mjs'

const SPACE = {
  id: 'cs-v2',
  profile: 'DESIGN_REVIEW',
  title: 'PDIG · Android Architecture',
  description: '技术设计评审',
  status: 'ACTIVE',
  project_id: 'pdig',
  relationship_key: '',
  default_goal: '决定 conflict merge strategy',
  default_mode: 'BALANCED',
  selected_source_ids: ['benchmark-note'],
  selected_quick_note_ids: [],
  retention_policy: { preset: 'STANDARD' },
  created_at: 1,
  updated_at: 2,
}

const SESSION = {
  id: 'cv-v2',
  space_id: SPACE.id,
  goal_ids: [],
  template: 'DESIGN_REVIEW',
  title: 'Architecture Review',
  scheduled_at: null,
  started_at: 2,
  ended_at: null,
  capture_mode: 'NOTES_ONLY',
  processing_mode: 'LOCAL',
  assistance_mode: 'BALANCED',
  consent_ack: true,
  pack_id: 'cpack-v2',
  status: 'ACTIVE',
  state: { current_topic: '', open_threads: [], last_guidance_id: '' },
  created_at: 1,
  updated_at: 2,
}

const DECISION = {
  id: 'ci-decision',
  space_id: SPACE.id,
  session_id: SESSION.id,
  type: 'Decision',
  state: 'AGREED',
  title: 'offline migration 采用 v2',
  detail: '',
  speaker_id: '',
  owner_id: '',
  due_at: '',
  source_refs: [{ kind: 'TRANSCRIPT_SEGMENT', excerpt: '那我们就按 v2 做' }],
  source_excerpt: '那我们就按 v2 做',
  confidence: 1,
  epistemic_status: 'OBSERVED',
  review_status: 'USER_CONFIRMED',
  supersedes_id: '',
  visibility: 'PRIVATE',
  created_at: 1,
  updated_at: 2,
}

const OPEN = {
  ...DECISION,
  id: 'ci-open',
  type: 'OpenQuestion',
  state: 'PROPOSED',
  title: 'rollback owner 还没有明确',
  review_status: 'AI_EXTRACTED',
}

function mocks() {
  let session = { ...SESSION }
  return async (pathname, method, request) => {
    if (pathname === '/api/product/conversation/demo') return {
      evidence: 'SYNTHETIC_DEMO',
      scenario: 'DESIGN_REVIEW',
      title: 'Android Architecture Review · Dry Run',
      goal: '明确 offline migration 方案并确认 rollback owner',
      steps: [
        { kind: 'PROPOSAL', title: 'Proposal ≠ Decision', input: '建议 v2', output: '保持 PROPOSED', state: 'PROPOSED' },
        { kind: 'RECALL', title: '跨场 Recall', input: '回到 migration', output: '上次已确认 v2', source: 'Synthetic prior Design Review' },
        { kind: 'CONTRIBUTION_OPPORTUNITY', title: '值得补充', input: '讨论规模', output: '10x data scale', source: 'Synthetic Benchmark Note' },
        { kind: 'SILENT', title: 'Stay Silent', input: '用户正在表达', output: 'SILENT · USER_SPEAKING' },
        { kind: 'CONTINUE', title: '会后逐项确认', input: 'owner 未知', output: '保持 Open Question' },
      ],
      privacy: { capture_default: 'NOTES_ONLY', processing_default: 'LOCAL' },
    }
    if (pathname === '/api/product/conversation/templates') return {
      items: [
        { key: 'PROJECT_SYNC', label: '项目同步', default_mode: 'BALANCED', guidance: ['RECALL', 'QUESTION'] },
        { key: 'DESIGN_REVIEW', label: '设计评审', default_mode: 'BALANCED', guidance: ['RECALL', 'CONTRIBUTION_OPPORTUNITY'] },
        { key: 'ONE_ON_ONE', label: '1:1', default_mode: 'ONE_ON_ONE', guidance: ['RECALL', 'QUESTION'] },
      ],
    }
    if (pathname === '/api/product/conversation/home') return {
      state: 'ACTIVE',
      spaces: [SPACE],
      next_session: null,
      next_focus: { kind: 'OPEN_QUESTION', title: OPEN.title, space_id: SPACE.id },
      owed_by_me: [],
      open_questions: [OPEN],
      recent_change: DECISION,
    }
    if (pathname === '/api/product/conversation/spaces' && method === 'GET') return { items: [SPACE] }
    if (pathname === '/api/product/conversation/spaces' && method === 'POST') return SPACE
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}` && method === 'GET') return {
      ...SPACE,
      goals: [{ id: 'cg-1', space_id: SPACE.id, title: SPACE.default_goal, outcome_definition: '', status: 'ACTIVE', priority: 50, source: { kind: 'USER' }, created_at: 1, resolved_at: null }],
      sessions: [{ ...session, status: 'ENDED', ended_at: 3 }],
      participants: [{ id: 'cp-1', space_id: SPACE.id, session_id: null, display_name: 'Alex', role: 'Backend', organization: '', identity_confidence: 1, identity_source: 'USER', visibility: 'PRIVATE', observations: [] }],
      decisions: [DECISION],
      commitments: [],
      open_questions: [OPEN],
      threads: [],
    }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/prepare`) return {
      space: SPACE,
      goals: [],
      next_session: null,
      open_commitments: [],
      open_questions: [OPEN],
      related_decisions: [DECISION],
      participants: [],
      selected_sources: ['benchmark-note'],
      selected_quick_notes: [],
    }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/retention`) return {
      space_id: SPACE.id,
      policy: { preset: 'STANDARD', transcript_days: 30, guidance_days: 30, draft_days: 30 },
      would_delete: { transcript_segments: 0, guidance_events: 0, draft_actions: 0 },
      kept: { confirmed_items: 'KEEP', session_packs: 'KEEP', provenance_tombstones: 'KEEP' },
      destructive: false,
    }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/sessions` && method === 'POST') return { ...SESSION, status: 'UPCOMING', started_at: null, pack_id: '' }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/preflight`) return {
      session: { ...SESSION, status: 'UPCOMING', started_at: null },
      space: SPACE,
      items: [
        { key: 'goal', label: '本次目标', value: SPACE.default_goal, ok: true },
        { key: 'mode', label: '帮助方式', value: 'BALANCED', ok: true },
      ],
      blockers: [],
      privacy_note: '记录规则依场景与组织政策而异。',
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/start` && method === 'POST') {
      session = { ...SESSION, status: 'ACTIVE' }
      return { session, pack: { id: 'cpack-v2', digest: 'abc' } }
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'GET') return session
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'PATCH') {
      session = { ...session, ...request.postDataJSON() }
      return session
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/guidance/evaluate` && method === 'POST') {
      const body = request.postDataJSON()
      if (body.user_speaking) return { guidance: null, suppressed: 'USER_SPEAKING', event: { id: 'ge-silent', expression_action: 'SILENT' } }
      return {
        guidance: {
          id: 'ge-1',
          session_id: SESSION.id,
          candidate_id: 'gc-1',
          kind: 'CONTRIBUTION_OPPORTUNITY',
          expression_action: 'ADD_TALKING_POINT',
          text: body.candidate_text || 'Q4 benchmark 已覆盖 10x data scale',
          source_refs: body.source_refs || [],
          status: 'SHOWN',
          reason: 'HIGH_VALUE_OPPORTUNITY',
          score: { value: 5 },
          user_action: 'NONE',
          rendered_at: 2,
          created_at: 2,
        },
        suppressed: null,
      }
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/ask` && method === 'POST') return {
      answer: '找到可追溯的相关记录：offline migration 采用 v2',
      matches: [DECISION],
      grounded: true,
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/end` && method === 'POST') {
      session = { ...session, status: 'ENDED', ended_at: 3 }
      return { session, decisions: [DECISION], commitments: [], open_questions: [OPEN], candidates: [OPEN], next_focus: { kind: 'OPEN_QUESTION', title: OPEN.title, source_ref: OPEN.id }, review_required: 1 }
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/continue`) return {
      session: { ...session, status: 'ENDED', ended_at: 3 },
      decisions: [DECISION], commitments: [], open_questions: [OPEN], candidates: [OPEN],
      next_focus: { kind: 'OPEN_QUESTION', title: OPEN.title, source_ref: OPEN.id }, review_required: 1,
    }
    if (pathname.startsWith('/api/product/conversation/items/') && pathname.endsWith('/review')) return { ...OPEN, review_status: 'USER_CONFIRMED' }
    if (pathname.startsWith('/api/product/conversation/guidance/')) return { id: 'ge-1', user_action: request.postDataJSON().action }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/export`) return { kind: 'CONVERSATION_SPACE', contract: 'v2.0-R1', space: SPACE }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/participants`) return { id: 'cp-2', display_name: 'Lei', role: 'Product' }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/goals`) return { id: 'cg-2', title: '确认 owner' }
    return undefined
  }
}

test.describe('v2.0 Conversation Profile', () => {
  test('first opt-in runs an explicitly synthetic dry run before Conversation Home', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'interview' },
      apiOverrides: mocks(),
    })
    await page.goto('/#/home')
    await page.getByLabel('工作模式').selectOption('conversation')
    await expect(page).toHaveURL(/#\/conversation\/onboarding/)
    await expect(page.getByTestId('conversation-onboarding')).toBeVisible()
    await expect(page.getByText('默认本地、私密、不开录音、不自动写外部系统。')).toBeVisible()
    await page.getByRole('button', { name: '运行 30–60 秒等价 Dry Run' }).click()
    await expect(page.getByTestId('conversation-dry-run')).toBeVisible()
    await expect(page.getByText('SYNTHETIC_DEMO')).toBeVisible()
    await expect(page.getByText('SILENT · USER_SPEAKING')).toBeVisible()
    await page.getByRole('button', { name: '开启 Conversation Beta' }).click()
    await expect(page).toHaveURL(/#\/conversation$/)
    const optin = await page.evaluate(() => localStorage.getItem('chengzhu-conversation-optin'))
    expect(optin).toBe('1')
  })


  test('profile switcher opens a real Conversation Home and Space', async ({ context, page }, testInfo) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto('/#/conversation')
    await expect(page.getByTestId('conversation-home')).toBeVisible()
    await expect(page.getByRole('heading', { name: '对话' })).toBeVisible()
    await expect(page.getByText('rollback owner 还没有明确').first()).toBeVisible()
    await expect(page.getByText('offline migration 采用 v2')).toBeVisible()
    await testInfo.attach('v2-conversation-home', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

    await page.getByRole('button', { name: /对话空间/ }).first().click()
    await expect(page).toHaveURL(/#\/conversation\/spaces/)
    await page.getByRole('button', { name: /PDIG · Android Architecture/ }).click()
    await expect(page.getByTestId('conversation-space')).toBeVisible()
    await expect(page.getByText('Conversation Goals')).toBeVisible()
    await expect(page.getByText('Alex · Backend')).toBeVisible()
  })

  test('Prepare → Preflight → Live → Guidance → Continue is one real product loop', async ({ context, page }, testInfo) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/spaces/${SPACE.id}/prepare`)
    await expect(page.getByRole('heading', { name: SPACE.title })).toBeVisible()
    await page.getByRole('button', { name: '生成本场并检查' }).click()
    await expect(page.getByText('记录规则依场景与组织政策而异。')).toBeVisible()
    await page.getByRole('button', { name: '开始会话' }).click()
    await expect(page).toHaveURL(new RegExp(`#/conversation/live/${SESSION.id}`))
    await expect(page.getByTestId('conversation-live')).toBeVisible()

    await page.getByLabel('当前话题').fill('offline migration')
    await page.getByLabel('值得补充的候选内容（如有）').fill('Q4 benchmark 已覆盖 10x data scale')
    await page.getByLabel('来源 / 依据').fill('Benchmark Note · confirmed')
    await page.getByRole('button', { name: '评估当前 Guidance' }).click()
    await expect(page.getByText('CONTRIBUTION_OPPORTUNITY')).toBeVisible()
    await expect(page.getByRole('paragraph').filter({ hasText: 'Q4 benchmark 已覆盖 10x data scale' })).toBeVisible()

    await testInfo.attach('v2-live-guidance', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

    await page.getByRole('button', { name: '结束并 Continue' }).click()
    await expect(page.getByText('这场之后')).toBeVisible()
    await expect(page.getByText('Next Focus · rollback owner 还没有明确')).toBeVisible()
  })

  test('Manual Ask is source-aware and user speaking produces SILENT', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-dark-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await page.getByPlaceholder('例如：我们之前为什么决定用 v2？').fill('offline sync v2')
    await page.getByRole('button', { name: '查已确认记录' }).click()
    await expect(page.getByText('找到可追溯的相关记录：offline migration 采用 v2')).toBeVisible()

    await page.getByText('我正在连续表达').click()
    await page.getByLabel('值得补充的候选内容（如有）').fill('应该补充 benchmark')
    await page.getByLabel('来源 / 依据').fill('benchmark source')
    await page.getByRole('button', { name: '评估当前 Guidance' }).click()
    await expect(page.getByText('这一次选择不打扰你')).toBeVisible()
    await expect(page.getByText('SILENT · USER_SPEAKING')).toBeVisible()
  })

  test('Transcript mode uses Conversation-owned capture controls instead of Interview answering', async ({ context, page }) => {
    const base = mocks()
    let capture = {
      active: false,
      session_id: '',
      owns_requested_session: false,
      device_id: null,
      candidate_mic_device_id: null,
      mode: 'IDLE',
    }
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: async (pathname, method, request) => {
        if (pathname === '/api/devices') return {
          devices: [
            { id: 1001, name: '会议软件系统音频', is_loopback: true },
            { id: 1002, name: '我的麦克风', is_loopback: false },
          ],
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'GET') {
          return { ...SESSION, capture_mode: 'TRANSCRIPT' }
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/capture` && method === 'GET') return capture
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/capture/start` && method === 'POST') {
          const body = request.postDataJSON()
          capture = {
            active: true,
            session_id: SESSION.id,
            owns_requested_session: true,
            device_id: body.device_id,
            candidate_mic_device_id: body.candidate_mic_device_id ?? null,
            mode: 'TRANSCRIPTION_ONLY',
            paused: false,
          }
          return capture
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/capture/pause`) {
          capture = { ...capture, paused: true }
          return capture
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/capture/resume`) {
          capture = { ...capture, paused: false }
          return capture
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/capture/stop`) {
          capture = { ...capture, active: false, owns_requested_session: false, mode: 'IDLE', paused: false }
          return capture
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/transcript`) return {
          items: capture.active ? [{
            id: 'cts-1', space_id: SPACE.id, session_id: SESSION.id,
            channel: 'PRIMARY_AUDIO', text: '我们回到 offline migration',
            provider: 'whisper', source: 'SYSTEM_LOOPBACK', is_final: true, created_at: 2,
          }] : [],
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/guidance`) return { items: [] }
        return base(pathname, method, request)
      },
    })

    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await expect(page.getByText('真实转写', { exact: true })).toBeVisible()
    await expect(page.getByLabel('主音频（优先系统/会议音频）')).toHaveValue('1001')
    await page.getByLabel('我的麦克风（可选）').selectOption('1002')
    await page.getByRole('button', { name: '开始转写' }).click()
    await expect(page.getByText('CAPTURING')).toBeVisible()
    await expect(page.getByText('只复用 Audio/VAD/STT；不会启动 Interview 自动答题、Fast Cue 或 Interview Review。')).toBeVisible()
    await expect.poll(async () => page.getByText('我们回到 offline migration').count()).toBeGreaterThan(0)
    await page.getByRole('button', { name: '暂停' }).click()
    await expect(page.getByText('PAUSED')).toBeVisible()
    await page.getByRole('button', { name: '继续' }).click()
    await page.getByRole('button', { name: '停止转写' }).click()
    await expect(page.getByText('OFF', { exact: true })).toBeVisible()
  })

  test('Conversation surfaces remain usable at 390px', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/#/conversation')
    await expect(page.getByTestId('conversation-home')).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    expect(overflow).toBeLessThanOrEqual(0)
  })
})
