"""Answer Planner: decide HOW to answer before generating any prose.

The planner absorbs services.answer_depth.py (depth contracts) and the intent
of services.copilot_strategy.py (interviewer focus). It outputs a structured
plan — mode, structure, claim constraints — never the full answer.

 INVARIANT:
  - Same LLM, different question types -> visibly different structures; no
    longer "one prompt answers everything".
  - The planner never supplies facts or claims about the candidate.
"""
from __future__ import annotations

from services.intelligence.interviewer_state import planner_hint
from services.intelligence.semantics import (
    ASSERTION_PROMPTS,
    ProvenanceStatus,
    SessionStatus,
    UserAssertionStatus,
    decide_assertion_policy,
    derive_axes,
    route_answer,
)
from services.intelligence.types import (
    AnswerPlan,
    DepthProfile,
    QuestionType,
    ResponseMode,
)

# Per-mode answer structures (master doc sections 17, 27, 28).
_MODE_STRUCTURES: dict[ResponseMode, list[str]] = {
    ResponseMode.EXPERIENCE: ["结论", "场景", "我的职责", "关键动作", "为什么这样做", "结果", "反思"],
    ResponseMode.EXPERIENCE_KNOWLEDGE: ["结论", "项目事实", "技术原因", "trade-off"],
    ResponseMode.KNOWLEDGE: ["直接回答", "机制/因果", "边界", "验证"],
    ResponseMode.HYPOTHETICAL: ["条件重述", "总体思路", "分步设计", "风险与验证", "条件化结论"],
    ResponseMode.OPEN_DESIGN: ["Clarify", "Requirements", "Architecture", "Data", "Scale", "Reliability", "Security", "Observability", "Cost", "Trade-offs", "Evolution"],
    ResponseMode.BEHAVIORAL: ["情境", "挑战", "行动", "结果", "反思"],
    ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE: ["事实边界", "相关经验", "对该技术的理解", "如果落地会怎么做"],
    ResponseMode.CODING: ["Understand", "Clarify", "Approach", "Complexity", "Code", "Edge Cases", "Explain"],
    ResponseMode.SYSTEM_DESIGN: ["Clarify", "FR", "NFR", "Capacity", "API", "Data", "Architecture", "Deep Dive", "Scale", "Reliability", "Security", "Observability", "Cost", "Trade-offs", "Evolution"],
    ResponseMode.CASE: ["澄清问题", "框架", "分析", "建议"],
    ResponseMode.NEGOTIATION: ["立场", "依据", "条件", "备选"],
    ResponseMode.OOD: ["Objects", "Responsibilities", "Relationships", "Patterns", "Extension"],
    ResponseMode.PRODUCT_CASE: ["澄清问题", "用户与目标", "框架", "分析", "建议与指标"],
}

_MODE_PROMPTS: dict[ResponseMode, str] = {
    ResponseMode.EXPERIENCE: (
        "回答模式 EXPERIENCE：讲真实项目。先给结论，再按 场景→我的职责→关键动作→为什么→结果→反思 展开；"
        "所有项目细节只能来自给定证据，不得补写。"
    ),
    ResponseMode.EXPERIENCE_KNOWLEDGE: (
        "回答模式 EXPERIENCE_KNOWLEDGE：先讲自己的项目事实，再讲技术原理与取舍；"
        "项目部分只来自证据，原理部分可以使用通用知识。"
    ),
    ResponseMode.KNOWLEDGE: (
        "回答模式 KNOWLEDGE：直接回答知识本身，不强套简历；候选人没做过不代表不能回答。"
    ),
    ResponseMode.HYPOTHETICAL: (
        "回答模式 HYPOTHETICAL：使用‘如果让我设计/如果规模变化’的条件句表达；"
        "不得把假设改写成‘我们当时就是这么做的’。"
    ),
    ResponseMode.OPEN_DESIGN: (
        "回答模式 OPEN_DESIGN：按 Clarify→Requirements→Architecture→Data→Scale→Reliability→"
        "Security→Observability→Cost→Trade-offs→Evolution 展开开放设计；先澄清关键约束再设计。"
    ),
    ResponseMode.BEHAVIORAL: (
        "回答模式 BEHAVIORAL：优先使用真实 Story Bank 检索到的故事（STAR 结构）；"
        "没有真实故事时提供找故事的方向，不编造事件。"
    ),
    ResponseMode.EXPERIENCE_BOUNDARY_KNOWLEDGE: (
        "回答模式 EXPERIENCE_BOUNDARY_KNOWLEDGE：先明确事实边界（是否做过），再讲相关经验、"
        "对该技术的理解，最后讲‘如果落地会怎么做’；不得把通用知识说成亲历。"
    ),
    ResponseMode.CODING: (
        "回答模式 CODING：按 Understand→Clarify→Approach→Complexity→Code→Edge Cases→Explain 展开；"
        "先讲思路再写代码。"
    ),
    ResponseMode.SYSTEM_DESIGN: (
        "回答模式 SYSTEM_DESIGN：按 Clarify→FR→NFR→Capacity→API→Data→Architecture→Deep Dive→"
        "Scale→Reliability→Security→Observability→Cost→Trade-offs→Evolution 展开；按岗位级别裁剪。"
    ),
    ResponseMode.CASE: (
        "回答模式 CASE：先澄清问题与约束，再给分析框架、量化分析和具体建议。"
    ),
    ResponseMode.NEGOTIATION: (
        "回答模式 NEGOTIATION：先表明立场，再给依据、条件和备选方案；语气专业克制。"
    ),
    ResponseMode.OOD: (
        "回答模式 OOD：按 对象→职责→关系→设计模式→扩展点 展开；先列核心对象再讲交互。"
    ),
    ResponseMode.PRODUCT_CASE: (
        "回答模式 PRODUCT_CASE：先澄清用户与目标，再给分析框架、关键假设和可衡量的建议。"
    ),
}


