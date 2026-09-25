"""准备空间 LLM 服务：岗位对齐洞察 / 项目技能卡 / 预测真题。

复用 review 模块的模型客户端（当前启用模型），所有 prompt 均要求模型
只依据「用户提供的简历 + JD」输出，不做编造；返回 JSON 便于前端渲染。
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.config import get_config
from core.logger import get_logger
from services.review_analysis import get_active_llm_client, _review_chat_kwargs

logger = get_logger("prep.service")

_MAX_TEXT = 30000


def _trim(text: str, limit: int = _MAX_TEXT) -> str:
    return (text or "")[:limit]


def prep_configured() -> bool:
    """当前是否配置了可用的 LLM 模型（含有效 API Key）。"""
    cfg = get_config()
    model = cfg.get_review_model()
    key = (model.api_key or "").strip()
    return bool(key) and key not in ("", "sk-your-api-key-here", "YOUR_API_KEY_HERE")


def _extract_json(content: str) -> Any:
    text = (content or "").strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
        if match:
            text = match.group(1).strip()
    return json.loads(text)


def _chat_json(system: str, prompt: str, max_tokens: int = 1600) -> Any:
    client, model_name = get_active_llm_client()
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        **_review_chat_kwargs(max_tokens),
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError("模型返回为空")
    return _extract_json(content)


# ---------------------------------------------------------------------------
# 岗位对齐洞察
# ---------------------------------------------------------------------------

_INSIGHT_SYSTEM = (
    "你是求职辅导教练，负责把「岗位 JD」和「候选人简历」放在一起做对齐分析。"
    "只依据给定材料输出，不编造简历里没有的经历；中文输出。"
)


def build_insight_prompt(role: str, company: str, jd_text: str, resume_text: str) -> str:
    return f"""请对下面的岗位和简历做「岗位对齐洞察」，帮助候选人判断该重点准备什么。

目标岗位：{role or '（未填写）'}
目标公司：{company or '（未填写）'}

岗位 JD：
{_trim(jd_text) or '（未提供 JD）'}

候选人简历：
{_trim(resume_text) or '（未提供简历）'}

请输出 JSON，结构如下：
{{
  "markdown": "### 岗位考察重点\\n- ...\\n\\n### 你的匹配亮点\\n- ...\\n\\n### 主要差距/风险\\n- ...\\n\\n### 建议重点准备\\n1. ...",
  "focus_points": ["考察点1", "考察点2", "考察点3"],
  "strengths": ["简历中的匹配亮点1", "..."],
  "gaps": ["短板/风险1", "..."]
}}
要求：
- markdown 用中文，简明可执行，长度 300-600 字
- focus_points / strengths / gaps 各 3-6 条，每条 20 字以内
- 不要编造简历中不存在的经历；JD 未提供时基于岗位名推断通用考察点
"""


def generate_insight(role: str, company: str, jd_text: str, resume_text: str) -> dict[str, Any]:
    result = _chat_json(
        _INSIGHT_SYSTEM,
        build_insight_prompt(role, company, jd_text, resume_text),
        max_tokens=1600,
    )
    if not isinstance(result, dict):
        raise ValueError("洞察返回格式异常")
    return {
        "markdown": str(result.get("markdown") or "").strip(),
        "focus_points": [str(x) for x in result.get("focus_points", [])][:8],
        "strengths": [str(x) for x in result.get("strengths", [])][:8],
        "gaps": [str(x) for x in result.get("gaps", [])][:8],
    }


# ---------------------------------------------------------------------------
# 项目技能卡
# ---------------------------------------------------------------------------

_SKILL_SYSTEM = (
    "你是资深技术面试陪练。把候选人简历里的项目经历提炼成结构化的「项目技能卡」，"
    "供候选人面试前复习；只依据简历输出，不编造事实；中文输出。"
)


def build_skill_card_prompt(role: str, jd_text: str, resume_text: str) -> str:
    return f"""请从下面的简历中提取「项目经历」，为每个项目生成一张技能卡。

目标岗位：{role or '（未填写）'}
岗位 JD（用于判断追问角度）：
{_trim(jd_text) or '（未提供 JD）'}

候选人简历：
{_trim(resume_text) or '（未提供简历，请基于岗位 JD 建议候选人在准备空间补充项目）'}

