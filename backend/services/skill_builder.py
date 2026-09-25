"""交互式项目技能卡工作台：AI 像面试官一样逐条追问项目，用户回答后整理成技能卡。

成竹的「技能卡沉淀」不是从简历一次性抽取，而是通过问答把
背景 / 角色 / 技术决策 / 量化结果 / 取舍 / 可能追问 逐项补齐并确认，
答不上来的会留在「待补齐」里。
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Optional

from core.logger import get_logger
from services.prep_service import _chat_json
from services.storage import prep_space as prep_storage

logger = get_logger("skill_builder")

_LOCK = threading.Lock()
_SESSIONS: dict[str, dict[str, Any]] = {}

PROJECT_QUESTION_COUNT = 6


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _extract_projects(resume_text: str) -> list[str]:
    result = _chat_json(
        "你是简历解析助手，只输出 JSON。",
        f"""请从下面的简历中提取「项目经历」的名称列表（每个项目一句话以内的名称）。
简历：
{resume_text[:20000]}

只输出 JSON：{{"projects": ["项目1", "项目2", ...]}}
如果简历里没有任何项目，输出 {{"projects": []}}。""",
        max_tokens=800,
    )
    projects = result.get("projects", []) if isinstance(result, dict) else []
    return [str(p).strip() for p in projects if str(p).strip()][:8]


def _question_plan(project: str, resume_text: str) -> list[str]:
    result = _chat_json(
        "你是资深技术面试官，负责针对候选人的项目设计追问清单，只输出 JSON。",
        f"""针对下面这个项目，设计 {PROJECT_QUESTION_COUNT} 条追问，帮助候选人把项目讲清楚。
要求覆盖：项目背景与要解决的问题、我的角色与职责、关键技术决策、量化结果、取舍/踩坑、面试官可能深挖的角度。
问题要具体、能回答、不空泛；一次只问一件事。

项目：{project}

候选人简历（节选）：
{resume_text[:20000]}

只输出 JSON：{{"questions": ["问题1", "问题2", ...]}}""",
        max_tokens=1200,
    )
    questions = result.get("questions", []) if isinstance(result, dict) else []
    return [str(q).strip() for q in questions if str(q).strip()][:PROJECT_QUESTION_COUNT]


def _finalize_card(project: str, qa: list[dict[str, str]], resume_text: str) -> dict[str, Any]:
    qa_text = "\n".join(
        f"问：{item.get('question', '')}\n答：{item.get('answer', '')}" for item in qa
    )
    result = _chat_json(
        "你是求职辅导教练，把问答整理成结构化的项目技能卡，只输出 JSON。",
        f"""把下面的项目问答整理成一张「项目技能卡」。
要求：只使用问答里出现的内容，不要编造；用户没答上来的维度，用空数组并在
likely_follow_ups 里提示"待补齐"。

项目：{project}

问答记录：
{qa_text or '（无问答，仅按简历）'}

简历（节选）：
{resume_text[:12000]}

