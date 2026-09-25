"""准备空间 API：岗位对齐洞察 + 项目技能卡 + 预测真题。"""

from __future__ import annotations

import threading
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from core.logger import get_logger
from services.storage import prep_space
from services import prep_service, practice_service, skill_builder, live_listen
from services.storage.resume_history import get_entry_detail

router = APIRouter()
_rlog = get_logger("prep.router")


class CreateSpaceRequest(BaseModel):
    title: Optional[str] = None
    role: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    jd_text: str = Field(default="", max_length=200000)
    resume_text: Optional[str] = Field(default=None, max_length=200000)
    resume_history_id: Optional[int] = None


def _resolve_resume_text(req: CreateSpaceRequest) -> tuple[str, Optional[int]]:
    """简历正文优先用请求传入；否则从简历历史记录加载完整摘要。"""
    if req.resume_text and req.resume_text.strip():
        return req.resume_text.strip(), req.resume_history_id
    if req.resume_history_id is not None:
        detail = get_entry_detail(req.resume_history_id)
        if detail:
            summary = (detail.get("summary") or "").strip()
            if summary:
                return summary, req.resume_history_id
    return (req.resume_text or "").strip(), req.resume_history_id


@router.post("/prep/spaces")
async def api_create_space(req: CreateSpaceRequest):
    if not (req.role or req.jd_text or req.resume_text or req.resume_history_id):
        raise HTTPException(400, "请至少填写岗位名称、JD 或简历")
    resume_text, history_id = _resolve_resume_text(req)
    space_id = prep_space.create_space(
        title=req.title or req.role or "未命名准备空间",
        role=req.role,
        company=req.company,
        jd_text=req.jd_text,
        resume_text=resume_text,
        resume_history_id=history_id,
    )
    # JD 同步到实时辅助：PrepSpace 填了 JD 后，实时回答自动注入 <jd_context>
    if (req.jd_text or "").strip():
        try:
            from core.config import update_config
            update_config({"jd_text": req.jd_text.strip()})
            _rlog.info("prep space %s synced jd_text to live assist", space_id)
        except Exception as e:
            _rlog.warning("prep jd sync failed space=%s: %s", space_id, e)
    return prep_space.get_space(space_id)


@router.get("/prep/spaces")
async def api_list_spaces():
    return {"items": prep_space.list_spaces()}


@router.get("/prep/spaces/{space_id}")
async def api_get_space(space_id: int):
    space = prep_space.get_space(space_id)
    if not space:
        raise HTTPException(404, "准备空间不存在")
    return space


@router.delete("/prep/spaces/{space_id}")
async def api_delete_space(space_id: int):
    if not prep_space.delete_space(space_id):
        raise HTTPException(404, "准备空间不存在")
    return {"ok": True}


def _generate_sync(space_id: int) -> None:
    """依次生成洞察 / 技能卡 / 真题；每部分独立记录状态，失败不阻塞其余部分。"""
    space = prep_space.get_space(space_id)
    if not space:
        return
    role, company = space.get("role") or "", space.get("company") or ""
    jd_text, resume_text = space.get("jd_text") or "", space.get("resume_text") or ""

    # 1) 岗位对齐洞察
    try:
        prep_space.update_insight(space_id, "", "generating")
        insight = prep_service.generate_insight(role, company, jd_text, resume_text)
        markdown = insight.get("markdown") or ""
        prep_space.update_insight(space_id, markdown, "done")
        _rlog.info("prep space %s insight done", space_id)
    except Exception as e:
        _rlog.warning("prep space %s insight failed: %s", space_id, e)
        prep_space.update_insight(space_id, "", "failed", str(e)[:300])

    # 2) 项目技能卡
    cards = []
    try:
        cards = prep_service.generate_skill_cards(role, jd_text, resume_text)
        for c in cards:
            card_id = prep_space.add_skill_card(space_id, c.get("name") or "未命名项目")
            prep_space.update_skill_card(card_id, c, "done")
        _rlog.info("prep space %s skill cards done (%d)", space_id, len(cards))
    except Exception as e:
        _rlog.warning("prep space %s skill cards failed: %s", space_id, e)
        card_id = prep_space.add_skill_card(space_id, "生成失败")
        prep_space.update_skill_card(card_id, {}, "failed", str(e)[:300])

    # 3) 预测真题（依赖洞察与技能卡）
    try:
        space = prep_space.get_space(space_id)
        insight_markdown = (space or {}).get("insight_markdown") or ""
        questions = prep_service.generate_questions(
            role, company, jd_text, resume_text, insight_markdown, cards
        )
        prep_space.update_questions(space_id, questions, "done")
        _rlog.info("prep space %s questions done (%d)", space_id, len(questions))
    except Exception as e:
        _rlog.warning("prep space %s questions failed: %s", space_id, e)
        prep_space.update_questions(space_id, [], "failed", str(e)[:300])


