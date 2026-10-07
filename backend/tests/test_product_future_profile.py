from services.product.future_profile import (
    AssistanceMode,
    CONVERSATION_CONTRACT_VERSION,
    ConversationItem,
    ConversationItemState,
    ConversationItemType,
    ConversationProfileKind,
    EpistemicStatus,
    ExpressionAction,
    GuidanceKind,
    OpportunityScore,
    PROFILES,
    ReviewStatus,
    SourceKind,
    SourceRef,
    can_promote_item,
    interview_goal_as_conversation_goal,
    profile,
)


def test_v2_conversation_profile_contract_is_complete_but_not_falsely_productized():
    expected = {
        ConversationProfileKind.INTERVIEW,
        ConversationProfileKind.PROJECT_SYNC,
        ConversationProfileKind.DESIGN_REVIEW,
        ConversationProfileKind.PRESENTATION_QA,
        ConversationProfileKind.ONE_ON_ONE,
        ConversationProfileKind.CLIENT_CALL,
        ConversationProfileKind.NEGOTIATION,
        ConversationProfileKind.MEETING,
    }
    assert CONVERSATION_CONTRACT_VERSION == "v2.0-R1"
    assert {item.key for item in PROFILES} == expected
    assert [item.key for item in PROFILES if item.productized] == [ConversationProfileKind.INTERVIEW]
    assert all(item.design_complete for item in PROFILES)
    assert all(item.runtime_available for item in PROFILES)
    assert {item.key for item in PROFILES if item.launch_wedge} == {
        ConversationProfileKind.PROJECT_SYNC,
        ConversationProfileKind.DESIGN_REVIEW,
    }
    assert profile(ConversationProfileKind.INTERVIEW).specialized_behavior_validated is True
    assert profile(ConversationProfileKind.PROJECT_SYNC).specialized_behavior_validated is False

    assert profile(ConversationProfileKind.PROJECT_SYNC).default_mode is AssistanceMode.BALANCED
    assert profile(ConversationProfileKind.PRESENTATION_QA).default_mode is AssistanceMode.PRESENTATION
    assert profile(ConversationProfileKind.ONE_ON_ONE).default_mode is AssistanceMode.ONE_ON_ONE
    assert set(profile(ConversationProfileKind.CLIENT_CALL).guidance_kinds) == {
        GuidanceKind.RECALL,
        GuidanceKind.ANSWER_CUE,
        GuidanceKind.QUESTION,
        GuidanceKind.RISK,
        GuidanceKind.CONTRIBUTION_OPPORTUNITY,
    }


def test_conversation_profile_guidance_lanes_match_canonical_contract():
    expected = {
        ConversationProfileKind.PROJECT_SYNC: {
            GuidanceKind.RECALL, GuidanceKind.QUESTION, GuidanceKind.RISK,
            GuidanceKind.CONTRIBUTION_OPPORTUNITY,
        },
        ConversationProfileKind.DESIGN_REVIEW: {
            GuidanceKind.RECALL, GuidanceKind.TALKING_POINT, GuidanceKind.QUESTION,
            GuidanceKind.RISK, GuidanceKind.CONTRIBUTION_OPPORTUNITY,
        },
        ConversationProfileKind.PRESENTATION_QA: {
            GuidanceKind.ANSWER_CUE, GuidanceKind.RECALL, GuidanceKind.QUESTION,
            GuidanceKind.DELIVERY,
        },
        ConversationProfileKind.ONE_ON_ONE: {
            GuidanceKind.RECALL, GuidanceKind.QUESTION, GuidanceKind.TALKING_POINT,
        },
        ConversationProfileKind.CLIENT_CALL: {
            GuidanceKind.RECALL, GuidanceKind.ANSWER_CUE, GuidanceKind.QUESTION,
            GuidanceKind.RISK, GuidanceKind.CONTRIBUTION_OPPORTUNITY,
        },
        ConversationProfileKind.NEGOTIATION: {
            GuidanceKind.RECALL, GuidanceKind.TALKING_POINT, GuidanceKind.QUESTION,
            GuidanceKind.RISK,
        },
    }
    for kind, lanes in expected.items():
        assert set(profile(kind).guidance_kinds) == lanes