输出 JSON：
{{
  "name": "项目名称",
  "background": "项目背景/要解决的问题",
  "my_role": "我的角色与职责",
  "tech_decisions": ["决策1", "..."],
  "metrics": ["量化结果1", "..."],
  "tradeoffs": ["取舍/踩坑1", "..."],
  "likely_follow_ups": ["面试官可能追问1（含待补齐项）", "..."]
}}""",
        max_tokens=1600,
    )
    if not isinstance(result, dict):
        raise ValueError("技能卡整理失败：返回格式异常")
    return {
        "name": str(result.get("name") or project).strip()[:120],
        "background": str(result.get("background") or "").strip(),
        "my_role": str(result.get("my_role") or "").strip(),
        "tech_decisions": [str(x) for x in result.get("tech_decisions", [])][:6],
        "metrics": [str(x) for x in result.get("metrics", [])][:6],
        "tradeoffs": [str(x) for x in result.get("tradeoffs", [])][:6],
        "likely_follow_ups": [str(x) for x in result.get("likely_follow_ups", [])][:6],
    }


def _start_project(session: dict[str, Any]) -> Optional[dict[str, Any]]:
    if session["project_index"] >= len(session["projects"]):
        return None
    project = session["projects"][session["project_index"]]
    questions = _question_plan(project, session["resume_text"])
    if not questions:
        questions = [
            f"请介绍一下「{project}」这个项目：背景、要解决的问题、你在其中的角色。",
            "这个项目里你做了哪些关键技术决策？为什么？",
            "有没有可量化的结果或指标？",
            "遇到过什么取舍或踩坑？",
            "如果面试官深挖，最可能问你什么？",
        ]
    session["current_project"] = project
    session["plan"] = questions
    session["plan_index"] = 0
    session["qa"] = []
    return {
        "project": project,
        "project_index": session["project_index"],
        "project_total": len(session["projects"]),
        "question": questions[0],
        "question_index": 1,
        "question_total": len(questions),
    }


def start_session(space_id: int) -> dict[str, Any]:
    space = prep_storage.get_space(space_id)
    if not space:
        raise ValueError("准备空间不存在")
    resume_text = (space.get("resume_text") or "").strip()
    if len(resume_text) < 20:
        raise ValueError("准备空间里还没有简历正文，请先在准备空间填写简历后再开始技能卡")
    projects = _extract_projects(resume_text)
    if not projects:
        raise ValueError("没有从简历里识别到项目，请补充项目经历后重试")
    session: dict[str, Any] = {
        "id": _new_id(),
        "space_id": space_id,
        "resume_text": resume_text,
        "projects": projects,
        "project_index": 0,
        "current_project": None,
        "plan": [],
        "plan_index": 0,
        "qa": [],
        "status": "active",
        "created_at": time.time(),
    }
    first = _start_project(session)
    with _LOCK:
        _SESSIONS[session["id"]] = session
    return {"builder_id": session["id"], **first}


def get_session(builder_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        return _SESSIONS.get(builder_id)


def _finalize_current(session: dict[str, Any]) -> dict[str, Any]:
    card = _finalize_card(session["current_project"], session["qa"], session["resume_text"])
    card_id = prep_storage.add_skill_card(session["space_id"], card.get("name") or session["current_project"])
    prep_storage.update_skill_card(card_id, card, "done")
    logger.info("skill card saved for %s (card_id=%s)", session["current_project"], card_id)
    return card


def answer(builder_id: str, text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("回答不能为空")
    session = get_session(builder_id)
    if not session or session["status"] != "active":
        raise ValueError("工作台会话不存在或已结束")
    q = session["plan"][session["plan_index"]]
    session["qa"].append({"question": q, "answer": text})
    session["plan_index"] += 1
    answered_total = session["plan_index"]

    if answered_total < len(session["plan"]):
        return {
            "done": False,
            "project": session["current_project"],
            "project_index": session["project_index"],
            "project_total": len(session["projects"]),
            "question": session["plan"][session["plan_index"]],
            "question_index": session["plan_index"] + 1,
            "question_total": len(session["plan"]),
        }

    # 当前项目问完 -> 整理成卡 -> 下一个项目
    card = _finalize_current(session)
    session["project_index"] += 1
    next_state = _start_project(session)
    if next_state is None:
        session["status"] = "finished"
        return {"done": True, "card_saved": card, "project_done": session["current_project"]}
    return {"done": False, "card_saved": card, "project_done": session["current_project"], **next_state}


def skip(builder_id: str) -> dict[str, Any]:
    """跳过当前项目剩余追问，按已答内容整理技能卡。"""
    session = get_session(builder_id)
    if not session or session["status"] != "active":
        raise ValueError("工作台会话不存在或已结束")
    card = _finalize_current(session)
    session["project_index"] += 1
    next_state = _start_project(session)
    if next_state is None:
        session["status"] = "finished"
        return {"done": True, "card_saved": card, "project_done": session["current_project"]}
    return {"done": False, "card_saved": card, "project_done": session["current_project"], **next_state}
