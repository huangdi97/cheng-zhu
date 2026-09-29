"""Tests for the Stage L1/L2 Job Workspace and the review -> prepare loop (G10).

Pure composition is tested directly; loop tests redirect the intelligence DB
to a tmp SQLite file before touching storage.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import services.storage.intelligence as intel_storage  # noqa: E402
from services.intelligence.candidate_representation import rebuild_and_persist  # noqa: E402
from services.intelligence.job_workspace import (  # noqa: E402
    build_attack_surface,
    build_gap_map,
    build_question_graph,
    build_stories,
    compose_workspace,
    mock_gap_focus,
)
from services.intelligence.review_writeback import write_back_after_review  # noqa: E402

RESUME = """项目经历
订单系统：负责整体架构设计，使用 Redis 做缓存，支撑日均 3 万 QPS，性能提升 40%
搭建内部文档问答助手，使用 RAG 检索
技能
熟悉 Kafka""".strip()

JD = """示例科技
高级后端开发工程师
岗位职责：
负责订单系统的设计与开发
任职要求：
熟悉 Redis、Kafka
熟悉 Kubernetes
有良好的跨团队协作能力""".strip()

ALIGNMENT = [
    {"requirement_text": "Redis", "source": "technology", "status": "STRONG_MATCH", "evidence_claim_ids": ["cl-a"]},
    {"requirement_text": "Kafka", "source": "technology", "status": "PARTIAL_MATCH", "evidence_claim_ids": ["cl-k"]},
    {"requirement_text": "Kubernetes", "source": "technology", "status": "KNOWLEDGE_MATCH", "evidence_claim_ids": []},
    {"requirement_text": "良好的跨团队协作能力", "source": "must_have", "status": "GAP", "evidence_claim_ids": []},
]

CLAIMS = [
    {"id": "cl-a", "type": "fact", "truth_status": "SUPPORTED",
     "text": "订单系统：负责整体架构设计，使用 Redis 做缓存，支撑日均 3 万 QPS"},
    {"id": "cl-b", "type": "fact", "truth_status": "SUPPORTED", "text": "搭建内部文档问答助手，使用 RAG 检索"},
    {"id": "cl-k", "type": "skill", "truth_status": "INFERRED", "text": "熟悉 Kafka"},
    {"id": "cl-x", "type": "fact", "truth_status": "CONTRADICTED", "text": "主导 Kubernetes 迁移"},
]

NO_SIGNALS: dict[str, list[dict]] = {"knowledge_weakness": [], "repeated_topic": []}


@pytest.fixture()
def intel_db(tmp_path, monkeypatch):
    monkeypatch.setattr(intel_storage, "DB_PATH", str(tmp_path / "intelligence.db"))
    intel_storage.init_db()
    return intel_storage


# ---------------------------------------------------------------------------
# Gap Map
# ---------------------------------------------------------------------------


def test_gap_map_is_explainable_and_prioritised():
    gaps = build_gap_map(ALIGNMENT, NO_SIGNALS)
    by_topic = {gap["topic"]: gap for gap in gaps}
    assert "Redis" not in by_topic  # strong matches are not gaps
    assert by_topic["良好的跨团队协作能力"]["priority"] == "high"  # must-have gap
    assert by_topic["Kubernetes"]["status"] == "KNOWLEDGE_MATCH"
    assert "不能说做过" in by_topic["Kubernetes"]["reason"]
    assert by_topic["Kafka"]["priority"] == "low"
    assert gaps[0]["priority"] == "high"
    assert all("%" not in gap["reason"] for gap in gaps)  # no fake precise match


def test_gap_map_folds_in_review_learning_and_dedups():
    signals = {
        "knowledge_weakness": [{"text": "RAG 评估", "confirmations": 3}, {"text": "kubernetes", "confirmations": 1}],
        "repeated_topic": [{"text": "缓存一致性"}],
    }
    gaps = build_gap_map(ALIGNMENT, signals)
    topics = [gap["topic"] for gap in gaps]
    rag = next(gap for gap in gaps if gap["topic"] == "RAG 评估")
    assert rag["priority"] == "high" and rag["source"] == "review" and "3 次" in rag["reason"]
    assert "缓存一致性" in topics
    assert [t.lower() for t in topics].count("kubernetes") == 1


# ---------------------------------------------------------------------------
# Attack Surface / Question Graph
# ---------------------------------------------------------------------------


def test_attack_surface_uses_only_fact_claims_and_ranks_aligned_metrics_first():
    surface = build_attack_surface(CLAIMS, ALIGNMENT)
    ids = [item["claim_id"] for item in surface]
    assert ids == ["cl-a", "cl-b"]  # INFERRED skill + CONTRADICTED excluded
    first = surface[0]
    assert first["job_aligned"] is True
    assert "指标会被追问口径与来源" in first["risks"]
    assert first["probes"] and all(probe.endswith("？") for probe in first["probes"])


def test_question_graph_is_a_tree_with_boundary_chain_for_gaps():
    surface = build_attack_surface(CLAIMS, ALIGNMENT)
    gaps = build_gap_map(ALIGNMENT, NO_SIGNALS)
    nodes = build_question_graph(surface, gaps)
    ids = {node["id"] for node in nodes}
    assert all(node["parent_id"] in ids for node in nodes if node["parent_id"])
    kube = next(node for node in nodes if node["kind"] == "KNOWLEDGE" and "Kubernetes" in node["text"])
    boundary = next(node for node in nodes if node["parent_id"] == kube["id"])
    design = next(node for node in nodes if node["parent_id"] == boundary["id"])
    assert boundary["kind"] == "EXPERIENCE_BOUNDARY"
    assert design["kind"] == "OPEN_DESIGN"


# ---------------------------------------------------------------------------
# Stories: real ones listed, prompts never invent events
# ---------------------------------------------------------------------------


def test_story_prompts_never_contain_fabricated_events():
    stories = [{"id": "st-1", "title": "推动跨团队上线", "tags_json": '["团队协作"]', "truth_status": "VERIFIED"}]
    result = build_stories(stories, ["团队协作", "沟通表达"], CLAIMS)
    assert result["items"][0]["title"] == "推动跨团队上线"
    competencies = [prompt["competency"] for prompt in result["prompts"]]
    assert "团队协作" not in competencies  # covered by a real story
    assert "沟通表达" in competencies
    for prompt in result["prompts"]:
        assert "真实经历" in prompt["hint"]
        assert all(source in [c["text"][:80] for c in CLAIMS] for source in prompt["candidate_sources"])


def test_story_prompts_tolerate_malformed_tags():
    result = build_stories([{"id": "s", "title": "t", "tags_json": "not json"}], [], [])
    assert result["items"][0]["tags"] == []


def test_compose_workspace_has_all_sections():
    workspace = compose_workspace({"competencies": ["团队协作"]}, ALIGNMENT, CLAIMS, [], NO_SIGNALS)
    assert set(workspace) == {"gap_map", "attack_surface", "question_graph", "stories"}


# ---------------------------------------------------------------------------
# Storage: memory ids stable across processes, stories listing
# ---------------------------------------------------------------------------


def test_memory_item_id_is_stable_across_processes():
    code = (
        "import sys; sys.path.insert(0, r'%s');"
        "from services.storage.intelligence import _memory_item_id;"
        "print(_memory_item_id('knowledge_weakness', 'RAG 评估'))" % BACKEND_DIR
    )
    outputs = {
        subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                       env={"PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8", "SYSTEMROOT": "C:\\Windows"},
                       cwd=str(BACKEND_DIR)).stdout.strip()
        for seed in ("1", "2")
    }
    assert len(outputs) == 1


def test_repeated_weakness_accumulates_confirmations(intel_db):
    intel_db.upsert_memory_item("knowledge_weakness", "RAG 评估")
    intel_db.upsert_memory_item("knowledge_weakness", "RAG 评估")
    rows = intel_db.list_memory_items("knowledge_weakness")
    assert len(rows) == 1 and rows[0]["confirmations"] == 2


# ---------------------------------------------------------------------------
# G10: review -> next prepare / mock sees the learning result
# ---------------------------------------------------------------------------


def test_review_learning_reaches_next_workspace_and_mock(intel_db):
    rebuild_and_persist(RESUME)
    before = mock_gap_focus(JD, RESUME, limit=12)
    assert "RAG 评估" not in before["terms"]

    summary = {"weak_points": ["RAG 评估"]}
    write_back_after_review(1, summary, [])
    write_back_after_review(2, summary, [])

    after = mock_gap_focus(JD, RESUME, limit=12)
    assert "RAG 评估" in after["terms"]
    assert any("RAG 评估" in q["question"] and "2 次" in q["why"] for q in after["questions"])


def test_job_title_line_is_not_a_requirement_gap():
    from services.intelligence.job_representation import build_job_representation

    job = build_job_representation(JD)
    assert job.title == "高级后端开发工程师"
    assert job.title not in job.must_have
    assert job.company not in job.must_have


def test_mock_gap_focus_never_persists_a_job(intel_db):
    rebuild_and_persist(RESUME)
    focus = mock_gap_focus(JD, RESUME)
    assert focus["questions"]
    assert intel_db.latest_job_id() == ""


def test_mock_gap_focus_empty_jd():
    assert mock_gap_focus("", "") == {"terms": [], "questions": []}


def test_workspace_endpoint_returns_job_and_workspace(intel_db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.intelligence.router import router

    rebuild_and_persist(RESUME)
    app = FastAPI()
    app.include_router(router, prefix="/api/intelligence")
    res = TestClient(app).post("/api/intelligence/workspace", json={"jd_text": JD, "resume_text": RESUME})
    assert res.status_code == 200
    body = res.json()
    assert body["job_id"] and body["alignment"]["requirements"]
    workspace = body["workspace"]
    assert workspace["attack_surface"][0]["truth_status"] in {"SUPPORTED", "VERIFIED"}
    assert any(node["kind"] == "EXPERIENCE_BOUNDARY" for node in workspace["question_graph"])
    # /job/rebuild contract unchanged
    legacy = TestClient(app).post("/api/intelligence/job/rebuild", json={"jd_text": JD})
    assert legacy.status_code == 200 and "workspace" not in legacy.json()
