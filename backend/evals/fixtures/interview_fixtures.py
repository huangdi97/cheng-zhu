"""Chengzhu eval fixtures.

The mandatory seven-turn dialogue (canonical section 40) plus the category
fixtures required by Stage R. Fixtures are pure data; the runner reconstructs
dialogue state and asserts routes/truth boundaries deterministically.
"""
from __future__ import annotations

SEVEN_TURN_RESUME = "构建 RAG + Agent 系统，使用 Redis 保存部分 session state。负责核心检索链路，QPS 3万。"

SEVEN_TURN_QUESTIONS: list[dict] = [
    {"id": "Q1", "question": "介绍一下你的项目。", "expected_route": "EXPERIENCE", "category": "resume_factual"},
    {"id": "Q2", "question": "为什么选 RAG？", "expected_route": "EXPERIENCE_KNOWLEDGE", "category": "resume_factual"},
    {"id": "Q3", "question": "为什么不用 fine-tuning？", "expected_route": "EXPERIENCE_KNOWLEDGE", "category": "follow_up"},
    {"id": "Q4", "question": "如果数据量扩大 100 倍呢？", "expected_route": "HYPOTHETICAL", "category": "hypothetical"},
    {"id": "Q5", "question": "那 Redis 会有什么问题？", "expected_route": "KNOWLEDGE", "category": "resume_outside_knowledge"},
    {"id": "Q6", "question": "你实际用过 Redis Cluster 吗？", "expected_route": "EXPERIENCE_BOUNDARY", "category": "boundary"},
    {"id": "Q7", "question": "没用过的话，你会怎么迁？", "expected_route": "OPEN_DESIGN", "category": "resume_outside_knowledge"},
]

SEVEN_TURN_FORBIDDEN: dict[str, list[str]] = {
    "Q6": ["我们用了 Redis Cluster", "我用了 Redis Cluster", "我们当时用了 Redis Cluster", "我用过 Redis Cluster"],
}


def _entry(
    fixture_id: str,
    *,
    category: str,
    question: str,
    expected_question_type: str,
    expected_route: str,
    resume_text: str = "",
    dialogue_history: list[dict] | None = None,
    forbidden_claims: list[str] | None = None,
    required_structure_hint: str = "",
) -> dict:
    return {
        "id": fixture_id,
        "category": category,
        "question": question,
        "resume_text": resume_text,
        "dialogue_history": dialogue_history or [],
        "expected_question_type": expected_question_type,
        "expected_route": expected_route,
        "forbidden_claims": forbidden_claims or [],
        "required_structure_hint": required_structure_hint,
    }


ALL_FIXTURES: list[dict] = [
]

ALL_FIXTURES = [
    _entry(
        "resume-outside-transformer",
        category="resume_outside_knowledge",
        question="Transformer 为什么需要 positional encoding？",
        expected_question_type="KNOWLEDGE",
        expected_route="KNOWLEDGE",
        resume_text=SEVEN_TURN_RESUME,
        forbidden_claims=["我用过 Transformer", "我做过 Transformer"],
    ),
    _entry(
        "system-design-short-video",
        category="system_design",
        question="设计一个支持百万 DAU 的短视频系统。",
        expected_question_type="SYSTEM_DESIGN",
        expected_route="SYSTEM_DESIGN",
        resume_text=SEVEN_TURN_RESUME,
    ),
    _entry(
        "coding-lru",
        category="coding",
        question="写一个 LRU 缓存。",
        expected_question_type="CODING",
        expected_route="CODING",
        resume_text=SEVEN_TURN_RESUME,
    ),
    _entry(
        "behavioral-cross-team",
        category="behavioral",
        question="讲一次你推动跨团队项目的经历。",
        expected_question_type="BEHAVIORAL",
        expected_route="BEHAVIORAL",
        resume_text=SEVEN_TURN_RESUME,
    ),
    _entry(
        "contradiction-redis-cluster",
        category="contradiction",
        question="你们当时用了 Redis Cluster 吗？",
        expected_question_type="EXPERIENCE",
        expected_route="EXPERIENCE_BOUNDARY",
        resume_text=SEVEN_TURN_RESUME,
        dialogue_history=[
            {"question": "介绍一下你的项目。", "answer": "我们做了 RAG + Agent 问答系统，我用 Redis 保存 session state。"},
            {"question": "为什么选 Redis？", "answer": "因为 session state 读写频繁，Redis 的内存读写快。"},
        ],
        forbidden_claims=["我们用了 Redis Cluster", "我们当时用了 Redis Cluster 做分片"],
    ),
    _entry(
        "hypothetical-traffic-100x",
        category="hypothetical",
        question="如果流量增长 100 倍怎么办？",
        expected_question_type="HYPOTHETICAL",
        expected_route="HYPOTHETICAL",
        resume_text=SEVEN_TURN_RESUME,
        dialogue_history=[{"question": "介绍一下你的项目。", "answer": "我们做了 RAG 问答系统，QPS 3万。"}],
    ),
    _entry(
        "company-knowledge",
        category="company",
        question="你对我们公司了解多少？",
        expected_question_type="COMPANY",
        expected_route="KNOWLEDGE",
        resume_text=SEVEN_TURN_RESUME,
    ),
    _entry(
        "mixed-language-rag",
        category="mixed_language",
        question="Tell me about your RAG project，为什么这么设计？",
        expected_question_type="EXPERIENCE",
        expected_route="EXPERIENCE_KNOWLEDGE",
        resume_text=SEVEN_TURN_RESUME,
    ),
    _entry(
        "topic-reset-os",
        category="topic_reset",
        question="讲讲操作系统内核。",
        expected_question_type="KNOWLEDGE",
        expected_route="KNOWLEDGE",
        resume_text=SEVEN_TURN_RESUME,
        dialogue_history=[
            {"question": "介绍一下你的项目。", "answer": "我们做了 RAG + Agent 问答系统。"},
            {"question": "为什么选 RAG？", "answer": "因为数据持续更新，检索可追溯。"},
            {"question": "换个话题，讲讲操作系统？", "answer": "好的，请问想了解哪个部分？"},
        ],
    ),
    _entry(
        "long-session-accumulation",
        category="long_session",
        question="那这个最后怎么验证？",
        expected_question_type="FOLLOW_UP",
        expected_route="EXPERIENCE_KNOWLEDGE",
        resume_text=SEVEN_TURN_RESUME,
        dialogue_history=[
            {"question": "介绍一下你的项目。", "answer": "我们做了 RAG 问答系统。"},
            {"question": "为什么选 RAG？", "answer": "数据持续更新。"},
            {"question": "检索用什么方案？", "answer": "混合检索，FTS 加语义。"},
            {"question": "rerank 呢？", "answer": "用了轻量 reranker。"},
            {"question": "延迟多少？", "answer": "P50 300ms 以内。"},
            {"question": "成本呢？", "answer": "主要是模型调用成本。"},
            {"question": "如果流量扩大呢？", "answer": "先测瓶颈，再考虑分片。"},
            {"question": "那缓存会有什么问题？", "answer": "缓存一致性需要处理。"},
        ],
    ),
]
