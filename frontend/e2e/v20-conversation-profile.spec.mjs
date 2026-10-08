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

const DESIGN_REVIEW_PLAYBOOK = {
  profile: 'DESIGN_REVIEW',
  success_conditions: [
    '把设计选择与证据/约束放在同一上下文',
    '显式保留 objection / risk / unresolved trade-off',
    '若形成决策，保留 supersession 与后续验证项',
  ],
  priority_truth_types: ['Decision', 'Proposal', 'Objection', 'Risk', 'Assumption', 'OpenQuestion', 'Metric'],
  prepare_prompts: ['本次要决定什么？', '关键 trade-off / objection 是什么？', '哪条证据最能改变决策？'],
  closing_objective: '得到有 provenance 的 Decision，或明确留下仍未解决的 trade-off / objection。',
  boundaries: ['不把 Proposal 当 Decision', '不把模型推断的 trade-off 当成参与者明确立场'],
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

const SCREEN_RUNTIME_OFF = {
  mode: 'OFF',
  available: true,
  route: 'UNAVAILABLE',
  model_name: '',
  model_id: '',
  fingerprint: '',
  raw_image_persisted: false,
  blockers: [],
}

function expressionPlan(event, target = '') {
  const silent = event.status !== 'SHOWN' || event.expression_action === 'SILENT'
  return {
    action: event.expression_action,
    guidance_kind: event.kind || null,
    target_participant_id: target,
    text: event.text || '',
    source_refs: event.source_refs || [],
    warnings: silent && event.reason ? [`Suppressed: ${event.reason}`] : [],
    max_length: silent ? 0 : 1200,
    render_as: silent ? 'SILENCE' : 'PRIMARY_CARD',
    suppression_reasons: silent && event.reason ? [event.reason] : [],
  }
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

const REVIEWED_OPEN = {
  ...OPEN,
  id: 'ci-open-reviewed',
  review_status: 'USER_CONFIRMED',
}

const THREAD = {
  id: 'cot-reviewed-open',
  space_id: SPACE.id,
  session_id: SESSION.id,
  kind: 'OpenQuestion',
  text: REVIEWED_OPEN.title,
  owner_id: '',
  status: 'OPEN',
  source_refs: [
    { kind: 'CONVERSATION_ITEM', id: REVIEWED_OPEN.id, session_id: SESSION.id, visibility: 'PRIVATE' },
    ...REVIEWED_OPEN.source_refs,
  ],
  created_at: 1,
  resolved_at: null,
}

const COMMITMENT_CANDIDATE = {
  ...DECISION,
  id: 'ci-commitment',
  type: 'Commitment',
  state: 'PROPOSED',
  title: '补 rollout plan',
  owner_id: '',
  source_refs: [{ kind: 'TRANSCRIPT_SEGMENT', id: 'cts-primary', excerpt: '我来补 rollout plan' }],
  source_excerpt: '我来补 rollout plan',
  epistemic_status: 'INFERRED',
  review_status: 'AI_EXTRACTED',
}

function mocks() {
  let session = { ...SESSION }
  let threadOpen = true
  let goal = {
    id: 'cg-1',
    space_id: SPACE.id,
    title: SPACE.default_goal,
    outcome_definition: '',
    status: 'ACTIVE',
    priority: 50,
    source: { kind: 'USER' },
    created_at: 1,
    resolved_at: null,
  }
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
        { key: 'PROJECT_SYNC', label: '项目同步', default_mode: 'BALANCED', guidance: ['RECALL', 'QUESTION', 'RISK', 'CONTRIBUTION_OPPORTUNITY'], runtime_available: true, launch_wedge: true, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'BETA_WEDGE' },
        { key: 'DESIGN_REVIEW', label: '设计评审', default_mode: 'BALANCED', guidance: ['RECALL', 'TALKING_POINT', 'QUESTION', 'RISK', 'CONTRIBUTION_OPPORTUNITY'], runtime_available: true, launch_wedge: true, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'BETA_WEDGE' },
        { key: 'PRESENTATION_QA', label: '演示 / Q&A', default_mode: 'PRESENTATION', guidance: ['ANSWER_CUE', 'RECALL', 'QUESTION', 'DELIVERY'], runtime_available: true, launch_wedge: false, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'SHARED_RUNTIME_TEMPLATE' },
        { key: 'ONE_ON_ONE', label: '1:1', default_mode: 'ONE_ON_ONE', guidance: ['RECALL', 'QUESTION', 'TALKING_POINT'], runtime_available: true, launch_wedge: false, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'SHARED_RUNTIME_TEMPLATE' },
        { key: 'CLIENT_CALL', label: '客户会', default_mode: 'BALANCED', guidance: ['RECALL', 'ANSWER_CUE', 'QUESTION', 'RISK', 'CONTRIBUTION_OPPORTUNITY'], runtime_available: true, launch_wedge: false, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'SHARED_RUNTIME_TEMPLATE' },
        { key: 'NEGOTIATION', label: '谈判', default_mode: 'QUIET', guidance: ['RECALL', 'TALKING_POINT', 'QUESTION', 'RISK'], runtime_available: true, launch_wedge: false, specialized_behavior_validated: false, stable_release: false, real_user_validated: false, maturity: 'SHARED_RUNTIME_TEMPLATE' },
      ],
    }
    if (pathname === '/api/product/conversation/history') return {
      items: [{
        ...SESSION, title: 'Review #1', status: 'ENDED', ended_at: 3,
        space_title: SPACE.title, space_profile: SPACE.profile,
        decisions_count: 1, commitments_count: 0, open_questions_count: 1, review_required: 1,
      }],
    }
    if (pathname === '/api/product/conversation/search') return {
      items: [{
        ...DECISION,
        space_title: SPACE.title,
        space_profile: SPACE.profile,
        session_title: SESSION.title,
        session_started_at: 2,
        session_ended_at: null,
      }],
    }
    if (pathname === '/api/product/conversation/home') return {
      state: 'ACTIVE',
      spaces: [SPACE],
      next_session: null,
      next_focus: { kind: 'OPEN_QUESTION', title: REVIEWED_OPEN.title, space_id: SPACE.id },
      owed_by_me: [],
      open_questions: [REVIEWED_OPEN],
      recent_change: DECISION,
    }
    if (pathname === '/api/product/conversation/spaces' && method === 'GET') return { items: [SPACE] }
    if (pathname === '/api/product/conversation/spaces' && method === 'POST') return SPACE
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}` && method === 'GET') return {
      ...SPACE,
      default_goal: goal.status === 'ACTIVE' ? goal.title : '',
      goals: [goal],
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
      open_questions: [REVIEWED_OPEN, OPEN],
      threads: threadOpen ? [THREAD] : [],
    }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/prepare`) return {
      space: { ...SPACE, default_goal: goal.status === 'ACTIVE' ? goal.title : '' },
      goals: [goal],
      next_session: null,
      open_commitments: [],
      open_questions: [REVIEWED_OPEN],
      open_threads: threadOpen ? [THREAD] : [],
      related_decisions: [DECISION],
      participants: [],
      selected_sources: ['benchmark-note'],
      selected_quick_notes: [],
      brief: { last_change: DECISION, unresolved_count: 1, known_participants: 1 },
      agenda: threadOpen ? [THREAD.text] : [],
      expected_questions: [REVIEWED_OPEN.title],
      contribution_candidates: [{ text: DECISION.title, source_refs: DECISION.source_refs, kind: 'RECALL' }],
      profile_playbook: DESIGN_REVIEW_PLAYBOOK,
    }
    if (pathname === `/api/product/conversation/threads/${THREAD.id}/resolve` && method === 'POST') {
      threadOpen = false
      return { ...THREAD, status: 'RESOLVED', resolved_at: 4 }
    }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/retention`) return {
      space_id: SPACE.id,
      policy: { preset: 'STANDARD', transcript_days: 30, guidance_days: 30, draft_days: 30 },
      would_delete: { transcript_segments: 0, guidance_events: 0, draft_actions: 0, screen_context_observations: 0 },
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
      resolved_ai_behavior: {
        policy: 'AI_ALLOWED',
        manual_ask: true,
        manual_guidance: true,
        automatic_transcript_guidance: true,
        automatic_candidate_extraction: true,
        expected_by_user_report: false,
        engine: 'LOCAL_DETERMINISTIC',
      },
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
      screen_runtime: SCREEN_RUNTIME_OFF,
      share_privacy_runtime: {
        requested: 'OFF',
        available: true,
        requires_desktop: false,
        proof_required: false,
        verified: true,
        runtime: 'OFF',
        proof_kind: '',
        note: '本场未请求 Share Privacy。',
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
        resolved_ai_behavior: {
          policy: 'AI_ALLOWED',
          manual_ask: true,
          manual_guidance: true,
          automatic_transcript_guidance: true,
          automatic_candidate_extraction: true,
          expected_by_user_report: false,
          engine: 'LOCAL_DETERMINISTIC',
        },
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
        screen_runtime: SCREEN_RUNTIME_OFF,
        share_privacy_runtime: {
        requested: 'OFF',
        available: true,
        requires_desktop: false,
        proof_required: false,
        verified: true,
        runtime: 'OFF',
        proof_kind: '',
        note: '本场未请求 Share Privacy。',
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
      conversation_state: {
        phase: 'PARTICIPATE',
        current_topic: '',
        user_speaking: false,
        direct_question_pending: false,
        audience_context: {},
        items: [
          { id: DECISION.id, type: DECISION.type, state: DECISION.state, title: DECISION.title, review_status: DECISION.review_status },
        ],
        open_threads: threadOpen ? [{ id: THREAD.id, kind: THREAD.kind, text: THREAD.text, owner_id: '' }] : [],
        last_guidance_id: '',
      },
      space: { id: SPACE.id, profile: SPACE.profile, title: SPACE.title },
      brief: {
        goal: SPACE.default_goal,
        agenda: [THREAD.text],
        expected_questions: [REVIEWED_OPEN.title],
        open_threads: [{
          id: THREAD.id,
          kind: THREAD.kind,
          text: THREAD.text,
          owner_id: THREAD.owner_id,
          source_refs: THREAD.source_refs,
        }],
        unresolved_count: 1,
        known_participants: 1,
        contribution_candidates: [{ text: DECISION.title, source_refs: DECISION.source_refs, kind: 'RECALL' }],
      },
      profile_playbook: DESIGN_REVIEW_PLAYBOOK,
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
      resolved_ai_behavior: {
        policy: 'AI_ALLOWED',
        manual_ask: true,
        manual_guidance: true,
        automatic_transcript_guidance: true,
        automatic_candidate_extraction: true,
        expected_by_user_report: false,
        engine: 'LOCAL_DETERMINISTIC',
      },
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
      screen_runtime: SCREEN_RUNTIME_OFF,
      share_privacy_runtime: {
        requested: 'OFF',
        available: true,
        requires_desktop: false,
        proof_required: false,
        verified: true,
        runtime: 'OFF',
        proof_kind: '',
        note: '本场未请求 Share Privacy。',
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
        const event = {
          id: 'ge-silent',
          session_id: SESSION.id,
          candidate_id: 'gc-silent',
          kind: 'CONTRIBUTION_OPPORTUNITY',
          expression_action: 'SILENT',
          text: '',
          source_refs: body.source_refs || [],
          status: 'SUPPRESSED',
          reason: 'USER_SPEAKING',
          score: {},
          user_action: 'NONE',
          rendered_at: null,
          created_at: 2,
        }
        event.expression_plan = expressionPlan(event, body.audience_participant_id || '')
        return { guidance: null, suppressed: 'USER_SPEAKING', event }
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
          expression_plan: expressionPlan({
            kind,
            expression_action: action,
            text: body.answer_cue || body.critical_risk || body.talking_point || body.delivery_focus || body.candidate_text || 'Q4 benchmark 已覆盖 10x data scale',
            source_refs: body.source_refs || [],
            status: 'SHOWN',
            reason: kind === 'DELIVERY' ? 'EXPRESSION_PLANNER' : kind === 'TALKING_POINT' ? 'MANUAL_TALKING_POINT' : kind === 'RISK' ? 'CRITICAL_RISK' : kind === 'ANSWER_CUE' ? 'DIRECT_QUESTION' : 'HIGH_VALUE_OPPORTUNITY',
          }, body.audience_participant_id || ''),
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
      return { session, profile_outcome: {
        profile: 'DESIGN_REVIEW',
        closing_objective: DESIGN_REVIEW_PLAYBOOK.closing_objective,
        priority_truth_types: DESIGN_REVIEW_PLAYBOOK.priority_truth_types,
        reviewed_counts: { Decision: 1, Proposal: 0, Objection: 0, Risk: 0, Assumption: 0, OpenQuestion: 1, Metric: 0 },
        reviewed_outputs: [DECISION, REVIEWED_OPEN].map((item) => ({ id: item.id, type: item.type, state: item.state, title: item.title, review_status: item.review_status })),
        interpretation: 'Reviewed output evidence only; not a meeting-quality or success score.',
      }, decisions: [DECISION], commitments: [], open_questions: [REVIEWED_OPEN], candidates: [OPEN], what_changed: [DECISION], pins: [], next_focus: { kind: 'OPEN_QUESTION', title: REVIEWED_OPEN.title, source_ref: REVIEWED_OPEN.id }, review_required: 1 }
    }
    if (pathname === `/api/product/conversation/sessions/${SESSION.id}/continue`) return {
      session: { ...session, status: 'ENDED', ended_at: 3 },
      profile_outcome: {
        profile: 'DESIGN_REVIEW',
        closing_objective: DESIGN_REVIEW_PLAYBOOK.closing_objective,
        priority_truth_types: DESIGN_REVIEW_PLAYBOOK.priority_truth_types,
        reviewed_counts: { Decision: 1, Proposal: 0, Objection: 0, Risk: 0, Assumption: 0, OpenQuestion: 1, Metric: 0 },
        reviewed_outputs: [DECISION, REVIEWED_OPEN].map((item) => ({ id: item.id, type: item.type, state: item.state, title: item.title, review_status: item.review_status })),
        interpretation: 'Reviewed output evidence only; not a meeting-quality or success score.',
      }, 
      decisions: [DECISION], commitments: [], open_questions: [REVIEWED_OPEN], candidates: [OPEN],
      what_changed: [DECISION], pins: [],
      next_focus: { kind: 'OPEN_QUESTION', title: REVIEWED_OPEN.title, source_ref: REVIEWED_OPEN.id }, review_required: 1,
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
    if (pathname === `/api/product/conversation/goals/${goal.id}` && method === 'PATCH') {
      const patch = request.postDataJSON()
      goal = {
        ...goal,
        ...patch,
        resolved_at: patch.status === 'RESOLVED' ? 4 : patch.status === 'ACTIVE' ? null : goal.resolved_at,
      }
      return goal
    }
    if (pathname === `/api/product/conversation/spaces/${SPACE.id}/goals` && method === 'POST') {
      const body = request.postDataJSON()
      return { id: 'cg-2', space_id: SPACE.id, ...body, status: 'ACTIVE', source: { kind: 'USER' }, created_at: 5, resolved_at: null }
    }
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
    // Conversation Home intentionally does not duplicate an Active Spaces
    // directory. The primary loop enters the relevant Space through Next Focus.
    await page.getByRole('button', { name: /rollback owner 还没有明确/ }).click()
    await expect(page.getByText('Open Threads')).toBeVisible()
    await expect(page.getByText(REVIEWED_OPEN.title).first()).toBeVisible()
    await page.goBack()
    await testInfo.attach('v2-conversation-home', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

    await page.getByRole('button', { name: /对话空间/ }).first().click()
    await expect(page).toHaveURL(/#\/conversation\/spaces/)
    await page.getByRole('button', { name: /PDIG · Android Architecture/ }).click()
    await expect(page.getByTestId('conversation-space')).toBeVisible()
    await expect(page.getByText('Conversation Goals')).toBeVisible()
    await expect(page.getByText('Alex · Backend')).toBeVisible()
  })

  test('Open Thread can be resolved from Space through reviewed provenance', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/spaces/${SPACE.id}`)
    await expect(page.getByText('Open Threads')).toBeVisible()
    await expect(page.getByText(THREAD.text).first()).toBeVisible()
    await page.getByLabel('Open Threads').getByRole('button', { name: '标记已解决' }).click()
    await expect(page.getByText('Open Thread 已通过其 reviewed Conversation Item provenance 标记为已解决。')).toBeVisible()
    await expect(page.getByText('暂无已确认的跨场未解决 thread。')).toBeVisible()
  })


  test('Goal editor controls outcome, priority and lifecycle without creating a second truth', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/spaces/${SPACE.id}`)
    await expect(page.getByText('PRIMARY ACTIVE GOAL')).toBeVisible()
    await page.getByRole('button', { name: '编辑' }).click()
    await expect(page.getByPlaceholder('例如：形成 conflict merge strategy 决策')).toHaveValue(SPACE.default_goal)
    await page.getByPlaceholder('例如：形成 conflict merge strategy 决策').fill('决定最终 conflict merge strategy')
    await page.getByPlaceholder('例如：方案、owner 与 rollout 条件均明确').fill('方案、owner 与 rollout 条件都明确')
    await page.getByLabel('Goal 优先级').fill('90')
    await page.getByRole('button', { name: '保存 Goal' }).click()
    await expect(page.getByText('决定最终 conflict merge strategy')).toBeVisible()
    await expect(page.getByText('达成定义 · 方案、owner 与 rollout 条件都明确')).toBeVisible()
    await expect(page.getByText('P90')).toBeVisible()
    await expect(page.getByText('PRIMARY ACTIVE GOAL')).toBeVisible()

    await page.getByRole('button', { name: '完成目标' }).click()
    await expect(page.getByText('RESOLVED')).toBeVisible()
    await expect(page.getByText('PRIMARY ACTIVE GOAL')).toHaveCount(0)

    await page.getByRole('button', { name: '重新打开' }).click()
    await expect(page.getByText('ACTIVE', { exact: true })).toBeVisible()
    await expect(page.getByText('PRIMARY ACTIVE GOAL', { exact: true })).toBeVisible()
  })


  test('Prepare → Preflight → Live → Guidance → Continue is one real product loop', async ({ context, page }, testInfo) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/spaces/${SPACE.id}/prepare`)
    await expect(page.getByRole('heading', { name: SPACE.title })).toBeVisible()
    await expect(page.getByText('DESIGN_REVIEW · Profile Playbook')).toBeVisible()
    await expect(page.getByText(DESIGN_REVIEW_PLAYBOOK.closing_objective)).toBeVisible()
    await expect(page.getByText('不把 Proposal 当 Decision')).toBeVisible()
    await page.getByRole('button', { name: '生成本场并检查' }).click()
    await expect(page.getByText('Session Pack Preview')).toBeVisible()
    await expect(page.getByText('Q4 Benchmark')).toBeVisible()
    await expect(page.getByText(/Ready Sources 1\/1/)).toBeVisible()
    await expect(page.getByText('AI AI_ALLOWED')).toBeVisible()
    await expect(page.getByText('Resolved AI Behavior')).toBeVisible()
    await expect(page.getByText('Auto transcript Guidance · ON')).toBeVisible()
    await expect(page.getByText('Auto candidate extraction · ON')).toBeVisible()
    await expect(page.getByText('记录规则依场景与组织政策而异。')).toBeVisible()
    await page.getByRole('button', { name: '开始会话' }).click()
    await expect(page).toHaveURL(new RegExp(`#/conversation/live/${SESSION.id}`))
    await expect(page.getByTestId('conversation-live')).toBeVisible()
    await expect(page.getByTestId('conversation-live-capture-status')).toHaveText('仅笔记 · 未采集音频')
    await expect(page.getByTestId('conversation-session-pulse')).toBeVisible()
    await expect(page.getByText('Session Pulse')).toBeVisible()
    await expect(page.getByText('Frozen Profile Playbook')).toBeVisible()
    await expect(page.getByText(DESIGN_REVIEW_PLAYBOOK.closing_objective)).toBeVisible()
    await expect(page.getByText(SPACE.default_goal)).toBeVisible()
    await expect(page.getByText('PACK abcdef12')).toBeVisible()
    await expect(page.getByText('Frozen Open Threads')).toBeVisible()
    await expect(page.getByText(REVIEWED_OPEN.title).last()).toBeVisible()
    await expect(page.getByText('Inference · LOCAL_DETERMINISTIC')).toBeVisible()
    await expect(page.getByText('Retention · LOCAL_PRODUCT_DB')).toBeVisible()
    await expect(page.getByText('Write-back · LOCAL_REVIEWED_DRAFT_ONLY')).toBeVisible()
    await expect(page.getByText('Screen · OFF')).toBeVisible()
    await expect(page.getByText('Raw screen image · NOT STORED')).toBeVisible()
    await expect(page.getByText('Frozen AI behavior')).toBeVisible()
    await expect(page.getByText('Policy · AI_ALLOWED')).toBeVisible()
    await expect(page.getByText('Auto Guidance · ON')).toBeVisible()
    await expect(page.getByText('Auto Extraction · ON')).toBeVisible()
    await page.getByText('高级 / 手动 Guidance 验证').click()
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
    await expect(page.getByText('PRIMARY_CARD', { exact: true })).toBeVisible()
    await expect(page.getByText('target cp-1', { exact: true })).toBeVisible()
    await expect(page.getByRole('paragraph').filter({ hasText: 'Q4 benchmark 已覆盖 10x data scale' })).toBeVisible()

    await testInfo.attach('v2-live-guidance', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' })

    await page.getByRole('button', { name: '结束并 Continue' }).click()
    await expect(page.getByText('这场之后')).toBeVisible()
    await expect(page.getByText('DESIGN_REVIEW · Reviewed Outcome Evidence')).toBeVisible()
    await expect(page.getByText('Decision 1', { exact: true })).toBeVisible()
    await expect(page.getByText(/not a meeting-quality or success score/)).toBeVisible()
    await expect(page.getByText('Next Focus · rollback owner 还没有明确')).toBeVisible()
  })

  test('Live exposes explicit Talking Point and Delivery planner lanes', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await page.getByText('高级 / 手动 Guidance 验证').click()
    await expect(page.getByLabel('明确 Talking Point（如有）')).toBeVisible()
    await expect(page.getByLabel('Delivery / 表达重点（如有）')).toBeVisible()
    await page.getByLabel('明确 Talking Point（如有）').fill('先明确 rollback owner 再谈 release window')
    await page.getByLabel('来源 / 依据').fill('Architecture decision note')
    await page.getByRole('button', { name: '评估当前 Guidance' }).click()
    await expect(page.getByText('TALKING_POINT', { exact: true })).toBeVisible()
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

    await page.getByText('高级 / 手动 Guidance 验证').click()
    await page.getByText('模拟：我正在连续表达').click()
    await page.getByLabel('高价值 Opportunity 候选（如有）').fill('应该补充 benchmark')
    await page.getByLabel('来源 / 依据').fill('benchmark source')
    await page.getByRole('button', { name: '评估当前 Guidance' }).click()
    await expect(page.getByText('这一次选择不打扰你')).toBeVisible()
    await expect(page.getByText('SILENT · USER_SPEAKING')).toBeVisible()
    await expect(page.getByText(/Expression Plan · SILENCE/)).toBeVisible()
  })

  test('SILENT polling never revives an older shown Guidance card', async ({ context, page }) => {
    const base = mocks()
    let guidanceReads = 0
    const prior = {
      id: 'ge-older', session_id: SESSION.id, candidate_id: '',
      kind: 'ANSWER_CUE', expression_action: 'ANSWER',
      text: '过期提示绝不能复活', source_refs: [],
      status: 'SHOWN', reason: 'DIRECT_QUESTION', score: {},
      user_action: 'NONE', rendered_at: 1, created_at: 1,
    }
    prior.expression_plan = expressionPlan(prior)
    const newest = {
      ...prior, id: 'ge-silent', status: 'SUPPRESSED',
      expression_action: 'SILENT', text: '', reason: 'USER_SPEAKING',
      rendered_at: null, created_at: 2,
    }
    newest.expression_plan = expressionPlan(newest)
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: async (pathname, method, request) => {
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/guidance`) {
          guidanceReads += 1
          return { items: [newest, prior] }
        }
        return base(pathname, method, request)
      },
    })
    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await expect.poll(() => guidanceReads).toBeGreaterThan(0)
    await expect(page.getByText('这一次选择不打扰你')).toBeVisible()
    await expect(page.getByText('SILENT · USER_SPEAKING')).toBeVisible()
    await expect(page.getByText(/Expression Plan · SILENCE/)).toBeVisible()
    await expect(page.getByText(prior.text)).toHaveCount(0)
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
    await expect(page.getByTestId('conversation-live-capture-status')).toHaveText('转写未启动')
    await expect(page.getByLabel('主音频（优先系统/会议音频）')).toHaveValue('1001')
    await page.getByLabel('我的麦克风（可选）').selectOption('1002')
    await page.getByRole('button', { name: '开始转写' }).click()
    await expect(page.getByText('CAPTURING')).toBeVisible()
    await expect(page.getByTestId('conversation-live-capture-status')).toHaveText('正在采集并转写')
    await expect(page.getByText('只复用 Audio/VAD/STT；不会启动 Interview 自动答题、Fast Cue 或 Interview Review。')).toBeVisible()
    await expect.poll(async () => page.getByText('我们回到 offline migration').count()).toBeGreaterThan(0)
    await page.getByRole('button', { name: '暂停' }).click()
    await expect(page.getByText('PAUSED')).toBeVisible()
    await expect(page.getByTestId('conversation-live-capture-status')).toHaveText('转写已暂停')
    await page.getByRole('button', { name: '继续' }).click()
    await expect(page.getByTestId('conversation-live-capture-status')).toHaveText('正在采集并转写')
    await page.getByRole('button', { name: '停止转写' }).click()
    await expect(page.getByText('OFF', { exact: true })).toBeVisible()
    await expect(page.getByTestId('conversation-live-capture-status')).toHaveText('转写未启动')
  })

  test('HUMAN_ALLOWED exposes an explicit session-scoped Human Coach link with minimum default permissions', async ({ context, page }) => {
    const base = mocks()
    let createBody = null
    const humanSession = {
      ...SESSION,
      policy: {
        ...SESSION.policy,
        human_assistance: 'HUMAN_ALLOWED',
        participant_transparency_plan: 'USER_WILL_NOTIFY_VERBALLY',
      },
    }

    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: async (pathname, method, request) => {
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'GET') return humanSession
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/context` && method === 'GET') {
          const original = await base(pathname, method, request)
          return { ...original, policy: humanSession.policy }
        }
        if (pathname === '/api/coach/sessions' && method === 'GET') {
          return { sessions: [], public_relay: 'BLOCKED-EXTERNAL' }
        }
        if (pathname === '/api/coach/sessions' && method === 'POST') {
          createBody = request.postDataJSON()
          return {
            id: 'coach-conversation',
            urls: {
              local: 'http://127.0.0.1:8000/coach#t=one-time-token',
              lan: '',
              public: '',
            },
            public_relay: 'BLOCKED-EXTERNAL',
          }
        }
        return base(pathname, method, request)
      },
    })

    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await expect(page.getByRole('heading', { name: '人工教练（Conversation）' })).toBeVisible()
    const panel = page.getByTestId('coach-panel')
    await expect(panel.getByText(/链接只绑定当前 Conversation Session/)).toBeVisible()
    await expect(panel.getByLabel('冻结 Session Context')).toBeChecked()
    await expect(panel.getByLabel('本场转写')).not.toBeChecked()
    await expect(panel.getByLabel('当前 AI Guidance')).not.toBeChecked()

    await panel.getByRole('button', { name: '生成教练链接' }).click()
    await expect(panel.getByText('链接只显示这一次（含一次性令牌）：')).toBeVisible()
    expect(createBody).toMatchObject({
      session_kind: 'conversation',
      target_session_id: SESSION.id,
      permissions: {
        transcript: false,
        ai_cue: false,
        session_context: true,
      },
    })
  })


  test('PRIVATE_OVERLAY verifies Electron protection before start and restores baseline after end', async ({ context, page }) => {
    const base = mocks()
    let startBody = null
    let privateSession = {
      ...SESSION,
      status: 'UPCOMING',
      started_at: null,
      pack_id: '',
      policy: { ...SESSION.policy, share_privacy: 'PRIVATE_OVERLAY' },
    }
    const pendingRuntime = {
      requested: 'PRIVATE_OVERLAY',
      available: true,
      requires_desktop: true,
      proof_required: true,
      verified: false,
      runtime: 'ELECTRON_SET_CONTENT_PROTECTION',
      proof_kind: 'ELECTRON_CONTENT_PROTECTION_ACTIVE',
      note: 'best effort only',
    }
    const verifiedRuntime = { ...pendingRuntime, verified: true }

    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: async (pathname, method, request) => {
        if (pathname === `/api/product/conversation/spaces/${SPACE.id}/sessions` && method === 'POST') {
          const body = request.postDataJSON()
          privateSession = {
            ...privateSession,
            title: body.title || privateSession.title,
            capture_mode: body.capture_mode,
            processing_mode: body.processing_mode,
            assistance_mode: body.assistance_mode,
            consent_ack: body.consent_ack,
            policy: { ...privateSession.policy, ...body.policy, share_privacy: 'PRIVATE_OVERLAY' },
          }
          return privateSession
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/preflight`) {
          const original = await base(pathname, method, request)
          return {
            ...original,
            session: privateSession,
            policy: privateSession.policy,
            warnings: [{
              key: 'share_privacy_verify_at_start',
              label: '屏幕共享保护',
              message: '本场将在桌面端点击“开始会话”时临时启用并验证 Electron content protection。',
            }],
            share_privacy_runtime: pendingRuntime,
            pack_preview: {
              ...original.pack_preview,
              share_privacy_runtime: pendingRuntime,
              policy: { ...original.pack_preview.policy, share_privacy: 'PRIVATE_OVERLAY' },
            },
          }
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/start` && method === 'POST') {
          startBody = request.postDataJSON()
          privateSession = { ...privateSession, status: 'ACTIVE', started_at: 2, pack_id: 'cpack-private' }
          return { session: privateSession, pack: { id: 'cpack-private', digest: 'private-pack' } }
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'GET') return privateSession
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/context` && method === 'GET') {
          const original = await base(pathname, method, request)
          return {
            ...original,
            policy: privateSession.policy,
            share_privacy_runtime: verifiedRuntime,
            pack_digest: 'private-pack',
          }
        }
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/end` && method === 'POST') {
          const original = await base(pathname, method, request)
          privateSession = { ...privateSession, status: 'ENDED', ended_at: 3 }
          return { ...original, session: privateSession }
        }
        return base(pathname, method, request)
      },
    })

    await context.addInitScript(() => {
      window.__sharePrivacyMode = 'OFF'
      window.__sharePrivacyCalls = []
      window.electronAPI = {
        hideWindow: async () => {},
        minimizeWindow: async () => {},
        quitApp: async () => {},
        showWindow: async () => {},
        getShortcuts: async () => ({}),
        updateShortcuts: async () => ({ ok: true, shortcuts: {} }),
        resetShortcuts: async () => ({ ok: true, shortcuts: {} }),
        toggleAlwaysOnTop: async () => false,
        toggleContentProtection: async () => false,
        getWindowState: async () => ({ alwaysOnTop: false, contentProtection: window.__sharePrivacyMode === 'PRIVATE_OVERLAY', visible: true }),
        setSharePrivacy: async (mode) => {
          window.__sharePrivacyMode = mode === 'PRIVATE_OVERLAY' ? 'PRIVATE_OVERLAY' : 'OFF'
          window.__sharePrivacyCalls.push(window.__sharePrivacyMode)
          return window.__sharePrivacyMode
        },
        getSharePrivacy: async () => ({
          mode: window.__sharePrivacyMode,
          protected: window.__sharePrivacyMode === 'PRIVATE_OVERLAY',
          note: 'best effort only',
        }),
      }
    })

    await page.goto(`/#/conversation/spaces/${SPACE.id}/prepare`)
    await page.getByLabel('屏幕共享保护').selectOption('PRIVATE_OVERLAY')
    await page.getByRole('button', { name: '生成本场并检查' }).click()
    await expect(page.getByText(/桌面端点击“开始会话”时临时启用并验证/)).toBeVisible()
    await page.getByRole('button', { name: '开始会话' }).click()

    await expect(page).toHaveURL(new RegExp(`#/conversation/live/${SESSION.id}`))
    await expect(page.getByTestId('conversation-share-privacy-status')).toContainText('ACTIVE')
    expect(startBody?.share_privacy_runtime_proof).toBe('ELECTRON_CONTENT_PROTECTION_ACTIVE')
    expect(await page.evaluate(() => window.__sharePrivacyMode)).toBe('PRIVATE_OVERLAY')

    // Simulate tray/other-runtime drift. The ACTIVE Session policy must
    // reassert protection instead of leaving a stale ACTIVE badge.
    await page.evaluate(() => { window.__sharePrivacyMode = 'OFF' })
    await expect.poll(async () => page.evaluate(() => window.__sharePrivacyMode)).toBe('PRIVATE_OVERLAY')
    await expect(page.getByTestId('conversation-share-privacy-status')).toContainText('ACTIVE')

    await page.getByRole('button', { name: '结束并 Continue' }).click()
    await expect(page.getByText('这场之后')).toBeVisible()
    await expect.poll(async () => page.evaluate(() => window.__sharePrivacyMode)).toBe('OFF')
    expect(await page.evaluate(() => window.__sharePrivacyCalls)).toEqual(['PRIVATE_OVERLAY', 'PRIVATE_OVERLAY', 'OFF'])
  })


  test('Review Queue never silently assigns unknown commitment owner to me', async ({ context, page }) => {
    const base = mocks()
    let reviewed = false
    let reviewBody = null
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: async (pathname, method, request) => {
        if (pathname === `/api/product/conversation/sessions/${SESSION.id}/continue`) {
          return {
            session: { ...SESSION, status: 'ENDED', ended_at: 3 },
            decisions: [DECISION],
            commitments: reviewed ? [{ ...COMMITMENT_CANDIDATE, state: 'COMMITTED', owner_id: 'Alex', review_status: 'USER_CONFIRMED' }] : [],
            open_questions: [],
            candidates: reviewed ? [] : [COMMITMENT_CANDIDATE],
            what_changed: reviewed ? [{ ...COMMITMENT_CANDIDATE, state: 'COMMITTED', owner_id: 'Alex', review_status: 'USER_CONFIRMED' }] : [DECISION],
            pins: [],
            next_focus: null,
            review_required: reviewed ? 0 : 1,
          }
        }
        if (pathname === `/api/product/conversation/items/${COMMITMENT_CANDIDATE.id}/review` && method === 'POST') {
          reviewBody = request.postDataJSON()
          reviewed = true
          return { ...COMMITMENT_CANDIDATE, state: 'COMMITTED', owner_id: reviewBody.patch.owner_id, review_status: 'USER_CONFIRMED' }
        }
        return base(pathname, method, request)
      },
    })
    await page.goto(`/#/conversation/spaces/${SPACE.id}/sessions`)
    await page.getByRole('button', { name: 'Continue' }).click()
    await expect(page.getByText('补 rollout plan')).toBeVisible()
    const confirm = page.getByRole('button', { name: '确认' }).last()
    await expect(confirm).toBeDisabled()
    await expect(page.getByText(/不要把主音频里的“我”自动当成当前用户/)).toBeVisible()
    await page.getByLabel('确认 Owner').fill('Alex')
    await expect(confirm).toBeEnabled()
    await confirm.click()
    await expect.poll(() => reviewBody?.patch?.owner_id ?? '').toBe('Alex')
    await expect(page.getByText('没有未确认事项。')).toBeVisible()
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
    await expect(page.getByText('SUPERSEDED', { exact: true })).toBeVisible()
    await expect(page.getByText('AGREED', { exact: true })).toBeVisible()
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


  test('Conversation global search stays grounded in Space Session time and source', async ({ context, page }) => {
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: mocks(),
    })
    await page.goto('/#/conversation/spaces?find=Decision')
    await expect(page.getByTestId('conversation-search')).toBeVisible()
    await expect(page.getByText('查找长期对话事实')).toBeVisible()
    await expect(page.getByText('offline migration 采用 v2')).toBeVisible()
    await expect(page.getByText(/PDIG · Android Architecture · Architecture Review/)).toBeVisible()
    await expect(page.getByText(/来源：TRANSCRIPT_SEGMENT/)).toBeVisible()
    await page.getByRole('button', { name: /offline migration 采用 v2/ }).click()
    await expect(page).toHaveURL(new RegExp(`#/conversation/spaces/${SPACE.id}/decisions`))
  })


  test('MANUAL Screen Context stays in Conversation namespace and never returns raw screenshot bytes', async ({ context, page }) => {
    const base = mocks()
    const manualScreen = async (pathname, method, request) => {
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'GET') {
        return { ...SESSION, policy: { ...SESSION.policy, screen_context: 'MANUAL' } }
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/context` && method === 'GET') {
        const original = await base(pathname, method, request)
        return {
          ...original,
          policy: { ...SESSION.policy, screen_context: 'MANUAL' },
          screen_runtime: {
            mode: 'MANUAL',
            available: true,
            route: 'LOCAL',
            model_name: 'local-vision',
            model_id: 'vision-local',
            fingerprint: 'vision-fp',
            raw_image_persisted: false,
            blockers: [],
          },
        }
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/screen-context` && method === 'GET') return { items: [] }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/screen-context/capture` && method === 'POST') {
        return {
          id: 'csc-e2e',
          space_id: SPACE.id,
          session_id: SESSION.id,
          capture_mode: 'MANUAL',
          region: request.postDataJSON().region === 'configured' ? 'left_half' : request.postDataJSON().region,
          text: '截图可见：rollback owner = Alex；版本 v2。',
          image_hash: 'abcdef1234567890abcdef1234567890',
          vision_model: 'vision-local',
          vision_route: 'LOCAL',
          vision_fingerprint: 'vision-fp',
          source: 'LOCAL_SCREEN_CAPTURE',
          created_at: 4,
        }
      }
      return base(pathname, method, request)
    }
    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: manualScreen,
    })
    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await expect(page.getByTestId('conversation-screen-context')).toBeVisible()
    await expect(page.getByText(/原图不保存/)).toBeVisible()
    await expect(page.getByText('LOCAL', { exact: true }).last()).toBeVisible()
    await page.getByRole('button', { name: '抓取一次' }).click()
    await expect(page.getByText('截图可见：rollback owner = Alex；版本 v2。')).toBeVisible()
    await expect(page.getByText('OBSERVED_NOT_CONFIRMED')).toBeVisible()
    await expect(page.getByText(/raw image NOT STORED/)).toBeVisible()
    await expect(page.locator('body')).not.toContainText('data:image/')
  })


  test('AUTO Screen Context requires explicit Live start and supports Off the record without raw image persistence', async ({ context, page }) => {
    const base = mocks()
    let autoStatus = {
      active: false,
      session_id: '',
      owns_requested_session: false,
      paused: false,
      interval_seconds: 30,
      region: 'configured',
      last_capture_at: null,
      last_error: '',
      consecutive_errors: 0,
      raw_image_persisted: false,
      explicit_start_required: true,
    }
    let observations = []

    const autoScreen = async (pathname, method, request) => {
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}` && method === 'GET') {
        return { ...SESSION, policy: { ...SESSION.policy, screen_context: 'AUTO' } }
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/context` && method === 'GET') {
        const original = await base(pathname, method, request)
        return {
          ...original,
          policy: { ...SESSION.policy, screen_context: 'AUTO' },
          screen_runtime: {
            mode: 'AUTO',
            available: true,
            route: 'LOCAL',
            model_name: 'local-vision',
            model_id: 'vision-local',
            fingerprint: 'vision-auto-fp',
            raw_image_persisted: false,
            auto_requires_explicit_start: true,
            auto_default_interval_seconds: 30,
            blockers: [],
          },
        }
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/screen-context` && method === 'GET') {
        return { items: observations }
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/screen-context/auto` && method === 'GET') {
        return autoStatus
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/screen-context/auto/start` && method === 'POST') {
        const body = request.postDataJSON()
        autoStatus = {
          ...autoStatus,
          active: true,
          session_id: SESSION.id,
          owns_requested_session: true,
          paused: false,
          interval_seconds: body.interval_seconds,
          region: body.region,
          last_capture_at: 5,
          last_error: '',
        }
        observations = [{
          id: 'csc-auto-e2e',
          space_id: SPACE.id,
          session_id: SESSION.id,
          capture_mode: 'AUTO',
          region: body.region === 'configured' ? 'left_half' : body.region,
          text: '自动观察：rollback owner = Alex；版本 v2。',
          image_hash: 'autoabcdef1234567890',
          vision_model: 'vision-local',
          vision_route: 'LOCAL',
          vision_fingerprint: 'vision-auto-fp',
          source: 'LOCAL_SCREEN_CAPTURE',
          created_at: 5,
        }]
        return autoStatus
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/screen-context/auto/pause` && method === 'POST') {
        autoStatus = { ...autoStatus, paused: true }
        return autoStatus
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/screen-context/auto/resume` && method === 'POST') {
        autoStatus = { ...autoStatus, paused: false }
        return autoStatus
      }
      if (pathname === `/api/product/conversation/sessions/${SESSION.id}/screen-context/auto/stop` && method === 'POST') {
        autoStatus = { ...autoStatus, active: false, session_id: '', owns_requested_session: false, paused: false }
        return autoStatus
      }
      return base(pathname, method, request)
    }

    await installMocks(context, {
      messages: COMMON_WS_BOOTSTRAP,
      localStorage: { 'ia-color-scheme': 'vscode-light-plus', 'chengzhu-product-profile': 'conversation' },
      apiOverrides: autoScreen,
    })
    await page.goto(`/#/conversation/live/${SESSION.id}`)
    await expect(page.getByTestId('conversation-screen-context-auto')).toBeVisible()
    await expect(page.getByText('NOT STARTED', { exact: true })).toBeVisible()
    await expect(page.getByText(/不会随会话自动启动/)).toBeVisible()
    await expect(page.locator('body')).not.toContainText('data:image/')

    await page.getByRole('button', { name: '开始自动屏幕上下文' }).click()
    await expect(page.getByText('ACTIVE', { exact: true })).toBeVisible()
    await expect(page.getByText('自动观察：rollback owner = Alex；版本 v2。')).toBeVisible()
    await expect(page.getByText('OBSERVED_NOT_CONFIRMED')).toBeVisible()

    await page.getByRole('button', { name: 'Off the record' }).click()
    await expect(page.getByText('OFF THE RECORD', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '恢复自动观察' }).click()
    await expect(page.getByText('ACTIVE', { exact: true })).toBeVisible()

    await page.getByRole('button', { name: '停止 AUTO' }).click()
    await expect(page.getByText('NOT STARTED', { exact: true })).toBeVisible()
    await expect(page.getByText(/raw image NOT STORED/)).toBeVisible()
    await expect(page.locator('body')).not.toContainText('data:image/')
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
