"""R2 Stage U: Human Coach MVP — policy, token, TTL, revoke, rate limit,
permissions, advice-not-evidence."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient  # noqa: E402

from services import coach  # noqa: E402
from services.coach import CoachAuthError, CoachPolicyError, CoachRateLimited, CoachRegistry  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_default_policy_refuses_live_and_allows_practice():
    reg = CoachRegistry()
    with pytest.raises(CoachPolicyError):
        reg.create(human_policy="HUMAN_PRACTICE_ONLY", session_kind="live")
    session, token = reg.create(human_policy="HUMAN_PRACTICE_ONLY", session_kind="practice")
    assert session.session_kind == "practice" and len(token) >= 40
    with pytest.raises(CoachPolicyError):
        reg.create(human_policy="HUMAN_FORBIDDEN", session_kind="practice")
    live, _ = reg.create(human_policy="HUMAN_ALLOWED", session_kind="live")
    assert live.session_kind == "live"

    with pytest.raises(CoachPolicyError):
        reg.create(human_policy="HUMAN_PRACTICE_ONLY", session_kind="conversation", live_session_id="conv-1")
    with pytest.raises(CoachPolicyError):
        reg.create(human_policy="HUMAN_ALLOWED", session_kind="conversation")
    conversation, _ = reg.create(
        human_policy="HUMAN_ALLOWED",
        session_kind="conversation",
        live_session_id="conv-1",
        permissions={"session_context": True, "transcript": False},
    )
    assert conversation.session_kind == "conversation"
    assert conversation.live_session_id == "conv-1"
    assert conversation.permissions["session_context"] is True


def test_ai_allowed_does_not_imply_human_allowed():
    from services.intelligence.policy import human_coach_allowed

    # AI policy is not an input at all: only the human policy decides.
    assert human_coach_allowed("", session_kind="live") is False


def test_token_is_hashed_ttl_and_revoke_fail_closed():
    clock = Clock()
    reg = CoachRegistry(clock=clock)
    session, token = reg.create(human_policy="HUMAN_PRACTICE_ONLY", session_kind="practice", ttl_min=10)
    assert token not in repr(session.__dict__)
    assert reg.authenticate(token).id == session.id
    with pytest.raises(CoachAuthError):
        reg.authenticate(token + "x")
    clock.t += 11 * 60
    with pytest.raises(CoachAuthError):
        reg.authenticate(token)
    s2, t2 = reg.create(human_policy="HUMAN_PRACTICE_ONLY", session_kind="practice")
    reg.revoke(s2.id)
    with pytest.raises(CoachAuthError):
        reg.authenticate(t2)


def test_revoke_for_target_is_scoped_to_exact_conversation_session():
    reg = CoachRegistry()
    conv_a, token_a = reg.create(
        human_policy="HUMAN_ALLOWED",
        session_kind="conversation",
        live_session_id="conv-a",
    )
    conv_b, token_b = reg.create(
        human_policy="HUMAN_ALLOWED",
        session_kind="conversation",
        live_session_id="conv-b",
    )
    interview, token_i = reg.create(
        human_policy="HUMAN_ALLOWED",
        session_kind="live",
        live_session_id="interview-live",
    )

    assert reg.revoke_for_target("conv-a", session_kind="conversation") == 1
    with pytest.raises(CoachAuthError):
        reg.authenticate(token_a)
    assert reg.authenticate(token_b).id == conv_b.id
    assert reg.authenticate(token_i).id == interview.id
    assert reg.revoke_for_target("conv-a", session_kind="conversation") == 0


def test_rate_limit():
    clock = Clock()
    reg = CoachRegistry(clock=clock)
    session, _ = reg.create(human_policy="HUMAN_PRACTICE_ONLY", session_kind="practice")
    for _ in range(coach.RATE_LIMIT_PER_MIN):
        reg.take_rate(session)
    with pytest.raises(CoachRateLimited):
        reg.take_rate(session)
    clock.t += 61
    reg.take_rate(session)


def test_coach_cue_is_advice_not_evidence():
    reg = CoachRegistry()
    session, _ = reg.create(human_policy="HUMAN_PRACTICE_ONLY", session_kind="practice")
    payload = coach.coach_cue_payload(session, text="就说你用过 Cluster" * 40)
    assert payload["source"] == "HUMAN_COACH" and payload["is_evidence"] is False
    assert len(payload["text"]) <= coach.MAX_TEXT_CHARS

    conversation, _ = reg.create(
        human_policy="HUMAN_ALLOWED",
        session_kind="conversation",
        live_session_id="conv-42",
    )
    scoped = coach.coach_cue_payload(conversation, text="只提醒当前这场")
    assert scoped["session_kind"] == "conversation"
    assert scoped["target_session_id"] == "conv-42"
    assert scoped["is_evidence"] is False


def test_public_relay_blocked_without_infrastructure(monkeypatch):
    monkeypatch.delenv("COACH_PUBLIC_BASE_URL", raising=False)
    assert coach.public_base_url() == ""


@pytest.fixture()
def client(monkeypatch, tmp_path):
    import services.storage.intelligence as intel_storage

    monkeypatch.setattr(intel_storage, "DB_PATH", str(tmp_path / "intelligence.db"))
    intel_storage.init_db()
    fresh = CoachRegistry()
    monkeypatch.setattr(coach, "registry", fresh)
    import api.coach.router as router

    monkeypatch.setattr(router, "_human_policy_for", lambda kind, target="": "HUMAN_PRACTICE_ONLY")
    sent: list[dict] = []
    monkeypatch.setattr(router, "_broadcast", sent.append)
    import main

    c = TestClient(main.app)
    c.sent = sent  # type: ignore[attr-defined]
    return c


def test_api_flow_permissions_and_revoke(client):
    r = client.post("/api/coach/sessions", json={"session_kind": "live"})
    assert r.status_code == 403 and "仅用于演练" in r.json()["detail"]

    r = client.post("/api/coach/sessions", json={"session_kind": "practice", "permissions": {"transcript": True, "ai_cue": False}})
    assert r.status_code == 200
    body = r.json()
    token = body["urls"]["local"].split("#t=")[1]
    assert "token" not in body and body["public_relay"] == "BLOCKED-EXTERNAL"
    assert client.get("/api/coach/sessions").json()["sessions"][0]["permissions"]["ai_cue"] is False

    assert client.get("/coach/api/state").status_code == 401
    state = client.get("/coach/api/state", headers={"X-Coach-Token": token}).json()
    assert "transcript" in state and "ai_cue" not in state and "resume_jd" not in state

    r = client.post("/coach/api/cue", json={"text": "先说边界"}, headers={"X-Coach-Token": token})
    assert r.status_code == 200
    assert client.sent[-1]["type"] == "coach_cue" and client.sent[-1]["source"] == "HUMAN_COACH"

    client.post(f"/api/coach/sessions/{body['id']}/revoke")
    assert client.post("/coach/api/cue", json={"text": "x"}, headers={"X-Coach-Token": token}).status_code == 401


def test_policy_tightened_mid_session_blocks_cues(client, monkeypatch):
    body = client.post("/api/coach/sessions", json={"session_kind": "practice"}).json()
    token = body["urls"]["local"].split("#t=")[1]
    import api.coach.router as router

    monkeypatch.setattr(router, "_human_policy_for", lambda kind, target="": "HUMAN_FORBIDDEN")
    assert client.post("/coach/api/cue", json={"text": "x"}, headers={"X-Coach-Token": token}).status_code == 403


def test_helper_page_keeps_token_out_of_requests(client):
    html = client.get("/coach").text
    assert "location.hash" in html and "history.replaceState" in html
    assert "X-Coach-Token" in html
    assert "conversation_context" in html
    assert "本场冻结上下文" in html
    assert "本页不能控制对方电脑" in html
    assert client.get("/coach").headers.get("referrer-policy") == "no-referrer"


def test_helper_app_exposes_only_coach_routes():
    """Behavioral check (independent of FastAPI's internal route types): the
    LAN helper app serves the coach page and endpoints and nothing else."""
    from api.coach.router import helper_app

    c = TestClient(helper_app)
    assert c.get("/coach").status_code == 200
    assert c.get("/coach/api/state").status_code == 401
    assert c.post("/coach/api/cue", json={"text": "x"}).status_code == 401
    for path in ("/api/options", "/api/config", "/api/intelligence/facts", "/docs", "/openapi.json", "/"):
        assert c.get(path).status_code == 404, path
