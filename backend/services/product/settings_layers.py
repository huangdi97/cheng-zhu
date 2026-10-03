"""Settings 3.0 layering: Global Default → Goal Default → This Session Override.

Global defaults are the persisted config.json values. Goal defaults and
session overrides live in product.db ``setting_override``. At Go Live the
resolved session values are installed as the config *session overlay*
(core.config.set_session_overlay) so the live pipeline reads them through
get_config() without them ever being saved as global defaults.

Each resolved value reports its origin so Preflight can show
我的成竹 / Goal 默认 / 本场覆盖 / 系统默认.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from core.config import AppConfig, clear_session_overlay, persisted_config, set_session_overlay
from services.storage import product as store

SCOPES = ("GOAL", "SESSION")
ORIGIN_LABELS = {
    "SESSION": "本场覆盖",
    "GOAL": "Goal 默认",
    "GLOBAL": "全局默认",
    "SYSTEM": "系统默认",
    "PERSON": "我的成竹",
}

# Keys that may be layered per Goal / per Session. Anything else is global-only.
LAYERED_KEYS: dict[str, dict[str, Any]] = {
    "answer_language": {"group": "Language", "label": "回答语言",
                        "options": ["中文", "English", "FOLLOW_INTERVIEW"]},
    "whisper_language": {"group": "Language", "label": "面试语言（识别）", "options": ["auto", "zh", "en"]},
    "language": {"group": "Language", "label": "编程语言",
                 "options": ["Python", "Java", "C++", "JavaScript", "TypeScript", "Go", "SQL"]},
    "technical_term_policy": {"group": "Language", "label": "技术术语",
                              "options": ["AUTO", "KEEP_ENGLISH", "TRANSLATE", "BILINGUAL"]},
    "ai_policy_mode": {"group": "Live & Overlay", "label": "AI 辅助",
                       "options": ["AI_FORBIDDEN", "AI_LIMITED", "AI_ALLOWED", "AI_EXPECTED"]},
    "human_assistance_policy": {"group": "Live & Overlay", "label": "真人辅助",
                                "options": ["HUMAN_FORBIDDEN", "HUMAN_PRACTICE_ONLY", "HUMAN_ALLOWED"]},
    "share_privacy_mode": {"group": "Privacy", "label": "共享隐私", "options": ["OFF", "PRIVATE_OVERLAY"]},
    "speech_adoption_analytics_live": {"group": "Privacy", "label": "Live 表达分析", "options": [True, False]},
    "proactive_guidance_enabled": {"group": "Live & Overlay", "label": "主动提示（Nudge）", "options": [True, False]},
    "kb_enabled": {"group": "Knowledge", "label": "知识库", "options": [True, False]},
    "active_model": {"group": "Models", "label": "回答模型", "options": None},
}

_SYSTEM_DEFAULTS = AppConfig().model_dump()


class SettingsLayerError(ValueError):
    pass


def _validate(key: str, value: Any) -> Any:
    spec = LAYERED_KEYS.get(key)
    if spec is None:
        raise SettingsLayerError(f"{key} 不支持按目标/本场覆盖")
    options = spec["options"]
    if options is not None and value not in options:
        raise SettingsLayerError(f"{key} 的取值必须是 {options} 之一")
    if key == "active_model":
        models = persisted_config().models
        if not isinstance(value, int) or not 0 <= value < len(models):
            raise SettingsLayerError("模型序号无效")
    return value


def set_override(scope: str, scope_id: str, key: str, value: Any) -> dict[str, Any]:
    if scope not in SCOPES:
        raise SettingsLayerError(f"未知层级：{scope}")
    if not scope_id:
        raise SettingsLayerError("缺少目标或场次")
    value = _validate(key, value)
    with store.connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO setting_override (scope, scope_id, key, value_json, updated_at) VALUES (?, ?, ?, ?, ?)",
            (scope, scope_id, key, json.dumps(value, ensure_ascii=False), store.now()),
        )
    return {"scope": scope, "scope_id": scope_id, "key": key, "value": value}


def clear_override(scope: str, scope_id: str, key: str = "") -> int:
    with store.connect() as conn:
        if key:
            return conn.execute("DELETE FROM setting_override WHERE scope = ? AND scope_id = ? AND key = ?",
                                (scope, scope_id, key)).rowcount
        return conn.execute("DELETE FROM setting_override WHERE scope = ? AND scope_id = ?", (scope, scope_id)).rowcount


def overrides(scope: str, scope_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in store.select("setting_override", "scope = ? AND scope_id = ?", (scope, scope_id)):
        out[row["key"]] = row["value"]
    return out


def resolve(goal_id: str = "", session_id: str = "") -> dict[str, dict[str, Any]]:
    """Effective value + origin for every layered key."""
    global_cfg = persisted_config().model_dump()
    goal = overrides("GOAL", goal_id) if goal_id else {}
    session = overrides("SESSION", session_id) if session_id else {}
    out: dict[str, dict[str, Any]] = {}
    for key, spec in LAYERED_KEYS.items():
        if key in session:
            value, origin = session[key], "SESSION"
        elif key in goal:
            value, origin = goal[key], "GOAL"
        else:
            value = global_cfg.get(key)
            origin = "SYSTEM" if value == _SYSTEM_DEFAULTS.get(key) else "GLOBAL"
        out[key] = {"value": value, "origin": origin, "origin_label": ORIGIN_LABELS[origin],
                    "label": spec["label"], "group": spec["group"],
                    "goal_value": goal.get(key), "session_value": session.get(key),
                    "global_value": global_cfg.get(key)}
    return out


def apply_session(goal_id: str = "", session_id: str = "") -> dict[str, Any]:
    """Install Goal + Session layers as the runtime overlay for this session."""
    resolved = resolve(goal_id, session_id)
    overlay = {k: v["value"] for k, v in resolved.items() if v["origin"] in ("GOAL", "SESSION")}
    return set_session_overlay(overlay)


def end_session() -> None:
    clear_session_overlay()


def explain(key: str, goal_id: str = "", session_id: str = "") -> Optional[dict[str, Any]]:
    return resolve(goal_id, session_id).get(key)
