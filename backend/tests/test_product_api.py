"""HTTP contract for /api/product (TestClient over the real app routes)."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.product import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/product")
    return TestClient(app)


def test_goal_home_history_flow_over_http(product_env):
    c = _client()
    assert c.get("/api/product/home").json()["state"] == "NO_GOAL"
    assert c.post("/api/product/goals", json={}).status_code == 400
    goal = c.post("/api/product/goals", json={"company": "MindRank", "role": "AIDD Agent Engineer",
                                              "jd": "任职要求：熟悉 RAG"}).json()
    gid = goal["id"]
    detail = c.get(f"/api/product/goals/{gid}", params={"opened": True}).json()
    assert detail["title"] == "MindRank · AIDD Agent Engineer" and "next_focus" in detail
    assert c.get("/api/product/goals/nope").status_code == 404
    prep = c.get(f"/api/product/goals/{gid}/prepare").json()
    assert {"gap_map", "attack_surface", "question_graph", "stories", "pack_preview"} <= set(prep)

    s = c.post("/api/product/practice", json={"goal_id": gid, "round": "TECHNICAL", "sources": ["ROLE_BANK"],
                                              "questions": 1, "closing": False}).json()
    done = c.post(f"/api/product/practice/{s['practice_id']}/answer", json={"answer": "我们做了缓存。"}).json()
    assert done["done"] is True
    hist = c.get("/api/product/history", params={"goal_id": gid}).json()["items"]
    assert len(hist) == 1 and hist[0]["type"] == "PRACTICE"
    refl = c.get(f"/api/product/reflection/practice/{s['practice_id']}").json()
    assert "first_screen" in refl


def test_quick_note_conflict_is_409_with_current_row(product_env):
    c = _client()
    note = c.post("/api/product/quick-notes", json={"content": "a"}).json()
    ok = c.patch(f"/api/product/quick-notes/{note['id']}", json={"content": "b", "base_revision": 1})
    assert ok.status_code == 200
    stale = c.patch(f"/api/product/quick-notes/{note['id']}", json={"content": "c", "base_revision": 1})
    assert stale.status_code == 409 and stale.json()["detail"]["current"]["content"] == "b"


def test_route_ordering_and_misc_endpoints(product_env):
    c = _client()
    assert c.post("/api/product/fact-inbox/batch", json={"ids": [], "action": "DISMISS"}).json() == {"done": [], "failed": []}
    assert c.post("/api/product/nudges/evaluate", json={"session_id": "s"}).json()["suppressed"]
    assert c.get("/api/product/practice/options").json()["personas"]
    assert c.get("/api/product/rubrics").json()["items"]
    assert c.get("/api/product/question-banks").json()["items"]
    assert c.get("/api/product/validation").json()["real_user_validation"] == "REAL_USER_VALIDATION_PENDING"
    assert c.get("/api/product/future-profile").json()["status"].endswith("NOT_PRODUCTIZED")
    assert c.post("/api/product/events", json={"name": "fast_cue_expanded"}).json()["recorded"] is True
    assert c.post("/api/product/closing/detect", json={"text": "你有什么想问我们的？"}).json()["trigger"] == "INTERVIEW_CLOSING"
    layers = c.get("/api/product/settings/layers").json()
    assert layers["items"]["answer_language"]["origin"] in ("GLOBAL", "SYSTEM")
    assert c.put("/api/product/settings/layers", json={"scope": "GOAL", "scope_id": "g", "key": "api_key",
                                                       "value": "x"}).status_code == 400


def test_conversation_participant_and_guidance_http_contracts_do_not_cross_fields(product_env):
    c = _client()
    space = c.post("/api/product/conversation/spaces", json={
        "title": "Packaged Evidence",
        "profile": "PROJECT_SYNC",
    }).json()
    participant = c.post(f"/api/product/conversation/spaces/{space['id']}/participants", json={
        "display_name": "Alex",
        "role": "CTO",
        "explicit_priority": "稳定性",
        "explicit_concern": "回滚风险",
        "relationship_context": "客户技术负责人",
    })
    assert participant.status_code == 200
    pid = participant.json()["id"]

    session = c.post(f"/api/product/conversation/spaces/{space['id']}/sessions", json={
        "title": "Review",
        "capture_mode": "NOTES_ONLY",
        "processing_mode": "LOCAL",
        "consent_ack": True,
    }).json()
    started = c.post(f"/api/product/conversation/sessions/{session['id']}/start")
    assert started.status_code == 200

    guidance = c.post(f"/api/product/conversation/sessions/{session['id']}/guidance/evaluate", json={
        "current_topic": "迁移稳定性",
        "direct_question": "现在主要看什么？",
        "audience_participant_id": pid,
        "audience_role": "CTO",
        "audience_priority": "稳定性",
        "audience_concern": "回滚风险",
    })
    assert guidance.status_code == 200
