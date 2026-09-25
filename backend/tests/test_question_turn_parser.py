from __future__ import annotations

from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.question_turn_parser import parse_question_turn  # noqa: E402


def test_long_project_prompt_becomes_one_cluster_with_subquestions():
    parsed = parse_question_turn([
        "你先介绍项目背景。当时为什么要重构？你具体负责什么？最后效果怎么样？"
    ])

    assert len(parsed.clusters) == 1
    cluster = parsed.clusters[0]
    assert cluster.primary_question == "你先介绍项目背景"
    assert cluster.subquestions == ["当时为什么要重构", "你具体负责什么", "最后效果怎么样"]
    assert cluster.question_type == "project"


def test_explicit_topic_switch_creates_independent_answer_tasks():
    parsed = parse_question_turn([
        "Redis 为什么快？另外说一下 Java 线程池参数怎么配置？"
    ])

    assert len(parsed.clusters) == 2
    assert parsed.clusters[0].question_type == "technical"
    assert "线程池" in parsed.clusters[1].primary_question


def test_constraint_is_attached_instead_of_becoming_question():
    parsed = parse_question_turn([
        "rules 和 skills 的区别是什么？不要结合项目，只讲核心原理。"
    ])

    assert len(parsed.clusters) == 1
    assert parsed.clusters[0].constraints == ["不要结合项目，只讲核心原理"]


def test_rephrase_replaces_primary_question():
    parsed = parse_question_turn([
        "怎么保证一致性？我是说缓存和数据库的一致性。"
    ])

    assert len(parsed.clusters) == 1
    assert parsed.clusters[0].primary_question == "缓存和数据库的一致性"


def test_context_statement_is_preserved_for_the_question():
    parsed = parse_question_turn([
        "我们线上日订单量比较大，之前还出现过超卖。你们怎么解决库存一致性问题？"
    ])

    assert len(parsed.clusters) == 1
    assert parsed.clusters[0].context
    assert "库存一致性" in parsed.clusters[0].primary_question


def test_same_topic_questions_become_subquestions_not_independent_tasks():
    parsed = parse_question_turn([
        "Redis 为什么快？它有哪些数据结构？项目里怎么使用的？"
    ])

    assert len(parsed.clusters) == 1
    assert len(parsed.clusters[0].subquestions) == 2
