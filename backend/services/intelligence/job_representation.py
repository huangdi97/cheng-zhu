"""Job Representation: structure a JD and compute explainable alignment.

Deterministic (no LLM, latency-free): a JD must produce structured fields plus
per-requirement alignment with evidence — never a fake precise "93% match".
"""
from __future__ import annotations

import re
import time

from core.logger import get_logger
from services.intelligence.types import AlignmentStatus, JobRepresentation, new_id

_log = get_logger("intelligence.job_representation")

_TECH_DICT: tuple[str, ...] = (
    "Python", "Java", "Go", "Golang", "C\\+\\+", "JavaScript", "TypeScript", "React", "Vue",
    "FastAPI", "Django", "Flask", "Spring", "Node\\.?js", "MySQL", "PostgreSQL", "Postgres",
    "Redis", "MongoDB", "Kafka", "RabbitMQ", "Elasticsearch", "ElasticSearch", "ES",
    "Kubernetes", "K8s", "Docker", "AWS", "Azure", "GCP", "LLM", "RAG", "Agent",
    "PyTorch", "TensorFlow", "SQL", "Linux", "Git", "Spark", "Flink", "Hive",
    "向量数据库", "微服务", "分布式", "高并发", "高可用", "大模型", "深度学习", "机器学习",
)

_LEVEL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"资深|专家|Principal|Staff", "senior"),
    (r"高级|高级工程师|Senior", "senior"),
    (r"中级|Mid[- ]level", "mid"),
    (r"初级|Junior|实习|校招|应届", "junior"),
)

_TECH_DIMENSIONS: tuple[tuple[str, str], ...] = (
    (r"redis|缓存", "缓存设计与一致性"),
    (r"kafka|rabbitmq|消息队列|mq", "消息队列与顺序性"),
    (r"mysql|postgres|mongo|数据库|分库分表", "数据库设计与调优"),
    (r"llm|大模型|rag|agent|微调", "模型评估与效果验证"),
    (r"k8s|kubernetes|docker|容器", "容器化与编排"),
    (r"高并发|高可用|微服务|分布式", "限流、容量与容灾"),
    (r"react|vue|前端", "前端性能与状态管理"),
    (r"spark|flink|hive|数据", "数据管道与治理"),
    (r"pytorch|tensorflow|深度学习", "训练与推理优化"),
)

_COMPETENCY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"沟通", "沟通表达"),
    (r"协作|合作|跨团队", "团队协作"),
    (r"推动|主导|owner", "ownership"),
    (r"学习|好奇", "学习能力"),
    (r"逻辑|分析", "结构化思维"),
    (r"抗压|压力", "抗压能力"),
)


def _clean(text: str) -> str:
    return (text or "").strip(" \t\r\n-•。；;，,")


