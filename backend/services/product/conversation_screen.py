"""Conversation-owned Screen Context runtime.

MANUAL and AUTO share the same ephemeral capture transport, but Conversation
owns the policy, lifecycle and persistence. Raw screenshots are never written
to product.db: only extracted observation text plus one-way image/model-route
provenance is stored.

AUTO is deliberately explicit-start and fail-closed. Selecting AUTO in
Preflight merely permits the capability; the user must start it again in Live.
"""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Any
from urllib.parse import urlparse

from core.config import get_config
from services.storage import product as store


_AUTO_MIN_INTERVAL_SECONDS = 10
_AUTO_DEFAULT_INTERVAL_SECONDS = 30
_AUTO_MAX_INTERVAL_SECONDS = 300
_AUTO_MAX_CONSECUTIVE_ERRORS = 3

_auto_lock = threading.RLock()
_auto_session_id = ""
_auto_thread: threading.Thread | None = None
_auto_stop_event: threading.Event | None = None
_auto_paused = False
_auto_interval_seconds = _AUTO_DEFAULT_INTERVAL_SECONDS
_auto_region = "configured"
_auto_last_capture_at: float | None = None
_auto_last_image_hash = ""
_auto_last_error = ""
_auto_consecutive_errors = 0


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
    """Resolve the concrete vision route and policy blockers for this Session."""
    policy = dict(session.get("policy") or {})
    screen_mode = str(policy.get("screen_context") or "OFF").upper()
    processing = str(session.get("processing_mode") or "LOCAL").upper()
    ai_policy = str(policy.get("ai_assistance") or "AI_ALLOWED").upper()
    models = _enabled_vision_models()
    model = models[0] if models else None
    route = _route_for_base_url(str(getattr(model, "api_base_url", "") or "")) if model else "UNAVAILABLE"
    blockers: list[str] = []

    if screen_mode in {"MANUAL", "AUTO"}:
        if processing == "OFF":
            blockers.append("Processing=OFF 时不能使用 Screen Context。")
        if ai_policy == "AI_FORBIDDEN":
            blockers.append("AI_FORBIDDEN 时不能调用视觉模型解析 Screen Context。")
        if model is None:
            blockers.append("没有配置可用的视觉模型；Screen Context 不能开始。")
        elif processing == "LOCAL" and route != "LOCAL":
            blockers.append("Local Processing 要求 Screen Context 使用本地视觉模型；当前视觉模型存在远程数据路径。")

    if screen_mode == "AUTO":
        consent = str(policy.get("participant_consent_status") or "NOT_RECORDED")
        transparency = str(policy.get("participant_transparency_plan") or "NOT_RECORDED")
        if consent == "NOT_RECORDED":
            blockers.append("AUTO Screen Context 前必须记录参与者 consent/allowance 状态（用户报告）。")
        if transparency == "NOT_RECORDED":
            blockers.append("AUTO Screen Context 前必须记录透明告知计划；成竹不会自动通知其他参与者。")

    return {
        "mode": screen_mode,
        "available": screen_mode in {"MANUAL", "AUTO"} and not blockers,
        "route": route,
        "model_name": str(getattr(model, "name", "") or "") if model else "",
        "model_id": str(getattr(model, "model", "") or "") if model else "",
        "fingerprint": _fingerprint(model) if model else "",
        "raw_image_persisted": False,
        "auto_requires_explicit_start": screen_mode == "AUTO",
        "auto_default_interval_seconds": _AUTO_DEFAULT_INTERVAL_SECONDS,
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
        raise ValueError("截图中没有提取到足够可用且可追溯的上下文")
    return text[:6000]


def _resolve_region(region: str) -> str:
    cfg = get_config()
    capture_region = (
        str(getattr(cfg, "screen_capture_region", "left_half") or "left_half")
        if region == "configured"
        else str(region or "left_half")
    )
    if capture_region not in {"full", "left_half", "right_half", "top_half", "bottom_half"}:
        raise ValueError("Screen Context region 不支持")
    return capture_region


def _capture_once(
    session: dict[str, Any],
    *,
    requested_mode: str,
    region: str,
    frozen_runtime: dict[str, Any] | None,
    dedupe_image: bool,
) -> dict[str, Any] | None:
    if str(session.get("status") or "") != "ACTIVE":
        raise ValueError("只有进行中的 Conversation Session 可以捕获 Screen Context")

    status = vision_runtime_status(session)
    mode = str(requested_mode or "").upper()
    if status["mode"] != mode:
        raise ValueError(f"本场 Screen Context 不是 {mode}；不能执行该捕获")
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

    capture_region = _resolve_region(region)
    cfg = get_config()
    image = capture_primary_region_data_url(
        capture_region,
        max_long_edge=int(getattr(cfg, "screen_capture_max_long_edge", 1600) or 1600),
    )
    image_hash = hashlib.sha256(image.encode("ascii", errors="ignore")).hexdigest()

    if dedupe_image:
        with _auto_lock:
            if session["id"] == _auto_session_id and image_hash == _auto_last_image_hash:
                return None

    extracted = _analyze_image(image, model)
    row = {
        "id": store.new_id("csc_"),
        "space_id": session["space_id"],
        "session_id": session["id"],
        "capture_mode": mode,
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


def capture_manual(
    session: dict[str, Any],
    *,
    region: str = "configured",
    frozen_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Capture one explicit screenshot and persist only its extracted observation."""
    with _auto_lock:
        if _auto_session_id == session.get("id"):
            raise ValueError("AUTO Screen Context 已占用本场屏幕捕获；Off the record 期间也不允许手动抓取，请先停止 AUTO")
    row = _capture_once(
        session,
        requested_mode="MANUAL",
        region=region,
        frozen_runtime=frozen_runtime,
        dedupe_image=False,
    )
    if row is None:
        raise ValueError("Screen Context 未产生新观察")
    return row


def list_context(session_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return store.select(
        "conversation_screen_context",
        where="session_id = ?",
        params=(session_id,),
        order="created_at DESC",
        limit=max(1, min(100, int(limit))),
    )


def auto_status(session_id: str = "") -> dict[str, Any]:
    with _auto_lock:
        active = bool(_auto_session_id and _auto_thread and _auto_thread.is_alive())
        return {
            "active": active,
            "session_id": _auto_session_id,
            "owns_requested_session": bool(session_id and session_id == _auto_session_id),
            "paused": bool(_auto_paused) if active else False,
            "interval_seconds": _auto_interval_seconds,
            "region": _auto_region,
            "last_capture_at": _auto_last_capture_at,
            "last_error": _auto_last_error,
            "consecutive_errors": _auto_consecutive_errors,
            "raw_image_persisted": False,
            "explicit_start_required": True,
        }


def _auto_worker(
    session_id: str,
    stop_event: threading.Event,
    *,
    interval_seconds: int,
    region: str,
    frozen_runtime: dict[str, Any],
) -> None:
    global _auto_session_id, _auto_paused
    global _auto_last_capture_at, _auto_last_error, _auto_consecutive_errors, _auto_last_image_hash
    try:
        while not stop_event.is_set():
            with _auto_lock:
                if session_id != _auto_session_id:
                    break
                paused = _auto_paused
            if paused:
                stop_event.wait(0.5)
                continue

            session = store.get("conversation_session", session_id)
            if session is None or str(session.get("status") or "") != "ACTIVE":
                break

            try:
                row = _capture_once(
                    session,
                    requested_mode="AUTO",
                    region=region,
                    frozen_runtime=frozen_runtime,
                    dedupe_image=True,
                )
                with _auto_lock:
                    if row is not None:
                        _auto_last_capture_at = float(row.get("created_at") or store.now())
                        _auto_last_image_hash = str(row.get("image_hash") or "")
                    _auto_last_error = ""
                    _auto_consecutive_errors = 0
            except ValueError as exc:
                message = str(exc)
                # A blank/unreadable frame is a normal observation outcome,
                # not a runtime failure. AUTO stays alive and simply waits for
                # the next interval without persisting anything.
                if "没有提取到足够可用且可追溯的上下文" in message:
                    with _auto_lock:
                        _auto_last_error = ""
                        _auto_consecutive_errors = 0
                else:
                    with _auto_lock:
                        _auto_last_error = message[:800]
                        _auto_consecutive_errors += 1
                        should_stop = _auto_consecutive_errors >= _AUTO_MAX_CONSECUTIVE_ERRORS
                    if should_stop:
                        break
            except Exception as exc:  # noqa: BLE001
                with _auto_lock:
                    _auto_last_error = str(exc)[:800]
                    _auto_consecutive_errors += 1
                    should_stop = _auto_consecutive_errors >= _AUTO_MAX_CONSECUTIVE_ERRORS
                if should_stop:
                    break

            stop_event.wait(interval_seconds)
    finally:
        with _auto_lock:
            if session_id == _auto_session_id:
                # Keep diagnostic error/last-capture fields, but release ownership.
                _auto_session_id = ""
                _auto_paused = False


def start_auto(
    session: dict[str, Any],
    *,
    interval_seconds: int = _AUTO_DEFAULT_INTERVAL_SECONDS,
    region: str = "configured",
    frozen_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    global _auto_session_id, _auto_thread, _auto_stop_event, _auto_paused
    global _auto_interval_seconds, _auto_region, _auto_last_capture_at
    global _auto_last_image_hash, _auto_last_error, _auto_consecutive_errors

    if str(session.get("status") or "") != "ACTIVE":
        raise ValueError("只有进行中的 Conversation Session 可以启动 AUTO Screen Context")
    status = vision_runtime_status(session)
    if status["mode"] != "AUTO":
        raise ValueError("本场 Screen Context 不是 AUTO")
    if status["blockers"]:
        raise ValueError(status["blockers"][0])

    interval = max(_AUTO_MIN_INTERVAL_SECONDS, min(_AUTO_MAX_INTERVAL_SECONDS, int(interval_seconds)))
    frozen = dict(frozen_runtime or {})
    frozen_fp = str(frozen.get("fingerprint") or "")
    if frozen_fp and frozen_fp != status["fingerprint"]:
        raise ValueError("视觉模型/数据路径已在本场开始后变化；请新开一场再启用 AUTO Screen Context")
    _resolve_region(region)

    with _auto_lock:
        if _auto_session_id:
            if _auto_session_id == session["id"]:
                return auto_status(session["id"])
            raise ValueError("另一场 Conversation 正在使用 AUTO Screen Context；请先停止它")
        _auto_session_id = session["id"]
        _auto_paused = False
        _auto_interval_seconds = interval
        _auto_region = region
        _auto_last_capture_at = None
        _auto_last_image_hash = ""
        _auto_last_error = ""
        _auto_consecutive_errors = 0
        _auto_stop_event = threading.Event()
        worker = threading.Thread(
            target=_auto_worker,
            kwargs={
                "session_id": session["id"],
                "stop_event": _auto_stop_event,
                "interval_seconds": interval,
                "region": region,
                "frozen_runtime": frozen,
            },
            daemon=True,
            name=f"chengzhu-screen-auto-{session['id'][:12]}",
        )
        _auto_thread = worker
        worker.start()
    return auto_status(session["id"])


def pause_auto(session_id: str) -> dict[str, Any]:
    global _auto_paused
    with _auto_lock:
        if session_id != _auto_session_id:
            raise ValueError("这场 Conversation 没有运行 AUTO Screen Context")
        _auto_paused = True
    return auto_status(session_id)


def resume_auto(session_id: str) -> dict[str, Any]:
    global _auto_paused
    with _auto_lock:
        if session_id != _auto_session_id:
            raise ValueError("这场 Conversation 没有运行 AUTO Screen Context")
        _auto_paused = False
    return auto_status(session_id)


def stop_auto(session_id: str = "") -> dict[str, Any]:
    global _auto_session_id, _auto_thread, _auto_stop_event, _auto_paused
    with _auto_lock:
        if not _auto_session_id:
            return auto_status(session_id)
        if session_id and session_id != _auto_session_id:
            return auto_status(session_id)
        owned_session = _auto_session_id
        thread = _auto_thread
        stop_event = _auto_stop_event
        if stop_event is not None:
            stop_event.set()

    if thread is not None and thread is not threading.current_thread():
        thread.join(timeout=3.0)

    with _auto_lock:
        if _auto_session_id == owned_session:
            _auto_session_id = ""
            _auto_paused = False
        _auto_thread = None
        _auto_stop_event = None
    return auto_status(session_id or owned_session)
