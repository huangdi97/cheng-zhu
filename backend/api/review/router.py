import re
import io
import threading
import time
import uuid
from typing import Optional

import numpy as np
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, JSONResponse
from pydantic import BaseModel

from services.storage import review
from services.storage import job_tracker
from services import review_analysis, review_async_analysis
from services.stt.factory import transcribe_with_fallback
from core.config import get_config

router = APIRouter()


class UpdateSessionRequest(BaseModel):
    title: str | None = None
    company: str | None = None
    role: str | None = None
    application_id: int | None = None


class ManualReviewRequest(BaseModel):
    transcript: str
    title: str | None = None
    company: str | None = None
    role: str | None = None
    analyze: bool = True


class AsrCorrectionTestRequest(BaseModel):
    question: str | None = None
    answer: str | None = None


class UpdateTurnRequest(BaseModel):
    question_text: str = ""
    candidate_answer_text: str = ""
    analyze: bool = True


def _decode_audio_to_pcm16k(data: bytes) -> Optional[np.ndarray]:
    """把任意常见音频(wav/mp3/m4a/ogg)解码为 16k 单声道 int16 PCM。

    依赖 PyAV（faster-whisper 的依赖，已随 requirements 安装）。
    """
    if not data:
        return None
    try:
        import av
    except Exception:  # noqa: BLE001
        return None
    try:
        container = av.open(io.BytesIO(data))
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        chunks: list[np.ndarray] = []
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                arr = out.to_ndarray()
                chunks.append(np.asarray(arr).ravel())
        for out in resampler.resample(None):
            arr = out.to_ndarray()
            chunks.append(np.asarray(arr).ravel())
        container.close()
        if not chunks:
            return None
        pcm = np.concatenate(chunks).astype(np.int16)
        if len(pcm) < 16000 * 1:  # 少于 1 秒，基本是空录音
            return None
        return pcm
    except Exception:  # noqa: BLE001
        return None


_UPLOAD_JOBS: dict[str, dict] = {}
_UPLOAD_JOBS_LOCK = threading.Lock()
_UPLOAD_JOB_TTL = 3600.0


def _prune_upload_jobs() -> None:
    now = time.time()
    with _UPLOAD_JOBS_LOCK:
        for jid in [k for k, v in _UPLOAD_JOBS.items() if now - v.get("created_at", 0) > _UPLOAD_JOB_TTL]:
            _UPLOAD_JOBS.pop(jid, None)


def _update_upload_job(job_id: str, **kwargs) -> None:
    with _UPLOAD_JOBS_LOCK:
        if job_id in _UPLOAD_JOBS:
            _UPLOAD_JOBS[job_id].update(kwargs)


def _run_audio_upload_job(
    job_id: str,
    data: bytes,
    title: str,
    company: str,
    role: str,
    analyze: bool,
) -> None:
    """后台执行：解码 -> 转写 -> 结构化 -> 落库，进度写入 _UPLOAD_JOBS。"""
    try:
        _update_upload_job(job_id, stage="decoding")
        pcm = _decode_audio_to_pcm16k(data)
        if pcm is None:
            _update_upload_job(job_id, stage="error", error="无法解析音频（支持 wav/mp3/m4a/ogg），或录音过短")
            return

        _update_upload_job(job_id, stage="transcribing")
        cfg = get_config()
        try:
            text = transcribe_with_fallback(
                (pcm.astype(np.float32) / 32767.0),
                16000,
                position=cfg.position,
                language=cfg.language,
                provider="doubao",
                scope="review",
                fallback_on_empty_remote=True,
            )
        except Exception as e:  # noqa: BLE001
            _update_upload_job(job_id, stage="error", error=f"转写失败: {e}")
            return
        text = (text or "").strip()
        if len(text) < 8:
            _update_upload_job(job_id, stage="error", error="转写结果为空或过短，请检查录音内容/音质")
            return

        _update_upload_job(job_id, stage="structuring")
        turns = review_analysis.structure_transcript_turns(text)
        if not turns:
            _update_upload_job(job_id, stage="error", error="转写成功但未能整理成问答，请确认录音包含面试对话")
            return

        session_id = review.create_session(
            started_at=time.time(),
            interviewer_enabled=True,
            candidate_enabled=True,
            source="audio",
            title=title or "录音复盘",
            company=company or "",
            role=role or "",
        )
        for idx, turn in enumerate(turns, start=1):
            review.add_turn(
                session_id=session_id,
                qa_id=f"audio-{session_id}-{idx}",
                seq=idx,
                question_text=turn["question"],
                candidate_answer_text=turn["answer"],
                analysis_status="pending",
            )
        review.end_session(session_id, status="analyzing" if analyze else "completed", ended_at=time.time())
        if analyze:
            review_async_analysis.analyze_session_async(session_id)
        _update_upload_job(job_id, stage="done", session_id=session_id, turn_count=len(turns))
    except Exception as e:  # noqa: BLE001
        _update_upload_job(job_id, stage="error", error=str(e)[:200])


