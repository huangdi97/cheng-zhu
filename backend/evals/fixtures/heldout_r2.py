"""R2 held-out routing set.

Written on 2026-09-30 BEFORE running the R2 router against it, and kept
separate from interview_fixtures.py (the train/dev set the router was
developed against). Do not tune semantics.route_answer against these cases;
if a case fails, report it. Adding cases is fine; editing expectations to make
the router pass is not.

Each case: question, resume (profile held in the pack), previous question
(for follow-ups), expected response mode.
"""
from __future__ import annotations

HELDOUT_RESUME = (
    "某电商公司 后端工程师 2021-2024\n"
    "负责订单服务重构，使用 Go 和 PostgreSQL，引入 Kafka 做异步解耦\n"
    "搭建内部 RAG 知识库问答，使用 Elasticsearch 做检索\n"
    "带领 3 人小组完成支付对账系统\n"
    "技能：熟悉 Kubernetes，了解 Flink"
)

HELDOUT_CASES: list[dict] = [
    # --- knowledge (zh / en / mixed) ---
    {"id": "h01", "question": "TCP 三次握手为什么不是两次？", "expected": "KNOWLEDGE"},
    {"id": "h02", "question": "Explain the difference between a process and a thread.", "expected": "KNOWLEDGE"},
    {"id": "h03", "question": "B+ 树为什么适合做数据库索引？", "expected": "KNOWLEDGE"},
    {"id": "h04", "question": "What is eventual consistency?", "expected": "KNOWLEDGE"},
    {"id": "h05", "question": "Kafka 的 ISR 机制是怎么保证不丢消息的？", "expected": "KNOWLEDGE"},
    # --- coding ---
    {"id": "h06", "question": "写一个函数判断链表是否有环", "expected": "CODING"},
    {"id": "h07", "question": "Implement an LRU cache, what's the complexity?", "expected": "CODING"},
    # --- system design (classic) ---
    {"id": "h08", "question": "设计一个短链接服务，需要支持每天一亿次访问", "expected": "SYSTEM_DESIGN"},
    {"id": "h09", "question": "Design a rate limiter for a public API.", "expected": "SYSTEM_DESIGN"},
    # --- hypothetical / open design ---
    {"id": "h10", "question": "如果订单量突然涨十倍，你的系统哪里会先扛不住？", "expected": "HYPOTHETICAL"},
    {"id": "h11", "question": "假设让你把对账系统迁到云上，你会怎么落地？", "expected": "OPEN_DESIGN"},
    # --- personal: evidence exists ---
    {"id": "h12", "question": "讲讲你做的订单服务重构", "expected": "EXPERIENCE"},
    {"id": "h13", "question": "你在支付对账系统里具体负责什么？", "expected": "EXPERIENCE"},
    {"id": "h14", "question": "Tell me about the RAG knowledge base you built.", "expected": "EXPERIENCE"},
    # --- personal: project deep dive / rationale ---
    {"id": "h15", "question": "订单服务为什么选 PostgreSQL 而不是 MySQL？", "expected": "EXPERIENCE_KNOWLEDGE"},
    {"id": "h16", "question": "为什么不用 RabbitMQ？", "previous": "讲讲你做的订单服务重构", "expected": "EXPERIENCE_KNOWLEDGE"},
    # --- personal: no evidence -> boundary ---
    {"id": "h17", "question": "你用过 Redis Cluster 吗？", "expected": "EXPERIENCE_BOUNDARY_KNOWLEDGE"},
    {"id": "h18", "question": "你在生产环境部署过 Flink 作业吗？", "expected": "EXPERIENCE_BOUNDARY_KNOWLEDGE"},
    {"id": "h19", "question": "Have you used Terraform in production?", "expected": "EXPERIENCE_BOUNDARY_KNOWLEDGE"},
    # --- behavioral / role fit ---
    {"id": "h20", "question": "讲一次你和同事意见不一致的经历", "expected": "BEHAVIORAL"},
    {"id": "h21", "question": "为什么想加入我们公司？", "expected": "BEHAVIORAL"},
    # --- negotiation ---
    {"id": "h22", "question": "你的期望薪资是多少？", "expected": "NEGOTIATION"},
    # --- product / case ---
    {"id": "h23", "question": "如果要提升 App 的次日留存，你会怎么分析？", "expected": "PRODUCT_CASE"},
    # --- OOD ---
    {"id": "h24", "question": "用面向对象设计一个停车场系统", "expected": "OOD"},
    # --- follow-ups naming a new subject (knowledge) ---
    {"id": "h25", "question": "那 Elasticsearch 的倒排索引是怎么工作的？", "previous": "讲讲你的 RAG 知识库", "expected": "KNOWLEDGE"},
    # --- follow-up pointing back to the project ---
    {"id": "h26", "question": "这个最后是怎么上线验证的？", "previous": "讲讲你做的订单服务重构", "expected": "EXPERIENCE_KNOWLEDGE"},
    # --- ASR typo / noisy ---
    {"id": "h27", "question": "卡夫卡的消费者组 rebalance 是什么", "expected": "KNOWLEDGE"},
    # --- self intro ---
    {"id": "h28", "question": "先做个自我介绍吧", "expected": "EXPERIENCE"},
]