@router.post("/prep/spaces/{space_id}/generate")
async def api_generate_space(space_id: int):
    if not prep_space.get_space(space_id):
        raise HTTPException(404, "准备空间不存在")
    if not prep_service.prep_configured():
        raise HTTPException(400, "尚未配置有效的模型 API Key，请先在设置中配置模型")
    await run_in_threadpool(_generate_sync, space_id)
    return prep_space.get_space(space_id)


@router.post("/prep/spaces/{space_id}/launch-pack")
async def api_activate_launch_pack(space_id: int):
    """Activate one prep space for the current live interview session."""
    space = prep_space.get_space(space_id)
    if not space:
        raise HTTPException(404, "准备空间不存在")
    from core.config import update_config
    from core.session import get_session
    from services import copilot_strategy

    update_config({
        "position": str(space.get("role") or "") or "通用岗位",
        "jd_text": str(space.get("jd_text") or ""),
        "resume_text": str(space.get("resume_text") or "") or None,
        "assist_answer_align_jd_enabled": True,
    })
    tree = copilot_strategy.load_tree(space_id)
    generated = False
    if tree is None and prep_service.prep_configured():
        tree = await run_in_threadpool(
            copilot_strategy.generate_strategy_tree,
            str(space.get("role") or ""),
            str(space.get("jd_text") or ""),
            str(space.get("resume_text") or ""),
            list(space.get("questions") or []),
        )
        if tree:
            copilot_strategy.save_tree(tree, space_id)
            generated = True
    if tree is not None:
        copilot_strategy.activate_tree(space_id, get_session().session_id)
    return {
        "ok": True,
        "strategy_ready": tree is not None,
        "strategy_generated": generated,
        "pack": prep_service.build_launch_pack(space),
    }

class StartPracticeRequest(BaseModel):
    space_id: int
    rounds: int = 5


class PracticeAnswerRequest(BaseModel):
    answer: str = Field(..., max_length=20000)


@router.post("/prep/practice/start")
async def api_practice_start(req: StartPracticeRequest):
    if not prep_service.prep_configured():
        raise HTTPException(400, "尚未配置有效的模型 API Key，请先在设置中配置模型")
    try:
        return await run_in_threadpool(practice_service.start_session, req.space_id, req.rounds)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/prep/practice/{practice_id}/answer")
async def api_practice_answer(practice_id: str, req: PracticeAnswerRequest):
    try:
        return await run_in_threadpool(practice_service.submit_answer, practice_id, req.answer)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/prep/practice/{practice_id}/finish")
