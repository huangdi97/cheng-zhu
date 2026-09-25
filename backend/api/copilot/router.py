"""Copilot 策略树 API：生成/读取/激活，供实时辅助在面试中预测追问与高危点。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import get_config
from services.storage import prep_space
from services import copilot_strategy
from core.session import get_session

router = APIRouter()


class StrategyGenRequest(BaseModel):
    space_id: int | None = None
    role: str = ""
    jd_text: str = ""
    resume_text: str = ""


class ActivateRequest(BaseModel):
    space_id: int | None = None


@router.post("/copilot/strategy-tree")
async def api_generate_strategy_tree(req: StrategyGenRequest):
    """基于 JD/简历生成提问策略树并激活。"""
    role = (req.role or "").strip()
    jd_text = (req.jd_text or "").strip()
    resume_text = (req.resume_text or "").strip()
    questions = None

    if req.space_id is not None:
        space = prep_space.get_space(int(req.space_id))
        if space:
            role = role or (space.get("role") or "")
            jd_text = jd_text or (space.get("jd_text") or "")
            resume_text = resume_text or (space.get("resume_text") or "")
            questions = space.get("questions") or None

    if not (jd_text or resume_text):
        cfg = get_config()
        jd_text = jd_text or (cfg.jd_text or "")
        resume_text = resume_text or (cfg.resume_text or "")
        role = role or cfg.position
    if not (jd_text or resume_text):
        raise HTTPException(400, "请先填写 JD 或简历（可在「面试准备」页或设置中填写）")

    try:
        tree = copilot_strategy.generate_strategy_tree(role, jd_text, resume_text, questions)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"策略树生成失败: {e}")

    space_id = int(req.space_id) if req.space_id is not None else None
    copilot_strategy.save_tree(tree, space_id)
    copilot_strategy.activate_tree(space_id, get_session().session_id)
    return {"ok": True, "space_id": space_id, "tree": tree}


@router.get("/copilot/strategy-tree")
async def api_get_strategy_tree(space_id: int | None = None):
    """读取策略树（默认读取当前已激活的）。"""
    session_id = get_session().session_id
    tree = copilot_strategy.load_tree(space_id) if space_id is not None else copilot_strategy.get_active_tree(session_id)
    return {"tree": tree, "active_space_id": copilot_strategy.get_active_space_id(session_id)}


@router.post("/copilot/strategy-tree/activate")
async def api_activate_strategy_tree(req: ActivateRequest):
    """激活某个空间已生成的策略树（面试开始前调用）。"""
    tree = copilot_strategy.activate_tree(req.space_id, get_session().session_id)
    if tree is None:
        raise HTTPException(404, "该空间还没有策略树，请先生成")
    return {"ok": True, "tree": tree}
