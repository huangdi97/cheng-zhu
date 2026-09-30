"""Tests for candidate/job representation, alignment and the evidence graph.

Deterministic builders are pure logic; rebuild_and_persist tests redirect the
intelligence DB to a tmp SQLite file via monkeypatch before touching storage.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import services.storage.intelligence as intel_storage  # noqa: E402
from services.intelligence.candidate_representation import (  # noqa: E402
    build_candidate_representation,
    extract_experience_expansion,
    rebuild_and_persist,
)
from services.intelligence.evidence_graph import (  # noqa: E402
    claim_status_summary,
    claims_for_subject,
    strongest_claim,
)
from services.intelligence.job_representation import (  # noqa: E402
    build_job_representation,
    compute_alignment,
)
from services.intelligence.types import AlignmentStatus, JobRepresentation, TruthStatus  # noqa: E402

MIXED_RESUME = """工作经历
2020-2023 阿里巴巴 高级工程师
项目经历
订单系统：负责整体架构设计，使用 Redis Cluster 做分片，支撑日均 3 万 QPS，性能提升 40%
订单系统：负责整体架构设计，使用 Redis Cluster 做分片，支撑日均 3 万 QPS，性能提升 40%
技能
熟悉 Kafka，了解 Flink
教育经历
2016-2020 浙江大学 本科 计算机科学与技术""".strip()

JD_TEXT = """某某科技有限公司
高级后端开发工程师
岗位职责：
负责订单系统的设计与开发
主导核心链路的性能优化
任职要求：
精通 Python，熟悉 MySQL、Redis
熟悉 Kafka 等消息队列
加分：
熟悉 Kubernetes""".strip()

# Per-requirement alignment states, one fixture per explainable status.
ALIGNMENT_FIXTURES = [
    ("使用 Redis Cluster 做分片", "使用 Redis Cluster 做分片的订单系统",
     ["负责订单系统：使用 Redis Cluster 做分片，支撑日均 3 万 QPS"], ["cl-1"], AlignmentStatus.STRONG_MATCH),
    ("熟悉 Kafka 生态", "熟悉 Kafka，了解 Flink", ["熟悉 Kafka，了解 Flink"], ["cl-2"], AlignmentStatus.PARTIAL_MATCH),
    ("精通 Elasticsearch 调优", "熟悉 Kafka，了解 Flink", [], [], AlignmentStatus.KNOWLEDGE_MATCH),
    ("会占星术与塔罗", "熟悉 Kafka，了解 Flink", [], [], AlignmentStatus.GAP),
]


@pytest.fixture()
def intel_db(tmp_path, monkeypatch):
    """Redirect the intelligence DB to a tmp file, then (re-)init it."""
    db_path = str(tmp_path / "intelligence.db")
    monkeypatch.setattr(intel_storage, "DB_PATH", db_path)
    intel_storage.init_db()
    return intel_storage


def test_mixed_resume_builds_claims_with_supported_and_inferred_statuses():
    rep = build_candidate_representation(MIXED_RESUME)

    fact_claims = [claim for claim in rep.claims if claim.truth_status == TruthStatus.SUPPORTED]
    skill_claims = [claim for claim in rep.claims if claim.truth_status == TruthStatus.INFERRED]

    assert any("订单系统" in claim.text for claim in fact_claims)
    assert fact_claims[0].confidence == 0.8
    assert any("Kafka" in claim.text for claim in skill_claims)
    assert skill_claims[0].confidence == 0.6
    assert len(rep.claims) == 2  # duplicate line merges; unique lines only


def test_duplicate_resume_line_merges_and_keeps_distinct_evidence_links():
    rep = build_candidate_representation(MIXED_RESUME)

    project_claim = next(claim for claim in rep.claims if "订单系统" in claim.text)
    metadata = json.loads(project_claim.metadata_json)
    evidence_ids = [json.loads(claim.metadata_json)["evidence_id"] for claim in rep.claims]

    assert metadata["merged"] == 1
    assert metadata["evidence_id"]
    assert len(evidence_ids) == len(set(evidence_ids)) == 2


def test_resume_metrics_are_extracted_with_units():
    rep = build_candidate_representation(MIXED_RESUME)

    units = {metric["unit"] for metric in rep.metrics}

    assert "万" in units  # 日均 3 万 QPS
    assert "%" in units  # 性能提升 40%
    assert all(metric["value"] for metric in rep.metrics)


def test_resume_sections_are_parsed_into_entities():
    rep = build_candidate_representation(MIXED_RESUME)

    assert rep.experiences[0]["company"] == "阿里巴巴"
    assert rep.experiences[0]["period"] == "2020-2023"
    assert rep.projects[0]["name"] == "订单系统"
    assert rep.education[0]["school"] == "浙江大学"
    assert rep.education[0]["degree"] == "本科"
    assert any(skill["name"] == "熟悉 Kafka" for skill in rep.skills)


def test_empty_resume_and_empty_jd_yield_empty_representations():
    rep = build_candidate_representation("   \n  ")
    assert rep.claims == [] and rep.experiences == [] and rep.metrics == [] and rep.profile_text == ""

    job = build_job_representation("")
    assert job.title == "" and job.company == "" and job.must_have == []
    assert job.responsibilities == [] and job.nice_to_have == []


def test_rebuild_and_persist_writes_claims_without_duplicating_on_rerun(intel_db):
    rebuild_and_persist(MIXED_RESUME, candidate_id="cand-rebuild")
    rep = rebuild_and_persist(MIXED_RESUME, candidate_id="cand-rebuild")

    assert rep.candidate_id == "cand-rebuild"
    assert len(intel_storage.list_claims("cand-rebuild")) == 2
    assert len(intel_storage.list_evidence("cand-rebuild")) == 4  # one per unique line


def test_experience_expansion_returns_bounded_keyword_aware_questions():
    base = extract_experience_expansion("负责订单系统的整体架构设计")
    with_cache = extract_experience_expansion("使用 Redis 缓存做分片")

    assert 0 < len(base) <= 12
    assert any("为什么" in question for question in base)
    assert all(question.strip() for question in base)
    assert "缓存的一致性是怎么保证的？" in with_cache
    assert "缓存的一致性是怎么保证的？" not in base
    assert len(with_cache) == 12


def test_jd_structures_title_level_and_requirements():
    rep = build_job_representation(JD_TEXT)

    assert rep.title == "高级后端开发工程师"
    assert rep.level == "senior"
    assert rep.company.endswith("公司")
    assert any("订单系统" in item for item in rep.responsibilities)
    assert any("Python" in item for item in rep.must_have)
    assert any("Kubernetes" in item for item in rep.nice_to_have)
    assert "Redis" in rep.technologies
    assert "Kafka" in rep.technologies
    assert rep.likely_interview_dimensions


@pytest.mark.parametrize(("requirement", "resume", "claims", "ids", "expected"), ALIGNMENT_FIXTURES)
def test_alignment_classifies_requirement_by_available_evidence(
    requirement: str, resume: str, claims: list[str], ids: list[str], expected: AlignmentStatus
):
    job = JobRepresentation(job_id="job-align", must_have=[requirement])

    results = compute_alignment(job, resume, claims, ids)

    assert results[0]["status"] == expected.value
    assert "%" not in results[0]["explanation"]


def test_alignment_with_claims_carries_evidence_ids_and_no_percentages():
    job = JobRepresentation(
        job_id="job-align",
        must_have=["使用 Redis Cluster 做分片", "熟悉 Kafka 生态", "精通 Elasticsearch 调优", "会占星术与塔罗"],
    )

    results = compute_alignment(
        job, "使用 Redis Cluster 做分片，熟悉 Kafka",
        ["负责订单系统：使用 Redis Cluster 做分片", "熟悉 Kafka，了解 Flink"], ["cl-1", "cl-2"],
    )

    assert len(results) == 4
    assert results[0]["evidence_claim_ids"] == ["cl-1"]
    assert results[1]["evidence_claim_ids"] == ["cl-2"]
    assert all("%" not in item["explanation"] for item in results)


def test_claims_for_subject_requires_every_qualifier():
    claims = [
        {"id": "cl-redis-cluster", "text": "我使用 Redis Cluster 做了分片", "truth_status": "SUPPORTED", "confidence": 0.8},
        {"id": "cl-redis", "text": "我使用 Redis 做缓存", "truth_status": "SUPPORTED", "confidence": 0.7},
    ]

    assert [claim["id"] for claim in claims_for_subject(claims, ["redis", "cluster"])] == ["cl-redis-cluster"]
    assert len(claims_for_subject(claims, ["redis"])) == 2


def test_strongest_claim_excludes_contradicted_and_summary_counts():
    claims = [
        {"id": "cl-bad", "text": "我使用 Redis Cluster 做了分片", "truth_status": "CONTRADICTED", "confidence": 0.99},
        {"id": "cl-good", "text": "我使用 Redis Cluster 支撑订单链路", "truth_status": "SUPPORTED", "confidence": 0.7},
        {"id": "cl-inf", "text": "熟悉 Kafka", "truth_status": "INFERRED", "confidence": 0.5},
    ]

    strongest = strongest_claim(claims, ["redis", "cluster"])

    assert strongest is not None and strongest["id"] == "cl-good"
    assert strongest_claim([claims[0]], ["redis", "cluster"]) is None

    summary = claim_status_summary(claims)

    assert summary["SUPPORTED"] == 1 and summary["INFERRED"] == 1 and summary["CONTRADICTED"] == 1
    assert summary["UNKNOWN"] == 0 and summary["VERIFIED"] == 0
