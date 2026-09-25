"""Copilot 策略树：面试前用 JD/简历生成提问策略树，面试中实时匹配问题并预测追问/高危点。

对标 TechSpar 的 copilot_prep / strategy_tree / intent_classifier：
- 生成：LLM 输出 {root_nodes, nodes[{id,label,intent,sample_questions,children,high_risk,risk_advice,advice}]}
- 匹配：字符 bigram 相似度（无需 embedding 服务），低置信度 + 上一轮节点 -> 视为追问沿用
- 存储：backend/data/copilot_strategy/{space_id or active}.json
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from types import SimpleNamespace
from typing import Any, Optional

from core.config import get_config
from core.logger import get_logger
from services.llm.streaming import (
    _build_think_params,
    _completion_token_kwargs,
    get_client_for_model,
)

_log = get_logger("copilot.strategy")

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "copilot_strategy")

_active_trees: dict[str, Optional[dict]] = {}
_active_space_ids: dict[str, Optional[int]] = {}
_current_node_ids: dict[str, Optional[str]] = {}
_lock = threading.Lock()


def _session_key(session_id: Optional[str]) -> str:
    return (session_id or "__default__").strip() or "__default__"


def _tree_file(space_id: Optional[int]) -> str:
    key = "active" if space_id is None else f"space-{int(space_id)}"
    return os.path.join(_DATA_DIR, f"{key}.json")


def _extract_json(content: str) -> Optional[dict]:
    text = (content or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        result = json.loads(text[start:end + 1])
        return result if isinstance(result, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _validate_tree(tree: Optional[dict]) -> Optional[dict]:
    if not isinstance(tree, dict):
        return None
    nodes = tree.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        return None
    root_nodes = tree.get("root_nodes") or []
    cleaned: dict[str, Any] = {"root_nodes": [], "nodes": {}}
    for nid, node in nodes.items():
        if not isinstance(node, dict):
            continue
        nid_s = str(nid)
        sample_questions = [str(q)[:200] for q in (node.get("sample_questions") or []) if str(q).strip()][:6]
        label = str(node.get("label") or "").strip()
        if not label and not sample_questions:
            continue
        cleaned["nodes"][nid_s] = {
            "id": nid_s,
            "label": str(node.get("label") or nid_s)[:80],
            "intent": str(node.get("intent") or "technical")[:40],
            "sample_questions": sample_questions,
            "children": [str(c) for c in (node.get("children") or [])][:6],
            "high_risk": bool(node.get("high_risk")),
            "risk_advice": str(node.get("risk_advice") or "")[:300],
            "advice": str(node.get("advice") or "")[:300],
        }
    if not cleaned["nodes"]:
        return None
    for r in root_nodes:
        if str(r) in cleaned["nodes"]:
            cleaned["root_nodes"].append(str(r))
    return cleaned


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------

def build_strategy_tree_prompt(
    role: str,
    jd_text: str,
    resume_text: str,
    questions: Optional[list[dict[str, Any]]] = None,
) -> str:
    q_text = ""
    if questions:
        q_text = "\n".join(
            f"- {q.get('question')}（类型:{q.get('type')}）"
            for q in questions[:12] if isinstance(q, dict)
        )
    return f"""你是资深面试教练。请基于岗位信息为候选人生成一棵“提问策略树”，用于真实面试中的实时辅助：面试官问一个问题时，能定位到树上的节点，并预测接下来最可能追问的方向与高危点。

目标岗位：{role or '（未填写）'}

岗位 JD：
{(jd_text or '（未提供）')[:4000]}

候选人简历：
{(resume_text or '（未提供）')[:4000]}

已知高频预测题（可选参考）：
{q_text or '（无）'}