# ---------------------------------------------------------------------------
# Held-out v2 — written 2026-09-30 AFTER v1 exposed classifier gaps and BEFORE
# the category-level classifier fix was run against anything. v1 results stay
# frozen in evals/reports/heldout_r2_v1_result.json. v2 is the honest
# post-fix measurement; do not tune against it either.
# ---------------------------------------------------------------------------

HELDOUT_V2_CASES: list[dict] = [
    {"id": "v2-01", "question": "HTTP/2 相比 HTTP/1.1 解决了什么问题？", "expected": "KNOWLEDGE"},
    {"id": "v2-02", "question": "What happens when you type a URL into the browser?", "expected": "KNOWLEDGE"},
    {"id": "v2-03", "question": "MVCC 在 PostgreSQL 里是怎么实现的？", "expected": "KNOWLEDGE"},
    {"id": "v2-04", "question": "手写一个二分查找", "expected": "CODING"},
    {"id": "v2-05", "question": "Write a function to merge two sorted arrays.", "expected": "CODING"},
    {"id": "v2-06", "question": "设计一个支持千万用户的消息推送系统", "expected": "SYSTEM_DESIGN"},
    {"id": "v2-07", "question": "How would you design a distributed job scheduler?", "expected": "SYSTEM_DESIGN"},
    {"id": "v2-08", "question": "如果 Kafka 集群挂了一个 broker 会怎样？", "expected": "HYPOTHETICAL"},
    {"id": "v2-09", "question": "介绍一下你做的 RAG 知识库", "expected": "EXPERIENCE"},
    {"id": "v2-10", "question": "你们订单服务重构的时候遇到过什么难点？", "expected": "EXPERIENCE"},
    {"id": "v2-11", "question": "What was your role in the payment reconciliation project?", "expected": "EXPERIENCE"},
    {"id": "v2-12", "question": "对账系统为什么用 Go 写？", "expected": "EXPERIENCE_KNOWLEDGE"},
    {"id": "v2-13", "question": "你用过 ClickHouse 吗？", "expected": "EXPERIENCE_BOUNDARY_KNOWLEDGE"},
    {"id": "v2-14", "question": "Did you use gRPC in production?", "expected": "EXPERIENCE_BOUNDARY_KNOWLEDGE"},
    {"id": "v2-15", "question": "说一次你推动跨团队合作的经历", "expected": "BEHAVIORAL"},
    {"id": "v2-16", "question": "Tell me about a time you failed.", "expected": "BEHAVIORAL"},
    {"id": "v2-17", "question": "你为什么想换工作？", "expected": "BEHAVIORAL"},
    {"id": "v2-18", "question": "期望的薪资范围大概是多少？", "expected": "NEGOTIATION"},
    {"id": "v2-19", "question": "怎么提高电商详情页的转化率？", "expected": "PRODUCT_CASE"},
    {"id": "v2-20", "question": "面向对象设计一个电梯调度系统", "expected": "OOD"},
    {"id": "v2-21", "question": "那 Go 的 GMP 调度模型是怎么回事？", "previous": "对账系统为什么用 Go 写？", "expected": "KNOWLEDGE"},
    {"id": "v2-22", "question": "这个方案后来效果怎么样？", "previous": "介绍一下你做的 RAG 知识库", "expected": "EXPERIENCE_KNOWLEDGE"},
    {"id": "v2-23", "question": "请简单介绍一下自己", "expected": "EXPERIENCE"},
    {"id": "v2-24", "question": "Redis 为什么是单线程还这么快？", "expected": "KNOWLEDGE"},
]
