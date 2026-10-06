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
  policy: {
    transcript_retention: 'SPACE_POLICY',
    screen_context: 'OFF',
    ai_assistance: 'AI_ALLOWED',
    human_assistance: 'HUMAN_PRACTICE_ONLY',
    share_privacy: 'OFF',
    external_writeback: 'REVIEW_REQUIRED',
    participant_consent_status: 'USER_REPORTS_ALLOWED',
    participant_transparency_plan: 'USER_WILL_NOTIFY_VERBALLY',
    connector_permissions: [],
    speaker_biometric_identity: 'OFF',
    emotion_sentiment_profiling: 'OFF',
    hidden_intent_claims: 'OFF',
  },
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
        { key: 'PROJECT_SYNC', label: '项目同步', default_mode: 'BALANCED', guidance: ['RECALL', 'QUESTION', 'TALKING_POINT'], runtime_available: true, launch_wedge: true, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'BETA_WEDGE' },
        { key: 'DESIGN_REVIEW', label: '设计评审', default_mode: 'BALANCED', guidance: ['RECALL', 'CONTRIBUTION_OPPORTUNITY', 'TALKING_POINT'], runtime_available: true, launch_wedge: true, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'BETA_WEDGE' },
        { key: 'ONE_ON_ONE', label: '1:1', default_mode: 'ONE_ON_ONE', guidance: ['RECALL', 'QUESTION', 'TALKING_POINT'], runtime_available: true, launch_wedge: false, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'SHARED_RUNTIME_TEMPLATE' },
      ],
    }
    if (pathname === '/api/product/conversation/history') return {
      items: [{
        ...SESSION, title: 'Review #1', status: 'ENDED', ended_at: 3,
        space_title: SPACE.title, space_profile: SPACE.profile,
        decisions_count: 1, commitments_count: 0, open_questions_count: 1, review_required: 1,
      }],
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
      participants: [{
        id: 'cp-1', space_id: SPACE.id, session_id: null, display_name: 'Alex', role: 'Backend',
        organization: '', identity_confidence: 1, identity_source: 'USER', visibility: 'PRIVATE', observations: [],
        counterparty_state: {
          known_explicit: {
            priority: '迁移稳定性',
            concern: '回滚风险',
            stated_position: '先灰度再全量',
            decision_authority: '架构方案批准人',
            relationship_context: '客户技术负责人',
          },
          source_refs: [{ kind: 'USER_NOTE', excerpt: 'Alex 明确关注回滚风险' }],
          confidence: 1,
          temporary_inferences: [],
          unknown: [],
        },
      }],
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
      brief: { last_change: DECISION, unresolved_count: 1, known_participants: 1 },
      agenda: [OPEN.title],
      expected_questions: [OPEN.title],
      contribution_candidates: [{ text: DECISION.title, source_refs: DECISION.source_refs, kind: 'RECALL' }],
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
      warnings: [],
      policy: SESSION.policy,
      processing_runtime: {
        mode: 'LOCAL',
        capture_mode: 'NOTES_ONLY',
        configured_stt_provider: 'whisper',
        main_audio_remote_possible: false,
        self_mic_remote_possible: false,
        data_path: {
          capture: 'STRUCTURED_NOTES_ONLY',
          stt: 'NOT_USED',
          inference: 'LOCAL_DETERMINISTIC',
          retention: 'LOCAL_PRODUCT_DB',
          writeback: 'LOCAL_REVIEWED_DRAFT_ONLY',
          audio_retention: 'OFF',
          transcript_retention: 'SPACE_POLICY',
        },
        blockers: [],
      },
      pack_preview: {
        goal_ids: [],
        selected_source_ids: ['benchmark-note'],
        selected_quick_note_ids: [],
        sources: [{
          material_id: 'benchmark-note',
          version_id: 'mv-benchmark-v1',
          title: 'Q4 Benchmark',
          kind: 'PROJECT',
          usage: 'FACTS',
          content_hash: 'sha256:fixture',
          is_personal_evidence: true,
        }],
        skipped_sources: [],
        quick_notes: [],
        missing_quick_note_ids: [],
        participants_count: 1,
        confirmed_items_count: 1,
        expression_profile: { conclusion_first: true, target_seconds: 60, shape: 'bullet' },
        processing_runtime: {
          mode: 'LOCAL',
          capture_mode: 'NOTES_ONLY',
          configured_stt_provider: 'whisper',
          main_audio_remote_possible: false,
          self_mic_remote_possible: false,
          blockers: [],
        },
        policy: { ...SESSION.policy, capture_mode: 'NOTES_ONLY', processing_mode: 'LOCAL', assistance_mode: 'BALANCED' },
      },
      privacy_note: '记录规则依场景与组织政策而异。',
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/start` && method === 'POST') {
      session = { ...SESSION, status: 'ACTIVE' }
      return { session, pack: { id: 'cpack-v2', digest: 'abc' } }
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'GET') return session
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/context` && method === 'GET') return {
      session_id: SESSION.id,
      space: { id: SPACE.id, profile: SPACE.profile, title: SPACE.title },
      brief: {
        goal: SPACE.default_goal,
        agenda: [OPEN.title],
        expected_questions: [OPEN.title],
        unresolved_count: 1,
        known_participants: 1,
        contribution_candidates: [{ text: DECISION.title, source_refs: DECISION.source_refs, kind: 'RECALL' }],
      },
      sources: [{
        material_id: 'benchmark-note',
        version_id: 'mv-benchmark-v1',
        title: 'Q4 Benchmark',
        kind: 'PROJECT',
        usage: 'FACTS',
        content_hash: 'sha256:fixture',
        is_personal_evidence: true,
      }],
      quick_notes: [],
      participants: [{
        id: 'cp-1',
        display_name: 'Alex',
        role: 'Backend',
        organization: '',
        counterparty_state: {
          known_explicit: {
            priority: '迁移稳定性',
            concern: '回滚风险',
            stated_position: '先灰度再全量',
            decision_authority: '架构方案批准人',
            relationship_context: '客户技术负责人',
          },
          source_refs: [{ kind: 'USER_NOTE', excerpt: 'Alex 明确关注回滚风险' }],
          confidence: 1,
          temporary_inferences: [],
          unknown: [],
        },
      }],
      expression_profile: { conclusion_first: true, target_seconds: 60, shape: 'bullet' },
      processing_runtime: {
        mode: 'LOCAL',
        capture_mode: 'NOTES_ONLY',
        configured_stt_provider: 'whisper',
        main_audio_remote_possible: false,
        self_mic_remote_possible: false,
        data_path: {
          capture: 'STRUCTURED_NOTES_ONLY',
          stt: 'NOT_USED',
          inference: 'LOCAL_DETERMINISTIC',
          retention: 'LOCAL_PRODUCT_DB',
          writeback: 'LOCAL_REVIEWED_DRAFT_ONLY',
          audio_retention: 'OFF',
          transcript_retention: 'SPACE_POLICY',
        },
        blockers: [],
      },
      policy: SESSION.policy,
      pack_digest: 'abcdef1234567890',
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'PATCH') {
      session = { ...session, ...request.postDataJSON() }
      return session
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/guidance/evaluate` && method === 'POST') {
      const body = request.postDataJSON()
      const kind = body.direct_question ? 'ANSWER_CUE'
        : body.critical_risk ? 'RISK'
          : body.talking_point ? 'TALKING_POINT'
            : body.delivery_focus ? 'DELIVERY'
              : 'CONTRIBUTION_OPPORTUNITY'
      const action = kind === 'ANSWER_CUE' ? 'ANSWER'
        : kind === 'RISK' ? 'FLAG_RISK'
          : kind === 'DELIVERY' ? 'CLARIFY'
            : 'ADD_TALKING_POINT'
      if (!body.direct_question && !body.critical_risk && !body.talking_point && !body.delivery_focus && body.user_speaking) {
        return { guidance: null, suppressed: 'USER_SPEAKING', event: { id: 'ge-silent', expression_action: 'SILENT' } }
      }
      return {
        guidance: {
          id: 'ge-1',
          session_id: SESSION.id,
          candidate_id: 'gc-1',
          kind,
          expression_action: action,
          text: body.answer_cue || body.critical_risk || body.talking_point || body.delivery_focus || body.candidate_text || 'Q4 benchmark 已覆盖 10x data scale',
          source_refs: body.source_refs || [],
          status: 'SHOWN',
          reason: kind === 'DELIVERY' ? 'EXPRESSION_PLANNER' : kind === 'TALKING_POINT' ? 'MANUAL_TALKING_POINT' : kind === 'RISK' ? 'CRITICAL_RISK' : kind === 'ANSWER_CUE' ? 'DIRECT_QUESTION' : 'HIGH_VALUE_OPPORTUNITY',
          score: { value: 5 },
          user_action: 'NONE',
          rendered_at: 2,
          created_at: 2,
        },
        suppressed: null,
      }
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/ask` && method === 'POST') return {
      answer: '已确认历史：offline migration 采用 v2 — Benchmark Note',
      matches: [{
        id: DECISION.id,
        kind: 'CONFIRMED_ITEM',
        authority: 'CONFIRMED_TRUTH',
        title: DECISION.title,
        excerpt: 'Benchmark Note',
        item_type: 'Decision',
        state: 'AGREED',
        review_status: 'USER_CONFIRMED',
        source_refs: DECISION.source_refs,
      }],
      grounded: true,
      truth_confirmed: true,
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/end` && method === 'POST') {
      session = { ...session, status: 'ENDED', ended_at: 3 }
      return { session, decisions: [DECISION], commitments: [], open_questions: [OPEN], candidates: [OPEN], what_changed: [DECISION], pins: [], next_focus: { kind: 'OPEN_QUESTION', title: OPEN.title, source_ref: OPEN.id }, review_required: 1 }
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/continue`) return {
      session: { ...session, status: 'ENDED', ended_at: 3 },
      decisions: [DECISION], commitments: [], open_questions: [OPEN], candidates: [OPEN],
      what_changed: [DECISION], pins: [],
      next_focus: { kind: 'OPEN_QUESTION', title: OPEN.title, source_ref: OPEN.id }, review_required: 1,
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/derived-draft` && method === 'POST') {
      const kind = request.postDataJSON().kind
      const title = kind === 'UPDATE_DECISION_LOG_DRAFT' ? 'Architecture Review · Decision Log Draft'
        : kind === 'CREATE_ISSUE_DRAFT' ? 'Architecture Review · Issue Draft'
          : 'Architecture Review · Task Draft'
      return {
        id: 'cda-derived',
        space_id: SPACE.id,
        session_id: SESSION.id,
        kind,
        title,
        content: kind === 'UPDATE_DECISION_LOG_DRAFT' ? '- offline migration 采用 v2 · state=AGREED' : '- draft item',
        target: '',
        payload: { derived_item_ids: [DECISION.id], execution: 'LOCAL_REVIEW_ONLY', external_execution: false },
        source_refs: DECISION.source_refs,
        status: 'DRAFT',
        created_at: 3,
        updated_at: 3,
      }
    }
    if (pathname === '/api/product/conversation/draft-actions/cda-derived/review' && method === 'POST') {
      return {
        id: 'cda-derived',
        space_id: SPACE.id,
        session_id: SESSION.id,
        kind: 'UPDATE_DECISION_LOG_DRAFT',
        title: 'Architecture Review · Decision Log Draft',
        content: '- offline migration 采用 v2 · state=AGREED',
        target: '',
        payload: { derived_item_ids: [DECISION.id], execution: 'LOCAL_REVIEW_ONLY', external_execution: false },
        source_refs: DECISION.source_refs,
        status: request.postDataJSON().action === 'APPROVE' ? 'APPROVED' : 'DISMISSED',
        created_at: 3,
        updated_at: 4,
      }
    }
    if (pathname.startsWith('/api/product/conversation/items/') && pathname.endsWith('/review')) return { ...OPEN, review_status: 'USER_CONFIRMED' }
    if (pathname.startsWith('/api/product/conversation/guidance/')) return { id: 'ge-1', user_action: request.postDataJSON().action }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/export`) return { kind: 'CONVERSATION_SPACE', contract: 'v2.0-R1', space: SPACE }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/participants`) return {
      id: 'cp-2', display_name: 'Lei', role: 'Product', counterparty_state: {
        known_explicit: request.postDataJSON(), source_refs: [], temporary_inferences: [], unknown: [],
      },
    }
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


  test('global Start follows Conversation Profile into the create/preflight flow', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: {
        'ia-color-scheme': 'vscode-light-plus',
        'chengzhu-product-profile': 'conversation',
        'chengzhu-conversation-optin': '1',
      },
      apiOverrides: mocks(),
    })
    await page.goto('/#/conversation')
    await page.getByTestId('start-conversation').click()
    await expect(page).toHaveURL(/#\/conversation\/spaces\?new=1/)
    await expect(page.getByLabel('空间名称')).toBeVisible()
    await expect(page.getByText('希望持续达成什么（可选）')).toBeVisible()
    await expect(page.getByText(/成熟度 · BETA_WEDGE/)).toBeVisible()
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
    await expect(page.getByText('Session Pack Preview')).toBeVisible()
    await expect(page.getByText('Q4 Benchmark')).toBeVisible()
    await expect(page.getByText(/Ready Sources 1\/1/)).toBeVisible()
    await expect(page.getByText('AI AI_ALLOWED')).toBeVisible()
    await expect(page.getByText('记录规则依场景与组织政策而异。')).toBeVisible()
    await page.getByRole('button', { name: '开始会话' }).click()
    await expect(page).toHaveURL(new RegExp(`#/conversation/live/${SESSION.id}`))
    await expect(page.getByTestId('conversation-live')).toBeVisible()
    await expect(page.getByTestId('conversation-session-pulse')).toBeVisible()
    await expect(page.getByText('Session Pulse')).toBeVisible()
    await expect(page.getByText(SPACE.default_goal)).toBeVisible()
    await expect(page.getByText('PACK abcdef12')).toBeVisible()
    await expect(page.getByText('Inference · LOCAL_DETERMINISTIC')).toBeVisible()
    await expect(page.getByText('Retention · LOCAL_PRODUCT_DB')).toBeVisible()
    await expect(page.getByText('Write-back · LOCAL_REVIEWED_DRAFT_ONLY')).toBeVisible()
    await expect(page.getByLabel('当前受众')).toHaveValue('cp-1')
    await expect(page.getByPlaceholder('对方明确角色，例如 CTO / 客户')).toHaveValue('Backend')
    await expect(page.getByPlaceholder('对方明确优先级')).toHaveValue('迁移稳定性')
    await expect(page.getByPlaceholder('对方明确 concern')).toHaveValue('回滚风险')
    await expect(page.getByPlaceholder('明确决策权限（可选）')).toHaveValue('架构方案批准人')
    await expect(page.getByPlaceholder('关系上下文，例如客户技术负责人')).toHaveValue('客户技术负责人')

    await page.getByLabel('当前话题').fill('offline migration')
    await page.getByLabel('高价值 Opportunity 候选（如有）').fill('Q4 benchmark 已覆盖 10x data scale')
    await page.getByLabel('来源 / 依据').fill('Benchmark Note · confirmed')
    await page.getByRole('button', { name: '评估当前 Guidance' }).click()
    await expect(page.getByText('CONTRIBUTION_OPPORTUNITY')).toBeVisible()
    await expect(page.getByRole('paragraph').filter({ hasText: 'Q4 benchmark 已覆盖 10x data scale' })).toBeVisible()

    await testInfo.attach('v2-live-guidance', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

    await page.getByRole('button', { name: '结束并 Continue' }).click()
    await expect(page.getByText('这场之后')).toBeVisible()
    await expect(page.getByText('Next Focus · rollback owner 还没有明确')).toBeVisible()
  })

  test('Live exposes explicit Talking Point and Delivery planner lanes', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await expect(page.getByLabel('明确 Talking Point（如有）')).toBeVisible()
    await expect(page.getByLabel('Delivery / 表达重点（如有）')).toBeVisible()
    await page.getByLabel('明确 Talking Point（如有）').fill('先明确 rollback owner 再谈 release window')
    await page.getByLabel('来源 / 依据').fill('Architecture decision note')
    await page.getByRole('button', { name: '评估当前 Guidance' }).click()
    await expect(page.getByText('TALKING_POINT')).toBeVisible()
    await expect(page.getByRole('paragraph').filter({ hasText: '先明确 rollback owner 再谈 release window' })).toBeVisible()
  })


  test('Manual Ask is source-aware and user speaking produces SILENT', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-dark-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await page.getByPlaceholder('例如：之前为什么用 v2？Q4 benchmark 说了什么？刚才是否提到 rollback？').fill('offline sync v2')
    await page.getByRole('button', { name: '查本场可用来源' }).click()
    await expect(page.getByText('已确认历史：offline migration 采用 v2 — Benchmark Note')).toBeVisible()
    await expect(page.getByText('CONFIRMED_TRUTH')).toBeVisible()

    await page.getByText('我正在连续表达').click()
    await page.getByLabel('高价值 Opportunity 候选（如有）').fill('应该补充 benchmark')
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

  test('Decision supersession is explicit, directional, and preserves the old Decision', async ({ context, page }) => {
    const base = mocks()
    let oldState = 'AGREED'
    let nextState = 'PROPOSED'
    let nextReview = 'AI_EXTRACTED'
    let nextSupersedes = ''
    const replacement = {
      ...DECISION,
      id: 'ci-decision-v3',
      state: nextState,
      title: 'offline migration 采用 v3',
      review_status: nextReview,
      supersedes_id: nextSupersedes,
      created_at: 3,
      updated_at: 3,
    }
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: async (pathname, method, request) => {
        if (pathname === `/api/product/conversation/spaces/${SPACE.id}` && method === 'GET') {
          const original = await base(pathname, method, request)
          return {
            ...original,
            decisions: [
              { ...DECISION, state: oldState },
              { ...replacement, state: nextState, review_status: nextReview, supersedes_id: nextSupersedes },
            ],
          }
        }
        if (pathname === '/api/product/conversation/items/ci-decision-v3/review' && method === 'POST') {
          const body = request.postDataJSON()
          if (body.action === 'SUPERSEDE') {
            oldState = 'SUPERSEDED'
            nextState = 'AGREED'
            nextReview = 'USER_CONFIRMED'
            nextSupersedes = DECISION.id
          }
          return { ...replacement, state: nextState, review_status: nextReview, supersedes_id: nextSupersedes }
        }
        return base(pathname, method, request)
      },
    })
    await page.goto(`/#/conversation/spaces/${SPACE.id}/decisions`)
    await expect(page.getByText('offline migration 采用 v3')).toBeVisible()
    await page.getByLabel('要替代的旧 Decision').selectOption(DECISION.id)
    await page.getByRole('button', { name: '确认并替代旧 Decision' }).click()
    await expect(page.getByText(`supersedes ${DECISION.id}`)).toBeVisible()
    await expect(page.getByText('SUPERSEDED')).toBeVisible()
    await expect(page.getByText('AGREED')).toBeVisible()
  })


  test('Continue exposes reviewed local write-back drafts without claiming connector execution', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/spaces/${SPACE.id}/sessions`)
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page.getByText('这场之后')).toBeVisible()
    await page.getByRole('button', { name: 'Decision Log Draft' }).click()
    await expect(page.getByText('Architecture Review · Decision Log Draft')).toBeVisible()
    await expect(page.getByText('- offline migration 采用 v2 · state=AGREED')).toBeVisible()
    await expect(page.getByText(/不代表已发送邮件、创建 task \/ issue 或写入 decision log/)).toBeVisible()
    await page.getByRole('button', { name: '确认草稿' }).click()
    await expect(page.getByText('APPROVED')).toBeVisible()
  })


  test('Conversation History stays inside Conversation Profile and returns to the same Space', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto('/#/conversation')
    await page.getByRole('button', { name: /历史/ }).first().click()
    await expect(page).toHaveURL(/#\/history/)
    await expect(page.getByTestId('conversation-history')).toBeVisible()
    await expect(page.getByText('Review #1')).toBeVisible()
    await expect(page.getByText('1 Decisions')).toBeVisible()
    await page.getByRole('button', { name: /Review #1/ }).click()
    await expect(page).toHaveURL(new RegExp(`#/conversation/spaces/${SPACE.id}/sessions`))
    await expect(page.getByTestId('conversation-space')).toBeVisible()
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
