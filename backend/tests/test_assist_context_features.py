# -*- coding: utf-8 -*-
"""New context features: JD/notes/memo injection, answer language, prefix warmup,
memo endpoint, review export builder."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.session import Session
from services.llm.prompts import (
    PROMPT_MODE_ASR_REALTIME,
    PROMPT_MODE_WRITTEN_EXAM,
    build_system_prompt,
)
from services.llm.streaming import warmup_prefix_cache


def _cfg_with(**overrides):
    from core.config import AppConfig

    data = AppConfig().model_dump()
    data.update(overrides)
    return AppConfig(**data)


class _FakeModel:
    name = "fake"
    api_key = "sk-test"
    api_base_url = "https://example.invalid/v1"
    model = "fake-model"


def test_session_manual_memo_injected_into_llm_messages():
    s = Session()
    s.memo_manual = "要强调支付项目的降级方案"
    s.system_summary = "- 问过 Redis"
    msgs = s.get_conversation_messages_for_llm()
    assert msgs and msgs[0]["role"] == "system"
    assert "手动记录的面试备忘" in msgs[0]["content"]
    assert "要强调支付项目的降级方案" in msgs[0]["content"]
    assert "滚动摘要" in msgs[0]["content"]
    snap = s.snapshot()
    assert snap["memo_manual"] == "要强调支付项目的降级方案"
    assert snap["system_summary"] == "- 问过 Redis"


def test_build_system_prompt_includes_jd_notes_memo_and_language(monkeypatch):
    from core.config import get_config

    cfg = get_config()
    monkeypatch.setattr(cfg, "jd_text", "要求：熟悉 Redis 与高并发")
    monkeypatch.setattr(cfg, "interview_notes", "我想强调支付项目降级")
    monkeypatch.setattr(cfg, "answer_language", "English")
    monkeypatch.setattr(cfg, "assist_answer_align_jd_enabled", True)

    prompt = build_system_prompt(
        mode=PROMPT_MODE_ASR_REALTIME,
        memo_context="## 已问过的问题\n- Redis 缓存一致性",
    )
    assert "<jd_context>" in prompt
    assert "<notes>" in prompt
    assert "<memo_context>" in prompt
    assert "请用英文回答" in prompt
    assert "回答贴合 JD 规则" in prompt


def test_build_system_prompt_skips_context_for_written_exam(monkeypatch):
    from core.config import get_config

    cfg = get_config()
    monkeypatch.setattr(cfg, "jd_text", "要求：熟悉 Redis")
    monkeypatch.setattr(cfg, "interview_notes", "备注")
    prompt = build_system_prompt(mode=PROMPT_MODE_WRITTEN_EXAM, memo_context="memo")
    assert "<jd_context>" not in prompt
    assert "<notes>" not in prompt
    assert "<memo_context>" not in prompt


def test_warmup_disabled_returns_skipped(monkeypatch):
    from core.config import get_config

    cfg = get_config()
    monkeypatch.setattr(cfg, "assist_prefix_cache_warmup_enabled", False)
    result = warmup_prefix_cache(
        [{"role": "system", "content": "x"}],
        model_cfg=_FakeModel(),
        timeout_s=1,
    )
    assert result["ok"] is False
    assert result["skipped"] == "disabled"


def test_warmup_empty_messages_skipped(monkeypatch):
    from core.config import get_config

    cfg = get_config()
    monkeypatch.setattr(cfg, "assist_prefix_cache_warmup_enabled", True)
    result = warmup_prefix_cache([], model_cfg=_FakeModel(), timeout_s=1)
    assert result["ok"] is False
    assert result["skipped"] == "empty"


def test_memo_endpoint_updates_and_broadcasts(monkeypatch):
    from api.assist.routes import api_update_memo, MemoUpdateRequest
    from core.session import get_session, reset_session

    reset_session()
    broadcasted = []

    monkeypatch.setattr("api.realtime.ws.broadcast", lambda data: broadcasted.append(data))
    import asyncio

    res = asyncio.run(api_update_memo(MemoUpdateRequest(text="手动备忘内容")))
    assert res == {"ok": True}
    assert get_session().memo_manual == "手动备忘内容"
    assert broadcasted and broadcasted[0]["type"] == "memo_update"
    assert broadcasted[0]["memo_manual"] == "手动备忘内容"


def test_review_markdown_export_builder():
    from api.review.router import _build_review_markdown

    detail = {
        "title": "腾讯一面",
        "company": "腾讯",
        "role": "后端",
        "status": "completed",
        "summary_markdown": "## 整体\n表现不错",
        "strong_points": ["表达清晰"],
        "weak_points": ["深度不够"],
        "turns": [
            {
                "question_text": "讲一下 Redis 持久化",
                "candidate_answer_text": "RDB 和 AOF",
                "corrected_answer": "RDB 快照 + AOF 追加日志",
                "strengths": ["结构完整"],
                "risks": ["缺少取舍"],
                "evidence": {"例子": "线上 1 秒丢数据"},
                "scorecard": {"技术深度": 7},
            }
        ],
    }
    md = _build_review_markdown(detail)
    assert "# 腾讯一面" in md
    assert "## 整体复盘" in md
    assert "讲一下 Redis 持久化" in md
    assert "RDB 快照 + AOF 追加日志" in md
    assert "技术深度: 7" in md