_LEGACY_TO_PROVENANCE = {
    # Legacy truth_status on the planner came from answer_grounding, where
    # SUPPORTED/VERIFIED meant "the resume states the asked subject".
    "VERIFIED": ProvenanceStatus.DIRECT_EVIDENCE,
    "SUPPORTED": ProvenanceStatus.DIRECT_EVIDENCE,
    "INFERRED": ProvenanceStatus.NO_EVIDENCE,
    "UNKNOWN": ProvenanceStatus.NO_EVIDENCE,
    "CONTRADICTED": ProvenanceStatus.CONFLICTING_EVIDENCE,
    "": ProvenanceStatus.DIRECT_EVIDENCE,
}


def route_for(qtype: QuestionType, *, personal_fact_boundary: bool = False, question_text: str = "") -> ResponseMode:
    """Compatibility wrapper around ``semantics.route_answer`` (the only
    routing table). ``personal_fact_boundary`` = the personal fact is asked
    and no source covers it."""
    act, content, req = derive_axes(qtype, question_text, personal_fact_required=personal_fact_boundary)
    provenance = ProvenanceStatus.NO_EVIDENCE if personal_fact_boundary else ProvenanceStatus.DIRECT_EVIDENCE
    return route_answer(act, content, req, provenance, question_text=question_text)


def create_plan(
    qtype: QuestionType,
    *,
    resolved_question: str = "",
    intent: str = "",
    expected_depth: DepthProfile = DepthProfile.STRUCTURED,
    truth_status: str = "",
    personal_fact_required: bool = False,
    must_use_claim_ids: list[str] | None = None,
    forbidden_claim_ids: list[str] | None = None,
    interviewer_state=None,
    open_world_allowed: bool = True,
    provenance: ProvenanceStatus | str | None = None,
    user_assertion: UserAssertionStatus | str = UserAssertionStatus.UNREVIEWED,
    session_status: SessionStatus | str = SessionStatus.NOT_STATED,
    is_follow_up: bool = False,
    ai_policy: str = "AI_ALLOWED",
    raw_question: str = "",
    state_carries_intent: bool = False,
) -> AnswerPlan:
    """Build the structured plan for one question (no prose)."""
    act, content, req = derive_axes(
        qtype,
        resolved_question,
        is_follow_up=is_follow_up,
        personal_fact_required=personal_fact_required,
        open_world_allowed=open_world_allowed,
        raw_question=raw_question,
    )
    prov = provenance if provenance is not None else _LEGACY_TO_PROVENANCE.get(str(truth_status or "").upper(), ProvenanceStatus.NO_EVIDENCE)
    assertion = decide_assertion_policy(prov, user_assertion, session_status, req, ai_policy=ai_policy)
    mode = route_answer(act, content, req, prov, user_assertion, assertion, question_text=resolved_question, session_status=session_status)
    allow_world = open_world_allowed or mode in {
        ResponseMode.KNOWLEDGE,
        ResponseMode.HYPOTHETICAL,
        ResponseMode.OPEN_DESIGN,
        ResponseMode.SYSTEM_DESIGN,
        ResponseMode.CODING,
    }
    structure = _MODE_STRUCTURES.get(mode, _MODE_STRUCTURES[ResponseMode.KNOWLEDGE])
    hint = planner_hint(interviewer_state)
    prompt_lines = [_MODE_PROMPTS.get(mode, _MODE_PROMPTS[ResponseMode.KNOWLEDGE]), ASSERTION_PROMPTS[assertion]]
    if expected_depth in {DepthProfile.DEEP, DepthProfile.COMPACT_DEEP}:
        prompt_lines.append(
            "按上述结构展开；实时节奏下每层只保留最有价值的 1-2 句。"
            if expected_depth == DepthProfile.COMPACT_DEEP
            else "按上述结构完整展开，每层给出关键决策与验证方式。"
        )
    if intent and not state_carries_intent:
        # When the interview state block already states the intent, repeating
        # it here would put the same fragment in the prompt twice.
        prompt_lines.append(f"当前问题意图：{intent}；回答要直接回应这个意图。")
    if hint:
        prompt_lines.append(hint)
    return AnswerPlan(
        mode=mode,
        intent=[intent] if intent else [],
        structure=structure,
        must_use_claim_ids=list(must_use_claim_ids or []),
        forbidden_claim_ids=list(forbidden_claim_ids or []),
        allow_world_knowledge=allow_world,
        allow_hypothesis=mode in {ResponseMode.HYPOTHETICAL, ResponseMode.OPEN_DESIGN, ResponseMode.SYSTEM_DESIGN},
        depth=expected_depth.value,
        surface="cue_first",
        question_type=qtype.value,
        personal_fact_required=personal_fact_required,
        plan_prompt="\n".join(prompt_lines),
        metadata={
            "truth_status": truth_status,
            "dialogue_act": act.value,
            "content_type": content.value,
            "truth_requirement": req.value,
            "provenance": _coerce_value(prov),
            "user_assertion": _coerce_value(user_assertion),
            "session_status": _coerce_value(session_status),
            "assertion_policy": assertion.value,
        },
    )


def _coerce_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value or "")