async def api_practice_finish(practice_id: str):
    try:
        return await run_in_threadpool(practice_service.finish_session, practice_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

class TranscribeAudioRequest(BaseModel):
    device_id: int
    duration_sec: float = 8.0


_record_lock = threading.Lock()


def _record_mic(device_id: int, duration_sec: float):
    import sounddevice as sd
    import numpy as np

    # 用设备原生采样率录制，再线性重采样到 16k（部分 WASAPI 设备不支持 16k）
    info = sd.query_devices(device_id, "input")
    rate = int(info.get("default_samplerate") or 48000)
    frames = max(1, int(duration_sec * rate))
    audio = sd.rec(frames, samplerate=rate, channels=1, dtype="int16", device=device_id)
    sd.wait()
    audio = np.asarray(audio[:, 0], dtype=np.int16)
    if rate != 16000:
        n_out = max(1, int(len(audio) * 16000 / rate))
        xs = np.linspace(0, max(0, len(audio) - 1), n_out)
        audio = np.interp(xs, np.arange(len(audio)), audio.astype(np.float64)).astype(np.int16)
    return audio


@router.post("/prep/practice/transcribe")
async def api_practice_transcribe(req: TranscribeAudioRequest):
    import time

    from core.config import get_config
    from services.stt import get_stt_engine

    duration = max(1.0, min(float(req.duration_sec or 8.0), 20.0))
    with _record_lock:
        try:
            audio = await run_in_threadpool(_record_mic, req.device_id, duration)
        except Exception as e:
            raise HTTPException(400, f"录音失败，请检查设备是否被占用：{str(e)[:160]}")
        try:
            cfg = get_config()
            engine = get_stt_engine()
            engine.load_model()
            t0 = time.time()
            text = await run_in_threadpool(
                engine.transcribe,
                audio,
                16000,
                getattr(cfg, "position", "后端开发"),
                getattr(cfg, "language", "Python"),
            )
            return {
                "text": (text or "").strip(),
                "duration_sec": round(duration, 1),
                "latency_ms": int((time.time() - t0) * 1000),
            }
        except Exception as e:
            raise HTTPException(500, f"转写失败：{str(e)[:200]}")

class SkillBuilderStartRequest(BaseModel):
    space_id: int


class SkillBuilderAnswerRequest(BaseModel):
    text: str = Field(..., max_length=20000)


@router.post("/prep/skill-builder/start")
async def api_skill_builder_start(req: SkillBuilderStartRequest):
    if not prep_service.prep_configured():
        raise HTTPException(400, "尚未配置有效的模型 API Key，请先在设置中配置模型")
    try:
        return await run_in_threadpool(skill_builder.start_session, req.space_id)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/prep/skill-builder/{builder_id}/answer")
async def api_skill_builder_answer(builder_id: str, req: SkillBuilderAnswerRequest):
    try:
        return await run_in_threadpool(skill_builder.answer, builder_id, req.text)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/prep/skill-builder/{builder_id}/skip")
async def api_skill_builder_skip(builder_id: str):
    try:
        return await run_in_threadpool(skill_builder.skip, builder_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

class ListenRequest(BaseModel):
    device_id: int
    max_seconds: float = 30.0
    silence_sec: float = 1.5


def _listen_mic(device_id: int, max_seconds: float, silence_sec: float):
    """VAD 监听：检测到说话才开始累积，停顿 silence_sec 自动结束。返回 (audio16k, rate)。"""
    import sounddevice as sd
    import numpy as np

    info = sd.query_devices(device_id, "input")
    rate = int(info.get("default_samplerate") or 48000)
    block = max(1, int(rate * 0.05))
    threshold = 32767 * 0.01
    started = time.time()
    buf: list[np.ndarray] = []
    speech = False
    silence_blocks = 0
    silence_limit = max(1, int(silence_sec * rate / block))

    def _cb(indata, _frames, _time_info, _status):
        nonlocal speech, silence_blocks
        a = np.asarray(indata[:, 0], dtype=np.int16)
        rms = float(np.sqrt(np.mean(a.astype(np.float64) ** 2))) if len(a) else 0.0
        if rms > threshold:
            speech = True
            silence_blocks = 0
        elif speech:
            silence_blocks += 1
        if speech:
            buf.append(a)

    with sd.InputStream(
        samplerate=rate, channels=1, dtype="int16",
        device=device_id, blocksize=block, callback=_cb,
    ):
        while time.time() - started < max_seconds:
            if speech and silence_blocks >= silence_limit:
                break
            time.sleep(0.05)

    if not buf:
        return np.zeros(0, dtype=np.int16), 16000
    audio = np.concatenate(buf)
    if rate != 16000:
        n_out = max(1, int(len(audio) * 16000 / rate))
        xs = np.linspace(0, max(0, len(audio) - 1), n_out)
        audio = np.interp(xs, np.arange(len(audio)), audio.astype(np.float64)).astype(np.int16)
    return audio, 16000


@router.post("/prep/listen")
async def api_prep_listen(req: ListenRequest):
    import time as _time_mod

    from core.config import get_config
    from services.stt import get_stt_engine

    max_sec = max(2.0, min(float(req.max_seconds or 30.0), 60.0))
    silence = max(0.5, min(float(req.silence_sec or 1.5), 5.0))
    with _record_lock:
        try:
            audio, rate = await run_in_threadpool(_listen_mic, req.device_id, max_sec, silence)
        except Exception as e:
            raise HTTPException(400, f"监听失败，请检查麦克风是否被占用：{str(e)[:160]}")
        if len(audio) == 0:
            return {"text": "", "duration_sec": 0.0, "latency_ms": 0, "heard_speech": False}
        try:
            cfg = get_config()
            engine = get_stt_engine()
            engine.load_model()
            t0 = _time_mod.time()
            text = await run_in_threadpool(
                engine.transcribe,
                audio,
                rate,
                getattr(cfg, "position", "后端开发"),
                getattr(cfg, "language", "Python"),
            )
            return {
                "text": (text or "").strip(),
                "duration_sec": round(len(audio) / rate, 1),
                "latency_ms": int((_time_mod.time() - t0) * 1000),
                "heard_speech": True,
            }
        except Exception as e:
            raise HTTPException(500, f"转写失败：{str(e)[:200]}")

class LiveListenStartRequest(BaseModel):
    device_id: int
    max_seconds: float = 60.0
    silence_sec: float = 1.5


@router.post("/prep/listen/start")
async def api_prep_listen_start(req: LiveListenStartRequest):
    try:
        return await run_in_threadpool(
            live_listen.start, req.device_id, req.max_seconds, req.silence_sec
        )
    except Exception as e:
        raise HTTPException(400, f"启动听写失败：{str(e)[:160]}")


@router.get("/prep/listen/status")
async def api_prep_listen_status():
    return live_listen.status()


@router.post("/prep/listen/stop")
async def api_prep_listen_stop():
    try:
        return await run_in_threadpool(live_listen.stop)
    except Exception as e:
        raise HTTPException(400, f"停止听写失败：{str(e)[:160]}")