@router.post("/review/upload-audio")
async def upload_audio_review(
    file: UploadFile = File(...),
    title: str = Form(""),
    company: str = Form(""),
    role: str = Form(""),
    analyze: bool = Form(True),
):
    """上传面试录音 → 后台自动转写 → 结构化 Q&A → 生成复盘（异步，轮询进度）。"""
    data = await file.read()
    if not data:
        raise HTTPException(400, "未接收到音频文件")
    _prune_upload_jobs()
    job_id = uuid.uuid4().hex[:12]
    with _UPLOAD_JOBS_LOCK:
        _UPLOAD_JOBS[job_id] = {"stage": "queued", "created_at": time.time()}
    threading.Thread(
        target=_run_audio_upload_job,
        args=(job_id, data, title or "", company or "", role or "", analyze),
        daemon=True,
    ).start()
    return {"job_id": job_id, "status": "processing"}


@router.get("/review/upload-audio/{job_id}")
async def get_upload_audio_status(job_id: str):
    """查询录音转写任务进度。"""
    with _UPLOAD_JOBS_LOCK:
        job = _UPLOAD_JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在或已过期")
    return {
        "stage": job.get("stage", "queued"),
        "session_id": job.get("session_id"),
        "turn_count": job.get("turn_count"),
        "error": job.get("error"),
    }


_QUESTION_PREFIX = re.compile(r"^\s*(?:Q(?:uestion)?\s*\d*|问题\s*\d*|问|面试官|Interviewer|HR)\s*[:：]\s*(.*)$", re.I)
_ANSWER_PREFIX = re.compile(r"^\s*(?:A(?:nswer)?\s*\d*|回答\s*\d*|答|候选人|Candidate|我)\s*[:：]\s*(.*)$", re.I)


def _parse_manual_turns(transcript: str) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    current_question = ""
    answer_parts: list[str] = []

    def flush() -> None:
        nonlocal current_question, answer_parts
        answer = "\n".join(part.strip() for part in answer_parts if part.strip()).strip()
        if current_question.strip() and answer:
            turns.append({
                "question_text": current_question.strip(),
                "candidate_answer_text": answer,
            })
        current_question = ""
        answer_parts = []

    for raw_line in transcript.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        question_match = _QUESTION_PREFIX.match(line)
        answer_match = _ANSWER_PREFIX.match(line)

        if question_match:
            flush()
            current_question = question_match.group(1).strip()
            continue
        if answer_match:
            if current_question:
                answer_parts.append(answer_match.group(1).strip())
            continue
        if current_question:
            answer_parts.append(line)

    flush()
    return turns


def _has_generated_analysis(detail: dict) -> bool:
    if detail.get("summary_markdown") or detail.get("avg_score") is not None:
        return True
    for turn in detail.get("turns", []):
        if turn.get("analysis_status") == "completed" and (
            turn.get("strengths") or turn.get("risks") or turn.get("scorecard")
        ):
            return True
    return False


@router.get("/review/sessions")
async def list_sessions(page: int = 1, page_size: int = 20):
    """列表页"""
    return review.list_sessions(page, page_size)


