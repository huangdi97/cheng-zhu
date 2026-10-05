from services.product.future_profile import (
    ConversationItemState,
    ConversationItemType,
    ConversationProfileKind,
    GuidanceKind,
    PROFILES,
    interview_goal_as_conversation_goal,
    profile,
)


def test_future_conversation_profile_contract_is_complete_but_not_productized():
    expected = {
        ConversationProfileKind.INTERVIEW,
        ConversationProfileKind.MEETING,
        ConversationProfileKind.PRESENTATION_QA,
        ConversationProfileKind.ONE_ON_ONE,
        ConversationProfileKind.DESIGN_REVIEW,
        ConversationProfileKind.CLIENT_CALL,
        ConversationProfileKind.NEGOTIATION,
    }
    assert {item.key for item in PROFILES} == expected
    assert [item.key for item in PROFILES if item.productized] == [ConversationProfileKind.INTERVIEW]

    interview = profile(ConversationProfileKind.INTERVIEW)
    assert GuidanceKind.ANSWER_CUE in interview.guidance_kinds
    assert GuidanceKind.RISK in interview.guidance_kinds

    for kind in expected - {ConversationProfileKind.INTERVIEW}:
        future = profile(kind)
        assert future.productized is False
        # The future contract preserves the full seven-kind design without
        # creating Meeting routes/tables/UI in v1.x.
        assert set(future.guidance_kinds) == set(GuidanceKind)


def test_future_conversation_fact_taxonomy_preserves_state_semantics():
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


def test_interview_goal_maps_into_general_conversation_contract():
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