def test_guidance_and_expression_support_silence_and_opportunity():
    assert set(GuidanceKind) == {
        GuidanceKind.RECALL,
        GuidanceKind.TALKING_POINT,
        GuidanceKind.ANSWER_CUE,
        GuidanceKind.QUESTION,
        GuidanceKind.RISK,
        GuidanceKind.DELIVERY,
        GuidanceKind.CONTRIBUTION_OPPORTUNITY,
    }
    assert ExpressionAction.SILENT in set(ExpressionAction)
    assert ExpressionAction.COMMIT_NEXT_STEP in set(ExpressionAction)


def test_conversation_fact_taxonomy_preserves_state_semantics():
    assert {item.value for item in ConversationItemType} == {
        "Decision",
        "Commitment",
        "Task",
        "Deadline",
        "Risk",
        "Assumption",
        "OpenQuestion",
        "Proposal",
        "Objection",
        "Metric",
        "Status",
    }
    assert {state.value for state in ConversationItemState} == {
        "PROPOSED",
        "AGREED",
        "COMMITTED",
        "DONE",
        "SUPERSEDED",
        "UNKNOWN",
    }


def test_decision_cannot_be_promoted_to_agreed_from_model_extraction_alone():
    source = SourceRef(id="s1", kind=SourceKind.TRANSCRIPT_SEGMENT, excerpt="Let's use v2")
    item = ConversationItem(
        id="i1",
        item_type=ConversationItemType.DECISION,
        state=ConversationItemState.PROPOSED,
        title="Use v2",
        source_refs=[source],
        epistemic_status=EpistemicStatus.OBSERVED,
        review_status=ReviewStatus.AI_EXTRACTED,
    )
    assert can_promote_item(item, ConversationItemState.AGREED) is False

    item.review_status = ReviewStatus.USER_CONFIRMED
    assert can_promote_item(item, ConversationItemState.AGREED) is True


def test_commitment_requires_owner_source_and_confirmation():
    source = SourceRef(id="s1", kind=SourceKind.TRANSCRIPT_SEGMENT, excerpt="I will send it Friday")
    item = ConversationItem(
        id="c1",
        item_type=ConversationItemType.COMMITMENT,
        state=ConversationItemState.PROPOSED,
        title="Send benchmark",
        source_refs=[source],
        review_status=ReviewStatus.USER_CONFIRMED,
    )
    assert can_promote_item(item, ConversationItemState.COMMITTED) is False
    item.owner_id = "me"
    assert can_promote_item(item, ConversationItemState.COMMITTED) is True


def test_opportunity_score_penalizes_interruption_uncertainty_and_staleness():
    strong = OpportunityScore(
        relevance=1,
        novelty=1,
        provenance_strength=1,
        role_relevance=1,
        goal_relevance=1,
        decision_impact=1,
    )
    risky = OpportunityScore(
        relevance=1,
        novelty=1,
        provenance_strength=1,
        role_relevance=1,
        goal_relevance=1,
        decision_impact=1,
        interruption_cost=1,
        uncertainty=1,
        stale_context_risk=1,
    )
    assert strong.value > risky.value


def test_interview_goal_still_maps_into_general_contract():
    mapped = interview_goal_as_conversation_goal(
        {
            "id": "g-1",
            "title": "MindRank · AIDD Agent Engineer",
            "company": "MindRank",
            "role": "AIDD Agent Engineer",
            "stage": "技术二面",
        }
    )
    assert mapped.id == "g-1"
    assert mapped.profile is ConversationProfileKind.INTERVIEW
    assert mapped.counterparty == "MindRank"
    assert mapped.attributes == {"role": "AIDD Agent Engineer", "stage": "技术二面"}