@router.post("/review/sessions/manual")
async def create_manual_review(req: ManualReviewRequest):
    """从粘贴的逐字稿/问答文本创建手动复盘。"""
    transcript = (req.transcript or "").strip()
    if len(transcript) < 12:
        raise HTTPException(400, "复盘文本太短，请粘贴至少一组问答")

    turns = _parse_manual_turns(transcript)
    if not turns:
        raise HTTPException(400, "未识别到问答结构，请使用“面试官: ... / 候选人: ...”或“Q: ... / A: ...”格式")

    session_id = review.create_session(
        started_at=time.time(),
        interviewer_enabled=True,
        candidate_enabled=True,
        source="manual",
        title=req.title or "手动复盘",
        company=req.company or "",
        role=req.role or "",
    )
    for idx, turn in enumerate(turns, start=1):
        review.add_turn(
            session_id=session_id,
            qa_id=f"manual-{session_id}-{idx}",
            seq=idx,
            question_text=turn["question_text"],
            candidate_answer_text=turn["candidate_answer_text"],
            analysis_status="pending",
        )
    review.end_session(session_id, status="analyzing" if req.analyze else "completed", ended_at=time.time())

    if req.analyze:
        review_async_analysis.analyze_session_async(session_id)

    return {"session_id": session_id, "turn_count": len(turns), "status": "started" if req.analyze else "created"}


def _require_review_session(session_id: int) -> dict:
    detail = review.get_session_detail(session_id)
    if not detail:
        raise HTTPException(404, "Session not found")
    return detail


def _requeue_analysis(session_id: int, analyze: bool) -> None:
    if not analyze:
        return
    review.update_session_status(session_id, "analyzing")
    review_async_analysis.analyze_session_async(session_id)


@router.patch("/review/sessions/{session_id}/turns/{qa_id}")
async def update_review_turn(session_id: int, qa_id: str, req: UpdateTurnRequest):
    """编辑一轮复盘（问题/回答），并把该轮标记为待重新分析。"""
    _require_review_session(session_id)
    if not (req.question_text or "").strip():
        raise HTTPException(400, "问题不能为空")
    changed = review.update_turn_text(
        session_id,
        qa_id,
        req.question_text.strip(),
        (req.candidate_answer_text or "").strip(),
    )
    if not changed:
        raise HTTPException(404, "Turn not found")
    _requeue_analysis(session_id, req.analyze)
    return {"ok": True, "status": "analyzing" if req.analyze else "pending"}


@router.delete("/review/sessions/{session_id}/turns/{qa_id}")
async def delete_review_turn(session_id: int, qa_id: str, analyze: bool = True):
    """删除一轮复盘，并重新生成总结。"""
    _require_review_session(session_id)
    changed = review.delete_turn(session_id, qa_id)
    if not changed:
        raise HTTPException(404, "Turn not found")
    _requeue_analysis(session_id, analyze)
    return {"ok": True, "status": "analyzing" if analyze else "deleted"}


@router.get("/review/sessions/{session_id}")
async def get_session(session_id: int):
    """详情页"""
    detail = review.get_session_detail(session_id)
    if not detail:
        raise HTTPException(404, "Session not found")
    return detail


