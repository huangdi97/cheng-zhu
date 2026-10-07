"""Conversation-owned manual Screen Context.

The capture transport is shared with Interview, but the state and persistence
are not.  Raw screenshots are ephemeral: only extracted text plus a one-way
image fingerprint/model-route provenance is written to product.db.
"""
from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlparse

from core.config import get_config
from services.storage import product as store


def _enabled_vision_models() -> list[Any]:
    cfg = get_config()
    return [
        model
        for model in list(getattr(cfg, "models", []) or [])
        if bool(getattr(model, "supports_vision", False))
        and bool(getattr(model, "enabled", True))
        and str(getattr(model, "api_key", "") or "") not in {"", "sk-your-api-key-here"}
    ]


def _route_for_base_url(base_url: str) -> str:
    raw = str(base_url or "").strip()
    if not raw:
        return "REMOTE"
    try:
        host = (urlparse(raw).hostname or "").lower()
    except Exception:
        host = ""
    if host in {"localhost", "127.0.0.1", "::1"}:
        return "LOCAL"
    return "REMOTE"


def _fingerprint(model: Any) -> str:
    raw = "|".join([
        str(getattr(model, "name", "") or ""),
        str(getattr(model, "model", "") or ""),
        str(getattr(model, "api_base_url", "") or ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def vision_runtime_status(session: dict[str, Any]) -> dict[str, Any]:
    """Resolve the concrete vision route for this Conversation session."""
    policy = dict(session.get("policy") or {})
    screen_mode = str(policy.get("screen_context") or "OFF").upper()
    processing = str(session.get("processing_mode") or "LOCAL").upper()
    ai_policy = str(policy.get("ai_assistance") or "AI_ALLOWED").upper()
    models = _enabled_vision_models()
    model = models[0] if models else None
    route = _route_for_base_url(str(getattr(model, "api_base_url", "") or "")) if model else "UNAVAILABLE"
    blockers: list[str] = []

    if screen_mode == "AUTO":
        blockers.append("Conversation 自动 Screen Context 尚未接线；当前仅支持 OFF / MANUAL。")
    elif screen_mode == "MANUAL":
        if processing == "OFF":
            blockers.append("Processing=OFF 时不能使用 Screen Context。")
        if ai_policy == "AI_FORBIDDEN":
            blockers.append("AI_FORBIDDEN 时不能调用视觉模型解析 Screen Context。")
        if model is None:
            blockers.append("没有配置可用的视觉模型；MANUAL Screen Context 不能开始。")
        elif processing == "LOCAL" and route != "LOCAL":
            blockers.append("Local Processing 要求 Screen Context 使用本地视觉模型；当前视觉模型存在远程数据路径。")

    return {
        "mode": screen_mode,
        "available": screen_mode == "MANUAL" and not blockers,
        "route": route,
        "model_name": str(getattr(model, "name", "") or "") if model else "",
        "model_id": str(getattr(model, "model", "") or "") if model else "",
        "fingerprint": _fingerprint(model) if model else "",
        "raw_image_persisted": False,
        "blockers": blockers,
    }


def _analyze_image(image_data_url: str, model: Any) -> str:
    from services.llm import _add_tokens, get_client_for_model

    prompt = (
        "你是成竹 Conversation 的 Screen Context 提取器。"
        "只提取截图中清晰可见、可能与当前对话相关的文字、数字、表格事实和明确状态。"
        "不要回答问题，不要补全截图外的信息，不要推断人物情绪、人格、隐藏意图、底价或未显示的结论。"
        "输出简洁中文纯文本；保留关键英文、数字、版本号。"
        "如果没有足够可读且有用的内容，只输出 NO_USABLE_CONTEXT。"
    )
    client = get_client_for_model(model)
    try:
        response = client.chat.completions.create(
            model=model.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }],
            temperature=0,
            max_tokens=1200,
            stream=False,
            timeout=60,
        )
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Screen Context 视觉解析失败: {exc}") from exc

    usage = getattr(response, "usage", None)
    if usage:
        _add_tokens(
            int(getattr(usage, "prompt_tokens", 0) or 0),
            int(getattr(usage, "completion_tokens", 0) or 0),
            str(getattr(model, "model", "") or ""),
        )
    text = ""
    if getattr(response, "choices", None):
        text = str(response.choices[0].message.content or "").strip()
    if not text or text == "NO_USABLE_CONTEXT":
        raise ValueError("截图中没有提取到足够可用的可追溯上下文")
    return text[:6000]


def capture_manual(
    session: dict[str, Any],
    *,
    region: str = "configured",
    frozen_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture one screenshot and persist only its extracted observation."""
    if str(session.get("status") or "") != "ACTIVE":
        raise ValueError("只有进行中的 Conversation Session 可以捕获 Screen Context")

    status = vision_runtime_status(session)
    if status["mode"] != "MANUAL":
        raise ValueError("本场 Screen Context 不是 MANUAL；不能执行手动截图")
    if status["blockers"]:
        raise ValueError(status["blockers"][0])

    frozen = dict(frozen_runtime or {})
    frozen_fp = str(frozen.get("fingerprint") or "")
    if frozen_fp and frozen_fp != status["fingerprint"]:
        raise ValueError("视觉模型/数据路径已在本场开始后变化；为保持 Session Pack 冻结语义，请新开一场再使用 Screen Context")

    models = _enabled_vision_models()
    if not models:
        raise ValueError("没有配置可用的视觉模型")
    model = models[0]

    from services.capture.screen_capture import capture_primary_region_data_url

    cfg = get_config()
    capture_region: Any
    if region == "configured":
        capture_region = str(getattr(cfg, "screen_capture_region", "left_half") or "left_half")
    else:
        capture_region = str(region or "left_half")
    if capture_region not in {"full", "left_half", "right_half", "top_half", "bottom_half"}:
        raise ValueError("Screen Context region 不支持")
    image = capture_primary_region_data_url(
        capture_region,
        max_long_edge=int(getattr(cfg, "screen_capture_max_long_edge", 1600) or 1600),
    )
    image_hash = hashlib.sha256(image.encode("ascii", errors="ignore")).hexdigest()
    extracted = _analyze_image(image, model)

    row = {
        "id": store.new_id("csc_"),
        "space_id": session["space_id"],
        "session_id": session["id"],
        "capture_mode": "MANUAL",
        "region": capture_region,
        "text": extracted,
        "image_hash": image_hash,
        "vision_model": status["model_id"] or status["model_name"],
        "vision_route": status["route"],
        "vision_fingerprint": status["fingerprint"],
        "source": "LOCAL_SCREEN_CAPTURE",
        "created_at": store.now(),
    }
    store.insert("conversation_screen_context", row)
    return store.get("conversation_screen_context", row["id"]) or row


def list_context(session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return store.select(
        "conversation_screen_context",
        where="session_id = ?",
        params=(session_id,),
        order="created_at DESC",
        limit=max(1, min(100, int(limit))),
    )