请输出 JSON：{{ "projects": [ ... ] }}
每个项目结构如下：
{{
  "name": "项目名称",
  "background": "项目背景/要解决的问题（1-2 句）",
  "my_role": "我在项目中的角色与职责",
  "tech_decisions": ["关键技术决策1", "..."],
  "metrics": ["可量化的结果/指标1", "..."],
  "tradeoffs": ["取舍/踩坑1", "..."],
  "likely_follow_ups": ["面试官可能追问的问题1", "..."]
}}
要求：
- 只使用简历中出现的项目；简历里没有项目时输出空数组
- 每张卡 5-9 个字段值，每个字段值 1 句话
- 简历没写清的地方，用 likely_follow_ups 提示候选人去补齐，不要编造
"""


def generate_skill_cards(role: str, jd_text: str, resume_text: str) -> list[dict[str, Any]]:
    result = _chat_json(
        _SKILL_SYSTEM,
        build_skill_card_prompt(role, jd_text, resume_text),
        max_tokens=2400,
    )
    projects = result.get("projects", []) if isinstance(result, dict) else []
    if not isinstance(projects, list):
        raise ValueError("技能卡返回格式异常")
    cards = []
    for p in projects[:10]:
        if not isinstance(p, dict) or not str(p.get("name") or "").strip():
            continue
        cards.append({
            "name": str(p.get("name") or "").strip()[:120],
            "background": str(p.get("background") or "").strip(),
            "my_role": str(p.get("my_role") or "").strip(),
            "tech_decisions": [str(x) for x in p.get("tech_decisions", [])][:6],
            "metrics": [str(x) for x in p.get("metrics", [])][:6],
            "tradeoffs": [str(x) for x in p.get("tradeoffs", [])][:6],
            "likely_follow_ups": [str(x) for x in p.get("likely_follow_ups", [])][:6],
        })
    return cards


def build_launch_pack(space: dict[str, Any]) -> dict[str, Any]:
    """Build a concise, evidence-bound briefing from an existing prep space."""
    skill_cards = list(space.get("skill_cards") or [])
    questions = list(space.get("questions") or [])
    project_anchors: list[dict[str, Any]] = []
    risk_prompts: list[str] = []
    for item in skill_cards[:6]:
        card = item.get("card") if isinstance(item, dict) else {}
        if not isinstance(card, dict):
            card = {}
        name = str(card.get("name") or item.get("project_name") or "未命名项目").strip()
        anchors = [
            str(card.get("background") or "").strip(),
            str(card.get("my_role") or "").strip(),
            *[str(v).strip() for v in (card.get("tech_decisions") or [])[:3]],
            *[str(v).strip() for v in (card.get("metrics") or [])[:2]],
        ]
        anchors = [value for value in anchors if value]
        followups = [str(v).strip() for v in (card.get("likely_follow_ups") or [])[:4] if str(v).strip()]
        risk_prompts.extend(followups)
        project_anchors.append({"name": name, "anchors": anchors[:6], "likely_followups": followups})

    question_groups: dict[str, list[str]] = {}
    for question in questions[:15]:
        if not isinstance(question, dict):
            continue
        q_text = str(question.get("question") or "").strip()
        if not q_text:
            continue
        q_type = str(question.get("type") or "general").strip() or "general"
        question_groups.setdefault(q_type, []).append(q_text)

    insight_lines = [
        line.strip().lstrip("-*># ").strip()
        for line in str(space.get("insight_markdown") or "").splitlines()
        if line.strip().lstrip("-*># ").strip()
    ]
    return {
        "space_id": int(space.get("id") or 0),
        "title": str(space.get("title") or "本场面试"),
        "role": str(space.get("role") or ""),
        "company": str(space.get("company") or ""),
        "briefing": insight_lines[:8],
        "project_anchors": project_anchors,
        "question_groups": question_groups,
        "risk_prompts": list(dict.fromkeys(risk_prompts))[:8],
        "readiness": {
            "has_jd": bool(str(space.get("jd_text") or "").strip()),
            "has_resume": bool(str(space.get("resume_text") or "").strip()),
            "project_count": len(project_anchors),
            "question_count": sum(len(values) for values in question_groups.values()),
        },
    }


# ---------------------------------------------------------------------------
# 预测真题
# ---------------------------------------------------------------------------

_QUESTION_SYSTEM = (
    "你是资深面试官。根据岗位 JD、候选人简历、项目技能卡，预测这场面试最可能被问到的问题。"
    "中文输出，只依据给定材料，不编造。"
)


def build_questions_prompt(
    role: str,
    company: str,
    jd_text: str,
    resume_text: str,
    insight_markdown: str,
    skill_cards: list[dict[str, Any]],
) -> str:
    cards_text = ""
    for idx, c in enumerate(skill_cards, 1):
        cards_text += (
            f"{idx}. {c.get('name')}：背景={c.get('background')}；角色={c.get('my_role')}；"
            f"决策={c.get('tech_decisions')}；指标={c.get('metrics')}；取舍={c.get('tradeoffs')}\n"
        )
    return f"""请为下面的面试预测 10-15 道最可能被问到的问题。

目标岗位：{role or '（未填写）'}
目标公司：{company or '（未填写）'}

岗位 JD：
{_trim(jd_text) or '（未提供 JD）'}

候选人简历：
{_trim(resume_text) or '（未提供简历）'}

岗位对齐洞察（简要）：
{_trim(insight_markdown, 4000) or '（未生成）'}

项目技能卡：
{cards_text or '（未生成）'}

请输出 JSON：{{ "questions": [ ... ] }}
每个问题结构如下：
{{
  "question": "问题全文",
  "type": "behavioral | technical | project | scenario | hr",
  "why": "为什么会被问/考察什么（一句话）"
}}
要求：
- 10-15 道，覆盖：项目深挖（基于技能卡）、岗位技术、行为/STAR、场景题、HR 常见
- 问题要具体、可直接拿来练习，不要空泛
"""


def generate_questions(
    role: str,
    company: str,
    jd_text: str,
    resume_text: str,
    insight_markdown: str,
    skill_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = _chat_json(
        _QUESTION_SYSTEM,
        build_questions_prompt(role, company, jd_text, resume_text, insight_markdown, skill_cards),
        max_tokens=2000,
    )
    questions = result.get("questions", []) if isinstance(result, dict) else []
    if not isinstance(questions, list):
        raise ValueError("预测真题返回格式异常")
    cleaned = []
    for q in questions[:15]:
        if not isinstance(q, dict) or not str(q.get("question") or "").strip():
            continue
        cleaned.append({
            "question": str(q.get("question") or "").strip(),
            "type": str(q.get("type") or "technical").strip()[:20],
            "why": str(q.get("why") or "").strip(),
        })
    return cleaned