@router.patch("/review/sessions/{session_id}")
async def update_session(session_id: int, req: UpdateSessionRequest):
    """更新会话信息（标题、公司、岗位）"""
    try:
        if not review.get_session_detail(session_id):
            raise HTTPException(404, "Session not found")
        updates = req.model_dump(exclude_unset=True)
        if "application_id" in updates and updates["application_id"] is not None:
            if not job_tracker.get_application(int(updates["application_id"])):
                raise HTTPException(404, "Application not found")
        update_kwargs = {
            "session_id": session_id,
            "title": updates.get("title"),
            "company": updates.get("company"),
            "role": updates.get("role"),
        }
        if "application_id" in updates:
            update_kwargs["application_id"] = updates["application_id"]
        review.update_session_info(**update_kwargs)
        detail = review.get_session_detail(session_id)
        auto_sync_eligible = review.is_auto_sync_eligible_session(detail)
        return {
            "success": True,
            "synced_todos": bool(detail and detail.get("application_id") and auto_sync_eligible),
            "auto_sync_eligible": auto_sync_eligible,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/review/asr-correction-test")
async def test_asr_correction(req: AsrCorrectionTestRequest):
    """测试当前复盘模型是否可用于 ASR 纠错。"""
    return review_analysis.run_asr_correction_check(
        question=req.question or "请介绍一下你做过的缓存优化。",
        candidate_answer=req.answer or "",
    )


def _md_list(items, empty="无"):
    if not items:
        return empty
    return "\n".join(f"- {x}" for x in items)


def _build_review_markdown(detail: dict) -> str:
    lines = []
    title = detail.get("title") or "面试复盘"
    lines.append(f"# {title}")
    meta = []
    if detail.get("company"):
        meta.append(detail["company"])
    if detail.get("role"):
        meta.append(detail["role"])
    if detail.get("application"):
        meta.append(str(detail["application"].get("company") or ""))
    if meta:
        lines.append("")
        lines.append(" | ".join(meta))
    status = detail.get("status") or ""
    if status:
        lines.append("")
        lines.append(f"状态：{status}")
    lines.append("")
    lines.append("---")
    lines.append("")
    summary = detail.get("summary_markdown") or ""
    if summary:
        lines.append("## 整体复盘")
        lines.append("")
        lines.append(summary)
        lines.append("")
        lines.append("---")
        lines.append("")
    strong = detail.get("strong_points") or []
    weak = detail.get("weak_points") or []
    if strong or weak:
        lines.append("## 亮点")
        lines.append("")
        lines.append(_md_list(strong))
        lines.append("")
        lines.append("## 待改进")
        lines.append("")
        lines.append(_md_list(weak))
        lines.append("")
        lines.append("---")
        lines.append("")
    turns = detail.get("turns") or []
    lines.append("## 逐轮问答")
    lines.append("")
    if not turns:
        lines.append("（无问答记录）")
    for idx, turn in enumerate(turns, start=1):
        lines.append(f"### 第 {idx} 轮")
        lines.append("")
        lines.append(f"**面试官：** {turn.get('question_text') or ''}")
        lines.append("")
        cand = turn.get("candidate_answer_text") or ""
        lines.append(f"**候选人：** {cand}")
        lines.append("")
        corrected = turn.get("corrected_answer") or ""
        if corrected:
            lines.append(f"**修正答案：** {corrected}")
            lines.append("")
        strengths = turn.get("strengths") or []
        risks = turn.get("risks") or []
        if strengths or risks:
            lines.append("**亮点：**")
            lines.append("")
            lines.append(_md_list(strengths))
            lines.append("")
            lines.append("**风险：**")
            lines.append("")
            lines.append(_md_list(risks))
            lines.append("")
        evidence = turn.get("evidence") or {}
        if evidence:
            lines.append("**证据：**")
            lines.append("")
            for k, v in evidence.items() if isinstance(evidence, dict) else []:
                lines.append(f"- {k}: {v}")
            lines.append("")
        scorecard = turn.get("scorecard") or {}
        if scorecard:
            lines.append("**评分：**")
            lines.append("")
            for k, v in scorecard.items() if isinstance(scorecard, dict) else []:
                lines.append(f"- {k}: {v}")
            lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


@router.get("/review/sessions/{session_id}/export")
async def export_session(session_id: int, format: str = "md"):
    """导出复盘：format=md（默认）或 json。"""
    detail = review.get_session_detail(session_id)
    if not detail:
        raise HTTPException(404, "Session not found")
    fmt = (format or "md").lower()
    if fmt == "json":
        return JSONResponse(detail)
    md = _build_review_markdown(detail)
    filename = f"review-{session_id}.md"
    return PlainTextResponse(
        md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/review/current")
async def get_current_session():
    """当前进行中的 session"""
    current = review.get_current_session()
    return {"session": current}


@router.get("/review/profile")
async def get_profile():
    """长期画像：聚合最近已完成复盘的强弱项/行为特征/领域掌握度。"""
    return review.recent_profile(limit=10)


@router.post("/review/sessions/{session_id}/generate")
async def trigger_review_analysis(session_id: int):
    """手动触发复盘分析（用于一开始未开启但已落库的 session）"""
    detail = review.get_session_detail(session_id)
    if not detail:
        raise HTTPException(404, "Session not found")

    status = detail.get("status", "")

    # 如果正在分析，返回 pending
    if status == "analyzing":
        return {"status": "pending", "message": "分析正在进行中"}

    # completed 只有在已有分析内容时才表示真正完成；历史数据可能只是结束录制。
    if status == "completed" and _has_generated_analysis(detail):
        return {"status": "done", "message": "复盘已完成"}

    # 允许触发的状态：已录制待分析、历史 completed 空复盘、部分录制、分析失败或旧的 recording 归档。
    if status not in ["recorded", "recording", "completed", "partial_capture", "analysis_failed"]:
        raise HTTPException(400, f"当前状态 {status} 不支持触发分析")

    try:
        # 调用异步分析任务
        review_async_analysis.analyze_session_async(session_id)
        return {"status": "started", "message": "复盘分析已开始"}
    except Exception as e:
        raise HTTPException(500, str(e))