输出严格 JSON：
{{
  "root_nodes": ["根节点id列表"],
  "nodes": {{
    "n1": {{
      "id": "n1",
      "label": "节点短名，如：项目深挖-高并发改造",
      "intent": "opening|technical|project|behavioral|scenario|closing|hr",
      "sample_questions": ["该节点最可能的 3-6 个问法"],
      "children": ["追问方向节点id"],
      "high_risk": true或false,
      "risk_advice": "高危点提示（候选人事先该准备什么，30字内）",
      "advice": "答题建议（30字内）"
    }}
  }}
}}
要求：
- 8-15 个节点，覆盖 开场/技术/项目深挖/行为/场景/收尾 主要环节；
- 根节点 3-5 个；children 指向该问题最可能的追问方向（形成深挖链）；
- 项目深挖、技术难点等节点 high_risk=true 并给 risk_advice；
- sample_questions 要具体、贴合 JD 与简历项目；只输出 JSON。
"""


def generate_strategy_tree(
    role: str,
    jd_text: str,
    resume_text: str,
    questions: Optional[list[dict[str, Any]]] = None,
) -> Optional[dict]:
    cfg = get_config()
    model_cfg = cfg.get_active_model()
    if not model_cfg or not getattr(model_cfg, "api_key", ""):
        raise ValueError("未配置可用的主 LLM（API Key）")
    client = get_client_for_model(model_cfg)
    prompt = build_strategy_tree_prompt(role, jd_text, resume_text, questions)
    kwargs = _completion_token_kwargs(model_cfg, 2500)
    think = _build_think_params(model_cfg, SimpleNamespace(think_mode=False, think_effort="off", max_tokens=2500))
    if think:
        kwargs["extra_body"] = think
    resp = client.chat.completions.create(
        model=model_cfg.model,
        messages=[
            {"role": "system", "content": "你是一位严谨的面试策略教练，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        stream=False,
        timeout=90,
        **kwargs,
    )
    content = resp.choices[0].message.content if resp.choices else ""
    tree = _validate_tree(_extract_json(content))
    if tree is None:
        raise ValueError("策略树生成结果格式异常")
    return tree


# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------

def save_tree(tree: dict, space_id: Optional[int] = None) -> str:
    os.makedirs(_DATA_DIR, exist_ok=True)
    path = _tree_file(space_id)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(tree, fh, ensure_ascii=False, indent=2)
    return path


def load_tree(space_id: Optional[int] = None) -> Optional[dict]:
    path = _tree_file(space_id)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return _validate_tree(json.load(fh))
    except Exception:  # noqa: BLE001
        return None


def activate_tree(space_id: Optional[int] = None, session_id: Optional[str] = None) -> Optional[dict]:
    tree = load_tree(space_id)
    key = _session_key(session_id)
    with _lock:
        _active_trees[key] = tree
        _active_space_ids[key] = space_id
        _current_node_ids[key] = None
    return tree


def get_active_tree(session_id: Optional[str] = None) -> Optional[dict]:
    key = _session_key(session_id)
    with _lock:
        return _active_trees.get(key)


def get_active_space_id(session_id: Optional[str] = None) -> Optional[int]:
    key = _session_key(session_id)
    with _lock:
        return _active_space_ids.get(key)


# ---------------------------------------------------------------------------
# 实时匹配（规则 + 字符 bigram，无外部 embedding 依赖）
# ---------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def _bigrams(text: str) -> set[str]:
    s = _WS_RE.sub("", text or "")
    return {s[i:i + 2] for i in range(len(s) - 1)}


def match_question(tree: dict, question_text: str, session_id: Optional[str] = None) -> dict[str, Any]:
    """把一句话匹配到策略树节点，返回追问预测/高危提示。"""
    key = _session_key(session_id)
    nodes = tree.get("nodes") or {}
    if not nodes:
        return {}
    q = (question_text or "").strip()
    if not q:
        return {}
    qb = _bigrams(q)
    if not qb:
        return {}

    best_node_id: Optional[str] = None
    best_score = 0.0
    for nid, node in nodes.items():
        texts = [str(node.get("label") or ""), str(node.get("intent") or "")]
        texts += [str(sq) for sq in (node.get("sample_questions") or [])]
        for t in texts:
            tb = _bigrams(t)
            if not tb:
                continue
            inter = len(qb & tb)
            union = len(qb | tb)
            score = inter / union if union else 0.0
            if score > best_score:
                best_score = score
                best_node_id = nid

    with _lock:
        current_node_id = _current_node_ids.get(key)
    inferred_from_previous = False
    if (best_node_id is None or best_score < 0.10) and current_node_id and current_node_id in nodes:
        best_node_id = current_node_id
        best_score = max(best_score, 0.06)
        inferred_from_previous = True
    with _lock:
        _current_node_ids[key] = best_node_id

    if best_node_id is None:
        return {}
    node = nodes[best_node_id]
    children = [nodes[c] for c in (node.get("children") or []) if c in nodes]
    return {
        "node_id": best_node_id,
        "label": str(node.get("label") or ""),
        "intent": str(node.get("intent") or ""),
        "confidence": round(float(best_score), 3),
        "uncertain": bool(best_score < 0.10),
        "inferred_from_previous": inferred_from_previous,
        "high_risk": bool(node.get("high_risk")),
        "risk_advice": str(node.get("risk_advice") or ""),
        "advice": str(node.get("advice") or ""),
        "predicted_followups": [
            {
                "label": str(c.get("label") or ""),
                "question": str((c.get("sample_questions") or [""])[0])[:200],
            }
            for c in children[:3]
        ],
    }


def reset_current_node(session_id: Optional[str] = None) -> None:
    key = _session_key(session_id)
    with _lock:
        _current_node_ids[key] = None