def _find_techs(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _TECH_DICT:
        display = pattern.replace("\\+\\+", "++").replace("\\.?", ".").replace("\\.", ".")
        if re.search(pattern, text, re.IGNORECASE):
            name = display.replace("++", "++")
            if name not in found:
                found.append(name)
    return found[:14]


def _is_requirement_line(line: str) -> bool:
    return bool(re.search(r"负责|主导|参与|推动|设计|开发|搭建|维护|熟悉|精通|掌握|扎实|深入|了解", line))


def build_job_representation(
    jd_text: str,
    *,
    company: str = "",
    title: str = "",
    role: str = "",
) -> JobRepresentation:
    """Deterministic JD structuring; never fabricates company/title."""
    raw = jd_text or ""
    lines = [_clean(line) for line in raw.splitlines()]
    lines = [line for line in lines if line]

    company_found = company.strip()
    if not company_found:
        for line in lines[:8]:
            match = re.search(r"([\u4e00-\u9fffA-Za-z0-9·]{2,20})(?:公司|科技|技术|集团)", line)
            if match:
                company_found = match.group(0)
                break

    title_found = (title or role).strip()
    if not title_found:
        for line in lines[:6]:
            match = re.search(r"([\u4e00-\u9fffA-Za-z+#.\-/]{2,24}(?:工程师|开发|算法|产品经理|架构师|经理|专家))", line)
            if match:
                title_found = match.group(0)
                break

    level_found = ""
    for pattern, normalized in _LEVEL_PATTERNS:
        if re.search(pattern, raw, re.IGNORECASE):
            level_found = normalized
            break
    if not level_found and title_found:
        level_found = "mid"

    responsibilities: list[str] = []
    must_have: list[str] = []
    nice_to_have: list[str] = []
    in_nice_section = False
    for line in lines:
        # A bare title line ("高级后端开发工程师") matches the 开发 verb; it is
        # the job's name, not a requirement the candidate could be missing.
        if line in (title_found, company_found):
            continue
        if re.search(r"加分|优先|plus|nice[- ]?to[- ]?have", line, re.IGNORECASE):
            # “加分：xxx” may carry items on the header line itself.
            if re.search(r"[:：]", line):
                stripped = _clean(re.sub(r"^.*?(?:加分|优先|plus|nice[- ]?to[- ]?have)[:：]\s*", "", line, flags=re.IGNORECASE))
                if stripped and stripped not in nice_to_have:
                    nice_to_have.append(stripped[:60])
                in_nice_section = True
                continue
            in_nice_section = True
            continue
        if re.search(r"任职要求|岗位要求|我们期待", line):
            in_nice_section = False
            continue
        if re.search(r"要求：", line):
            # “要求：xxx” may carry items on the header line itself; strip the
            # header prefix and keep parsing the remainder.
            line = _clean(re.sub(r"^(?:任职要求|岗位要求|我们期待|要求)[:：]?\s*", "", line))
            if not line:
                continue
        if _is_requirement_line(line):
            target = nice_to_have if in_nice_section else must_have
            bucket = responsibilities if re.search(r"负责|主导|参与|推动|design|build", line, re.IGNORECASE) and not re.search(r"熟悉|精通|掌握|扎实", line) else target
            if re.search(r"负责|主导|参与|推动", line):
                if line[:60] not in responsibilities:
                    responsibilities.append(line[:60])
            elif line[:60] not in bucket:
                bucket.append(line[:60])

    technologies = _find_techs(raw)
    competencies: list[str] = []
    for pattern, name in _COMPETENCY_PATTERNS:
        if re.search(pattern, raw, re.IGNORECASE):
            competencies.append(name)

    dimensions: list[str] = []
    for pattern, dimension in _TECH_DIMENSIONS:
        if re.search(pattern, raw, re.IGNORECASE) and dimension not in dimensions:
            dimensions.append(dimension)
    if not dimensions:
        dimensions = ["项目深挖", "技术基础"]
    return JobRepresentation(
        job_id=new_id("job-"),
        company=company_found[:40],
        title=title_found[:40],
        level=level_found,
        jd_text=raw,
        responsibilities=responsibilities[:10],
        must_have=must_have[:12],
        nice_to_have=nice_to_have[:10],
        technologies=technologies,
        competencies=competencies[:8],
        likely_interview_dimensions=dimensions[:12],
        created_at=time.time(),
        updated_at=time.time(),
    )


def compute_alignment(
    job: JobRepresentation,
    resume_text: str,
    claim_texts: list[str] | None = None,
    claim_ids: list[str] | None = None,
) -> list[dict]:
    """Per-requirement alignment with evidence claim ids (no percentages)."""
    claim_texts = claim_texts or []
    claim_ids = claim_ids or [""] * len(claim_texts)
    resume_lc = (resume_text or "").lower()
    results: list[dict] = []
    seen: set[str] = set()

    def _classify(requirement: str, source: str) -> None:
        text = _clean(requirement)
        if not text or text in seen:
            return
        seen.add(text)
        evidence_ids: list[str] = []
        strong = False
        partial = False
        terms = [chunk for chunk in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z][a-zA-Z0-9+#.\-/]{2,}", text.lower())][:6]
        for term in terms:
            if term in resume_lc:
                for idx, claim in enumerate(claim_texts):
                    if term.lower() in claim.lower():
                        if idx < len(claim_ids) and claim_ids[idx]:
                            evidence_ids.append(claim_ids[idx])
                        if re.search(r"做过|使用|负责|参与|实现|搭建|设计|开发|优化|落地", claim):
                            strong = True
                        else:
                            partial = True
        if strong:
            status = AlignmentStatus.STRONG_MATCH
            explanation = "简历/材料中有带动作动词的项目证据"
        elif partial:
            status = AlignmentStatus.PARTIAL_MATCH
            explanation = "仅技能层面提及（熟悉/了解），无项目落地证据"
        elif terms and any(re.search(pattern, text, re.IGNORECASE) for pattern in _TECH_DICT):
            status = AlignmentStatus.KNOWLEDGE_MATCH
            explanation = "无候选人证据，但属于可由通用知识覆盖的技术域"
        elif text:
            status = AlignmentStatus.GAP
            explanation = "无候选人证据，也不属于已知技术域，需要准备"
        else:
            status = AlignmentStatus.UNKNOWN
            explanation = "要求内容无法解析"
        results.append(
            {
                "requirement_text": text[:120],
                "source": source,
                "status": status.value,
                "evidence_claim_ids": list(dict.fromkeys(evidence_ids))[:6],
                "explanation": explanation,
            }
        )

    for requirement in job.must_have:
        _classify(requirement, "must_have")
    for technology in job.technologies:
        _classify(technology, "technology")
    for responsibility in job.responsibilities[:6]:
        _classify(responsibility, "responsibility")
    return results


def save_job(job: JobRepresentation, job_id: str = "", alignment: list[dict] | None = None) -> str:
    """Persist via the intelligence storage layer; returns the job id."""
    try:
        from services.storage import intelligence as intel_storage

        final_id = job_id or job.job_id or new_id("job-")
        if alignment is not None:
            job.alignment = {"requirements": alignment}
        intel_storage.save_job_profile(final_id, job.payload())
        return final_id
    except Exception as exc:  # noqa: BLE001
        # Persistence is a mirror; the in-memory representation remains usable.
        _log.warning("job profile persist failed: %s", exc)
        return job_id or job.job_id
