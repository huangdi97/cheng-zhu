"""Answer generation worker for the assist pipeline."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from core.config import get_config
from core.session import get_session, conversation_lock
from services.stt import classify_followup, normalize_transcription_for_analysis
from services.answer_grounding import (
    analyze_experience_grounding,
    enforce_experience_answer,
)
from services.answer_depth import (
    build_conversation_bridge,
    classify_answer_depth,
)
from services.llm import (
    PROMPT_MODE_ASR_REALTIME,
    PROMPT_MODE_MANUAL_TEXT,
    PROMPT_MODE_SERVER_SCREEN,
    PROMPT_MODE_WRITTEN_EXAM,
    PromptMode,
    build_system_prompt,
    chat_stream_single_model,
    create_answer_stream_sanitizer,
    schedule_prefix_cache_warmup,
    get_token_stats,
    LLMError,
    postprocess_answer_for_mode,
)
from api.assist.scheduler import TaskPayload


@dataclass(frozen=True)
class AnswerWorkerDeps:
    abort_check: Callable[[], bool]
    is_session_current: Callable[[int], bool]
    flush_commit: Callable[[int, Callable[[], None]], None]
    mark_seq_skipped: Callable[[int], None]
    submit_knowledge_record: Callable[[str, str, str, str], bool]
    broadcast: Callable[[dict], None]
    logger: Any
    error_logger: Any
    start_abort_check: Optional[Callable[[], bool]] = None
    model_cfg_snapshot: Any = None
    # The dispatcher captures the complete immutable configuration that was
    # active when the task claimed a model.  Runtime/session state is still
    # read through the callbacks above, but prompt and generation settings
    # must not drift while a queued worker is waiting to start.
    config_snapshot: Any = None


def _screen_region_label(region: str) -> str:
    labels = {
        "full": "主显示器全屏",
        "left_half": "主显示器左半屏",
        "right_half": "主显示器右半屏",
        "top_half": "主显示器上半屏",
        "bottom_half": "主显示器下半屏",
        "custom": "主显示器自定义区域",
    }
    return labels.get(region, "主显示器左半屏")


def prompt_server_screen_code(language: str, region: str) -> str:
    where = _screen_region_label(region)
    return (
        f"下图来自运行本后端的电脑「{where}」的实时画面，可能包含题目描述、输入输出约束或代码片段。\n\n"
        f"请基于图中可见信息作答。若是编程题，代码请优先使用 {language}（SQL 题使用 sql）。\n\n"
        "请尽量按以下顺序组织：题目理解、主方案代码、备选方案代码（1-2 个）、方案对比、思路与复杂度、测试用例设计。\n"
        "如果关键信息看不清，请明确说明缺失项，不要编造；可在合理假设下给出最小可执行方案。"
    )


def _normalize_task_images(image: Any) -> list[str]:
    if isinstance(image, list):
        return [str(x) for x in image if x]
    if image:
        return [str(image)]
    return []


def _image_payload_chars(images: list[str]) -> int:
    return sum(len(img or "") for img in images)


def _message_text_chars(messages: list[dict]) -> int:
    total = 0
    for msg in messages:
        content = msg.get("content")
        if isinstance(content, str):
            total += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += len(str(part.get("text") or ""))
    return total


def _clip_text(text: str, max_chars: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max(0, max_chars - 1)].rstrip() + "…"


def _context_excerpt(text: str, max_chars: int) -> str:
    cleaned = " ".join(str(text or "").split())
    budget = max(80, int(max_chars or 0))
    if len(cleaned) <= budget:
        return cleaned
    if budget <= 140:
        return _clip_text(cleaned, budget)
    head_budget = max(60, min(120, budget // 2))
    tail_budget = max(60, budget - head_budget - 3)
    return f"{cleaned[:head_budget].rstrip()}…{cleaned[-tail_budget:].lstrip()}"


def _written_exam_question_context_label(question: str, source: str) -> str:
    cleaned = " ".join(str(question or "").split())
    if (
        cleaned.startswith("下图来自运行本后端")
        or "请基于图中可见信息作答" in cleaned
    ):
        if source == "server_screen_multi":
            return "上一批连续截图题面（无 OCR 文本，以上一版答案和当前截图为准）"
        return "上一张截图题面（无 OCR 文本，以上一版答案和当前截图为准）"
    return _clip_text(cleaned, 260)


def _written_exam_followup_context(session_ref, *, source: str, image_count: int) -> str:
    if image_count <= 0 or not (source or "").startswith("server_screen_"):
        return ""
    recent_qas = [
        qa
        for qa in session_ref.qa_pairs[-4:]
        if (qa.question or qa.answer)
        and (qa.source or "").startswith("server_screen_")
        and not (qa.source or "").endswith("exam_preflight")
    ][-2:]
    if not recent_qas:
        return ""

    lines = [
        "[笔试连续截图上下文]",
        "当前截图优先级最高: 若截图里出现新增规则、隐藏/边界条件、失败用例、编译/运行报错、预期输出和实际输出, 必须据此修正上一版答案。",
        "不要因为上一版代码已存在就忽略当前截图; 若当前截图显示上一版未通过, 直接输出修正后的完整可提交代码。",
        "如果当前截图明显是新题或与上一题无关, 忽略下面旧答案, 按新题作答。",
        "最近上一版答案参考:",
    ]
    for idx, qa in enumerate(recent_qas, start=1):
        lines.append(
            f"{idx}. 题目/截图: {_written_exam_question_context_label(qa.question, qa.source)}"
        )
        lines.append(f"   上一版答案: {_clip_text(qa.answer, 900)}")
    return "\n".join(lines)


def _candidate_context_settings(cfg) -> tuple[bool, int, int, int]:
    enabled = bool(getattr(cfg, "candidate_asr_enabled", False)) and bool(
        getattr(cfg, "candidate_context_enabled", True)
    )
    return (
        enabled,
        max(0, min(2000, int(getattr(cfg, "candidate_context_wait_ms", 200) or 0))),
        max(100, min(4000, int(getattr(cfg, "candidate_context_max_chars", 900) or 900))),
        max(1, min(100, int(getattr(cfg, "candidate_context_min_chars", 6) or 6))),
    )


_CANDIDATE_BACKGROUND_STOP_TERMS = frozenset(
    {
        "一个",
        "一下",
        "上一个",
        "上一轮",
        "上一",
        "上轮",
        "上面",
        "下一个",
        "这个",
        "那个",
        "这些",
        "那些",
        "怎么",
        "如何",
        "什么",
        "为什么",
        "为什",
        "可以",
        "能不能",
        "你们",
        "我们",
        "他们",
        "里面",
        "就是",
        "如果",
        "然后",
        "还有",
        "另外",
        "但是",
        "不过",
        "具体",
        "详细",
        "展开",
        "补充",
        "介绍",
        "讲讲",
        "说说",
        "回答",
        "问题",
        "项目",
        "经历",
        "业务",
        "核心",
        "实现",
        "处理",
        "方案",
        "使用",
        "用了",
        "实际",
        "讲的是",
        "候选",
        "候选人",
    }
)
_CANDIDATE_BACKGROUND_EN_STOP_TERMS = frozenset(
    {
        "and",
        "are",
        "can",
        "could",
        "did",
        "does",
        "for",
        "how",
        "that",
        "the",
        "this",
        "what",
        "when",
        "why",
        "would",
        "you",
        "your",
    }
)


def _candidate_background_topic_terms(text: str) -> set[str]:
    normalized = normalize_transcription_for_analysis(text).lower()
    if not normalized:
        return set()
    terms: set[str] = set()
    for token in re.findall(r"[a-z0-9][a-z0-9_+#.-]{1,}", normalized):
        cleaned = token.strip("._-")
        if len(cleaned) >= 2 and cleaned not in _CANDIDATE_BACKGROUND_EN_STOP_TERMS:
            terms.add(cleaned)

    for block in re.findall(r"[\u4e00-\u9fff]+", normalized):
        max_size = min(4, len(block))
        for size in range(2, max_size + 1):
            for start in range(0, len(block) - size + 1):
                term = block[start: start + size]
                if term not in _CANDIDATE_BACKGROUND_STOP_TERMS:
                    terms.add(term)
    return terms


def _candidate_background_matches_current_question(
    question_text: str,
    last_qa: Any,
    actual_spoken_answer: str,
) -> bool:
    question_terms = _candidate_background_topic_terms(question_text)
    if not question_terms:
        return False
    previous_terms = _candidate_background_topic_terms(
        f"{getattr(last_qa, 'question', '')} {actual_spoken_answer}"
    )
    return bool(question_terms & previous_terms)


_FOLLOWUP_BRIDGE_PREFIXES = (
    "那",
    "那么",
    "然后",
    "所以",
    "但是",
    "不过",
    "另外",
    "还有",
    "这个",
    "那个",
    "这样",
    "这种",
    "刚才",
    "前面",
    "上面",
    "how",
    "why",
    "what about",
    "then",
    "so",
    "and",
    "also",
    "could you",
    "can you",
)
_FOLLOWUP_BRIDGE_PHRASES = (
    "刚才说的",
    "前面说的",
    "上一个",
    "上一轮",
    "这个怎么",
    "那个怎么",
    "怎么验证",
    "为什么不",
    "展开讲",
    "详细讲",
    "具体讲",
    "举个例子",
    "补充一下",
    "接着说",
    "继续说",
    "you just mentioned",
    "you said",
    "previous one",
    "last round",
    "how did you",
    "how would you",
    "how do you",
    "why did you",
    "why not",
    "can you elaborate",
    "could you elaborate",
    "give an example",
    "tell me more",
    "continue",
)

_RESUME_CONTEXT_CUES = (
    "简历",
    "实习",
    "项目经历",
    "项目经验",
    "实习经历",
    "工作经历",
    "过往经历",
    "个人经历",
    "你的经历",
    "你过去经历",
    "自我介绍",
    "介绍一下自己",
    "介绍下自己",
    "介绍你自己",
    "介绍一下你自己",
    "简单介绍",
    "先介绍一下",
    "先做个介绍",
    "先做个自我介绍",
    "说说你自己",
    "聊聊你自己",
    "你做过",
    "你之前做",
    "你负责",
    "你们当时",
    "上一家公司",
    "项目里",
    "项目中",
    "项目上",
    "你的项目",
    "你们项目",
    "你在项目",
    "做过的项目",
    "负责的项目",
    "参与的项目",
    "最近的项目",
    "讲讲项目",
    "说说项目",
    "resume",
    "cv",
    "tell me about yourself",
    "introduce yourself",
    "introduce yourself briefly",
    "quick introduction",
    "brief introduction",
    "walk me through your resume",
    "walk me through your cv",
    "walk me through your background",
    "walk through your resume",
    "walk through your background",
    "share your background",
    "about your background",
    "my background",
    "your background",
    "my experience",
    "your experience",
    "my project",
    "your project",
    "previous project",
    "project experience",
    "internship",
    "work experience",
    "previous company",
    "what you built",
    "what you worked on",
)
_RESUME_CONTEXT_NEGATIONS = (
    "不要结合项目",
    "不结合项目",
    "不用结合项目",
    "别结合项目",
    "不要参考项目",
    "不参考项目",
    "不用参考项目",
    "别参考项目",
    "不要带项目",
    "不带项目",
    "不用带项目",
    "别带项目",
    "先不说项目",
    "先别说项目",
    "和项目无关",
    "跟项目无关",
    "与项目无关",
    "不要结合简历",
    "不结合简历",
    "不用结合简历",
    "别结合简历",
    "不要参考简历",
    "不参考简历",
    "不用参考简历",
    "别参考简历",
    "不要看简历",
    "不看简历",
    "不用看简历",
    "别看简历",
    "和简历无关",
    "跟简历无关",
    "与简历无关",
    "without resume",
    "without my resume",
    "without your resume",
    "not based on resume",
    "not based on my resume",
    "not based on your resume",
    "ignore resume",
    "ignore my resume",
    "ignore your resume",
    "do not use resume",
    "don't use resume",
    "without project context",
    "no project context",
    "not based on project",
    "not based on my project",
    "not based on your project",
    "ignore project",
    "ignore my project",
    "ignore your project",
    "do not use project",
    "don't use project",
    "do not relate to my project",
    "don't relate to my project",
    "do not relate to your project",
    "don't relate to your project",
    "do not relate it to my project",
    "don't relate it to my project",
    "do not relate it to your project",
    "don't relate it to your project",
    "do not combine with project",
    "don't combine with project",
)
_CHINESE_RESUME_NEGATION_ACTIONS = (
    "不要结合",
    "不结合",
    "不用结合",
    "别结合",
    "不要参考",
    "不参考",
    "不用参考",
    "别参考",
    "不要带",
    "不带",
    "不用带",
    "别带",
    "不要看",
    "不看",
    "不用看",
    "别看",
    "不要基于",
    "不基于",
    "不用基于",
    "别基于",
    "先不说",
    "先别说",
)
_CHINESE_RESUME_NEGATION_TARGETS = ("项目", "简历")
_CHINESE_RESUME_UNRELATED_PREFIXES = ("和", "跟", "与")
_CHINESE_RESUME_UNRELATED_MARKERS = ("无关", "没关系", "没有关系")


def _contains_resume_context_negation(normalized_lc: str) -> bool:
    if any(phrase in normalized_lc for phrase in _RESUME_CONTEXT_NEGATIONS):
        return True
    for action in _CHINESE_RESUME_NEGATION_ACTIONS:
        start = normalized_lc.find(action)
        while start >= 0:
            tail = normalized_lc[start + len(action): start + len(action) + 14]
            if any(target in tail for target in _CHINESE_RESUME_NEGATION_TARGETS):
                return True
            start = normalized_lc.find(action, start + 1)
    for prefix in _CHINESE_RESUME_UNRELATED_PREFIXES:
        start = normalized_lc.find(prefix)
        while start >= 0:
            tail = normalized_lc[start + len(prefix): start + len(prefix) + 14]
            if (
                any(target in tail for target in _CHINESE_RESUME_NEGATION_TARGETS)
                and any(marker in tail for marker in _CHINESE_RESUME_UNRELATED_MARKERS)
            ):
                return True
            start = normalized_lc.find(prefix, start + 1)
    return False


def _followup_needs_bridge(question_text: str) -> bool:
    normalized = normalize_transcription_for_analysis(question_text)
    if not normalized:
        return False
    normalized_lc = normalized.lower()
    if len(normalized) <= 18:
        return True
    if any(phrase in normalized_lc for phrase in _FOLLOWUP_BRIDGE_PHRASES) and len(normalized) <= 64:
        return True
    if any(normalized_lc.startswith(prefix) for prefix in _FOLLOWUP_BRIDGE_PREFIXES) and len(normalized) <= 56:
        return True
    return False


def _question_explicitly_requests_resume_context(question_text: str) -> bool:
    normalized = normalize_transcription_for_analysis(question_text)
    if not normalized:
        return False
    normalized_lc = normalized.lower()
    if _contains_resume_context_negation(normalized_lc):
        return False
    return any(phrase in normalized_lc for phrase in _RESUME_CONTEXT_CUES)


def _question_rejects_resume_context(question_text: str) -> bool:
    normalized = normalize_transcription_for_analysis(question_text)
    if not normalized:
        return False
    return _contains_resume_context_negation(normalized.lower())


def _should_include_resume_context(
    prompt_mode: PromptMode,
    question_text: str,
    *,
    last_qa=None,
    is_followup: bool = False,
    followup_needs_bridge: bool = False,
) -> bool:
    if _question_rejects_resume_context(question_text):
        return False
    if prompt_mode != PROMPT_MODE_ASR_REALTIME:
        return True
    if _question_explicitly_requests_resume_context(question_text):
        return True
    if not is_followup or not last_qa or not followup_needs_bridge:
        return False
    return _question_explicitly_requests_resume_context(getattr(last_qa, "question", ""))


def _empty_history_stats(profile: str) -> dict[str, Any]:
    return {
        "messages": 0,
        "history_messages": 0,
        "stripped_images": 0,
        "profile": profile,
        "raw_text_chars": 0,
        "trimmed_text_chars": 0,
        "max_chars_per_message": 0,
        "total_char_budget": 0,
    }


def _history_context_options(prompt_mode: PromptMode, written_exam: bool) -> dict[str, Any]:
    if written_exam:
        return {
            "profile": "written_none",
            "turns": 0,
            "max_chars_per_message": 0,
            "include_summary": False,
            "total_char_budget": 0,
        }
    if prompt_mode == PROMPT_MODE_ASR_REALTIME:
        return {
            "profile": "asr_compact",
            "turns": 1,
            "max_chars_per_message": 520,
            "include_summary": False,
            "total_char_budget": 1100,
        }
    if prompt_mode == PROMPT_MODE_SERVER_SCREEN:
        return {
            "profile": "screen_light",
            "turns": 1,
            "max_chars_per_message": 700,
            "include_summary": False,
            "total_char_budget": 900,
        }
    if prompt_mode == PROMPT_MODE_MANUAL_TEXT:
        return {
            "profile": "manual_balanced",
            "turns": 3,
            "max_chars_per_message": 900,
            "include_summary": True,
            "total_char_budget": 2600,
        }
    return {
        "profile": "default",
        "turns": None,
        "max_chars_per_message": None,
        "include_summary": True,
        "total_char_budget": None,
    }


def _max_tokens_for_prompt(
    prompt_mode: PromptMode,
    cfg,
    *,
    high_churn_short_answer: bool = False,
    answer_depth_profile: str = "concise",
) -> int:
    base_limit = max(1, int(getattr(cfg, "max_tokens", 4096) or 4096))
    if prompt_mode == PROMPT_MODE_ASR_REALTIME:
        if high_churn_short_answer:
            cap = int(getattr(cfg, "assist_realtime_high_churn_max_tokens", 420) or 420)
        elif answer_depth_profile in {"deep", "structured", "compact_deep"}:
            # Keep the user-facing realtime toggle as a latency default, but
            # do not let it truncate open-ended judgement/design questions to
            # a slogan.  The normal realtime cap remains the explicit upper
            # bound configured by the user.
            cap = int(getattr(cfg, "assist_realtime_max_tokens", 900) or 900)
        elif bool(getattr(cfg, "assist_realtime_concise_answer", True)):
            # 极简口语话术：给足 100-150 字 + 少量余量即可，防止模型扩成长文。
            cap = int(getattr(cfg, "assist_realtime_concise_max_tokens", 480) or 480)
        else:
            cap = int(getattr(cfg, "assist_realtime_max_tokens", 900) or 900)
        return max(1, min(base_limit, cap))
    return base_limit


def _wait_for_candidate_context_if_pending(session_ref, qa_id: str, wait_ms: int) -> None:
    if wait_ms <= 0 or not qa_id:
        return
    deadline = time.monotonic() + (wait_ms / 1000.0)
    while time.monotonic() < deadline:
        if not getattr(session_ref, "has_candidate_asr_pending_for_qa", lambda *_args, **_kwargs: False)(qa_id):
            return
        time.sleep(0.025)


def _supports_candidate_context_source(source: str, meta: dict[str, Any]) -> bool:
    if source == "manual_text":
        return True
    if source in ("asr", "conversation_loopback", "conversation_mic"):
        return True
    return meta.get("origin") == "asr"


def prompt_mode_for_task(
    source: str,
    manual_input: bool,
    written_exam: bool = False,
) -> PromptMode:
    if written_exam:
        return PROMPT_MODE_WRITTEN_EXAM
    if (source or "").startswith("server_screen_"):
        return PROMPT_MODE_SERVER_SCREEN
    if manual_input:
        return PROMPT_MODE_MANUAL_TEXT
    return PROMPT_MODE_ASR_REALTIME


def _build_memo_context(session_ref) -> str:
    try:
        from core.config import get_config
        if not bool(getattr(get_config(), "rolling_memo_enabled", True)):
            return ""
    except Exception:
        pass
    parts = []
    manual = (getattr(session_ref, "memo_manual", "") or "").strip()
    auto = (getattr(session_ref, "system_summary", "") or "").strip()
    if manual:
        parts.append("## 手动备忘\n" + manual)
    if auto:
        parts.append(auto)
    return "\n\n".join(parts)


def _schedule_question_translation(qa_id: str, question_text: str, model_cfg, broadcast) -> None:
    """面试官问题定稿后，并行翻一句（不阻塞主回答链路）。"""
    def _worker() -> None:
        try:
            from services.llm.streaming import get_client_for_model
            cfg = get_config()
            ans_lang = (cfg.answer_language or "中文").strip().lower()
            target_lang = "中文" if ans_lang in ("en", "english", "英文", "英语") else "英文"
            prompt = (
                f"请把下面这句面试问题翻译成{target_lang}，只输出译文，不要任何解释或前缀：\n"
                f"{question_text[:2000]}"
            )
            client = get_client_for_model(model_cfg)
            resp = client.chat.completions.create(
                model=model_cfg.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=512,
                temperature=0.2,
                stream=False,
                timeout=15,
            )
            translated = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            if translated:
                broadcast({
                    "type": "translation",
                    "id": qa_id,
                    "question": question_text,
                    "translated": translated,
                    "to": target_lang,
                })
        except Exception:  # noqa: BLE001
            pass

    try:
        threading.Thread(target=_worker, name="question-translate", daemon=True).start()
    except Exception:  # noqa: BLE001
        pass


def _schedule_answer_suggestion(qa_id: str, question: str, answer: str, model_cfg, broadcast) -> None:
    """答完后并行生成 下一句/证据/风险/自评 四行建议。"""
    def _worker() -> None:
        try:
            from services.llm.streaming import get_client_for_model
            prompt = (
                "你是面试辅导教练。根据面试官问题和候选人的回答，给出 4 行短建议：\n"
                "下一句：继续这个话题该补的一句（第一人称，不超过 40 字）\n"
                "证据：还缺的一个具体例子或数字（不超过 40 字）\n"
                "风险：这句话可能踩的坑（不超过 40 字）\n"
                "自评：0-10 分 + 一句话理由（不超过 30 字）\n"
                "只输出这 4 行，不要多余文字。\n\n"
                f"问题：{question}\n"
                f"回答：{answer[:1500]}"
            )
            client = get_client_for_model(model_cfg)
            resp = client.chat.completions.create(
                model=model_cfg.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.4,
                stream=False,
                timeout=20,
            )
            text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            if text:
                broadcast({"type": "suggestion", "id": qa_id, "text": text, "question": question})
        except Exception:  # noqa: BLE001
            pass

    try:
        threading.Thread(target=_worker, name="answer-suggestion", daemon=True).start()
    except Exception:  # noqa: BLE001
        pass


def emit_early_cue(question_text: str, qa_id: str, meta: dict, *, broadcast) -> dict:
    """R2 Stage I/K: deterministic L0 cue right after the question group is
    confirmed, before the late-constraint grace delays the deep answer.
    Read-only: no interview-state event is committed here (the answer
    worker does that), only understanding + frozen-pack compile + L0."""
    from services.intelligence import fast_cue, latency_clock
    from services.intelligence.answer_planner import create_plan
    from services.intelligence.context_compiler import compile_live_context
    from services.intelligence.question_understanding import understand_question
    from services.intelligence.semantics import provenance_from_grounding
    from services.answer_grounding import analyze_experience_grounding

    cfg = get_config()
    sid = _live_session_id()
    latency_clock.start_turn(
        sid,
        qa_id,
        source=str(meta.get("source", "") or "asr"),
        provisional=bool(meta.get("provisional")),
    )
    pack = _resolve_live_pack(sid, cfg)
    understanding = understand_question(question_text)
    grounding = analyze_experience_grounding(question_text, resume_text=pack.profile_text, interview_notes=_pack_notes(pack, cfg))
    plan = create_plan(
        understanding.question_type,
        resolved_question=understanding.resolved_question,
        intent=understanding.intent,
        expected_depth=understanding.expected_depth,
        personal_fact_required=understanding.personal_fact_required,
        open_world_allowed=understanding.open_world_allowed,
        provenance=provenance_from_grounding(grounding.status, has_profile=bool(pack.profile_text.strip()), question=question_text, profile_text=pack.profile_text),
        raw_question=question_text,
        profile_text=pack.profile_text,
        ai_policy=pack.ai_policy,
    )
    from services.intelligence.policy import live_guidance_allowed_for_pack

    if not live_guidance_allowed_for_pack(pack, cfg):
        return {}
    compiled, _sections = compile_live_context(pack, question_text, deep=False)
    body = fast_cue.build_l0(
        question_raw=question_text,
        resolved_question=understanding.resolved_question,
        plan_meta=dict(plan.metadata or {}),
        response_mode=plan.mode.value,
        compiled_items=compiled.items,
        job_requirements=pack.job_requirements,
    )
    latency_clock.mark(qa_id, "G0")
    payload = fast_cue.finalize(body, qa_id=qa_id, timing=latency_clock.metrics(qa_id))
    payload["early"] = True
    # The cue can render its own card before answer_start (the deep answer
    # waits for the late-constraint grace), so it carries the question.
    payload["question"] = str(meta.get("display_question") or question_text)
    payload["provisional"] = bool(meta.get("provisional"))
    if meta.get("reconciled"):
        payload["reconciled"] = str(meta["reconciled"])
    broadcast(payload)
    try:
        from api.coach.router import remember_fast_cue

        remember_fast_cue(payload)
    except Exception:  # noqa: BLE001
        pass
    return payload


def _live_session_id() -> str:
    try:
        from core.session import session_id as _sid

        return str(_sid() or "default")
    except Exception:  # noqa: BLE001
        return "default"


def _resolve_live_pack(session_id: str, cfg):
    from services.intelligence.interview_pack import ephemeral_pack, resolve_live_pack

    try:
        return resolve_live_pack(session_id, cfg)
    except Exception:  # noqa: BLE001
        return ephemeral_pack(session_id, cfg)


def _pack_notes(pack, cfg) -> str:
    """Interview notes are frozen into the pack; an unfrozen session uses the
    current config value (there is no other session to confuse it with)."""
    prefs = pack.answer_preferences if pack.frozen else {}
    if "notes" in prefs:
        return str(prefs.get("notes") or "")
    return str(getattr(cfg, "interview_notes", "") or "")


def _voice_line(pack) -> str:
    try:
        from api.intelligence.r2_router import voice_prompt_line

        return voice_prompt_line(dict((pack.voice_profile or {}).get("explicit_preferences") or {}))
    except Exception:  # noqa: BLE001
        return ""


def _save_turn_trace(
    *,
    qa_id: str,
    session_id: str,
    pack,
    question_text: str,
    intelligence_layer: dict,
    fast_cue_payload: dict,
    compiled_items: list,
    compile_stats: dict,
    latency_metrics: dict,
    provider: str,
    model: str,
    stream_guard,
) -> None:
    """Review 2.0 trace: what the candidate saw for this turn. Never contains
    provider keys or the full resume; context is recorded by fragment id."""
    try:
        from services.storage import intelligence as intel_storage

        plan = intelligence_layer.get("plan") or {}
        understanding = intelligence_layer.get("understanding") or {}
        intel_storage.save_turn_trace(
            qa_id,
            session_id,
            str(getattr(pack, "id", "") or ""),
            {
                "question_raw": question_text[:500],
                "resolved_question": str(understanding.get("resolved_question", "") or "")[:500],
                "response_mode": str(plan.get("mode", "") or ""),
                "axes": {k: (plan.get("metadata") or {}).get(k) for k in ("dialogue_act", "content_type", "truth_requirement", "provenance", "assertion_policy")},
                "fast_cue": {k: fast_cue_payload.get(k) for k in ("direction", "cues", "cautions", "level")} if fast_cue_payload else {},
                "context": [
                    {"fragment_id": (item.metadata or {}).get("fragment_id", item.id), "source_type": item.source_type.value, "provenance": (item.metadata or {}).get("provenance", "")}
                    for item in compiled_items
                ],
                "context_stats": compile_stats,
                "latency": latency_metrics,
                "provider": provider,
                "model": model,
                "stream_guard_rewrites": int(getattr(stream_guard, "rewrites", 0) or 0),
            },
        )
    except Exception:  # noqa: BLE001
        pass


def _lat_mark(qa_id: str, point: str, mono: Optional[float] = None) -> None:
    try:
        from services.intelligence import latency_clock

        latency_clock.mark(qa_id, point, mono)
    except Exception:  # noqa: BLE001
        pass


def _lat_finish(qa_id: str) -> dict:
    try:
        from services.intelligence import latency_clock

        return latency_clock.finish_turn(qa_id)
    except Exception:  # noqa: BLE001
        return {}


def _apply_guard_rewrites(text: str, guard) -> str:
    for event in getattr(guard, "events", []):
        if event.kind == "rewrite" and event.sentence and event.sentence in text:
            text = text.replace(event.sentence, event.released, 1)
    return text


def _emit_fast_cue(
    *,
    qa_id: str,
    question_text: str,
    intelligence_layer: dict,
    compiled_items: list,
    kb_hits: list,
    live_pack,
    session_claim_block: str,
    cfg,
    broadcast,
    logger,
) -> dict:
    """R2 Stage K: emit guidance_fast (L0) before the deep stream starts."""
    try:
        from services.intelligence import fast_cue, latency_clock

        plan = intelligence_layer.get("plan") or {}
        understanding = intelligence_layer.get("understanding") or {}
        body = fast_cue.build_l0(
            question_raw=question_text,
            resolved_question=str(understanding.get("resolved_question", "") or question_text),
            plan_meta=dict(plan.get("metadata") or {}),
            response_mode=str(plan.get("mode", "") or "KNOWLEDGE"),
            compiled_items=compiled_items,
            kb_hits=[hit for hit in (kb_hits or []) if live_pack.kb_path_allowed(str(getattr(hit, "path", "") or ""))],
            job_requirements=live_pack.job_requirements,
            session_constraints=session_claim_block,
        )
        latency_clock.mark(qa_id, "G0")
        payload = fast_cue.finalize(body, qa_id=qa_id, timing=latency_clock.metrics(qa_id))
        broadcast(payload)
        try:
            from api.coach.router import remember_fast_cue

            remember_fast_cue(payload)
        except Exception:  # noqa: BLE001
            pass
        _schedule_fast_cue_l1(qa_id, payload, live_pack, cfg, broadcast)
        return payload
    except Exception as exc:  # noqa: BLE001
        logger.warning("fast cue failed id=%s: %s", qa_id, exc)
        return {}


def _schedule_fast_cue_l1(qa_id: str, l0_payload: dict, live_pack, cfg, broadcast) -> None:
    """Optional L1: a small fast model rewrites the cue; L0 stays on failure."""
    idx = int(getattr(cfg, "fast_cue_model_index", -1) or -1)
    models = list(getattr(cfg, "models", []) or [])
    if idx < 0 or idx >= len(models):
        return

    def _worker() -> None:
        try:
            from services.intelligence import fast_cue
            from services.llm.streaming import get_client_for_model

            model_cfg = models[idx]
            client = get_client_for_model(model_cfg)
            resp = client.chat.completions.create(
                model=model_cfg.model,
                messages=[{"role": "system", "content": fast_cue.L1_SYSTEM}, *fast_cue.l1_messages(l0_payload.get("resolved_question") or l0_payload.get("question_raw", ""), l0_payload)],
                max_tokens=100,
                temperature=0.2,
                stream=False,
                timeout=4,
            )
            text = (resp.choices[0].message.content or "").strip() if resp.choices else ""
            corpus = " ".join([live_pack.profile_text, *[str(c.get("text", "")) for c in live_pack.claims]])
            cues = fast_cue.parse_l1(text, l0_payload, corpus)
            if cues:
                broadcast({**l0_payload, "cues": cues, "level": "L1"})
        except Exception:  # noqa: BLE001
            pass

    try:
        threading.Thread(target=_worker, name="fast-cue-l1", daemon=True).start()
    except Exception:  # noqa: BLE001
        pass


def process_question_parallel(
    task: TaskPayload,
    seq: int,
    model_idx: int,
    sess_v: int,
    deps: AnswerWorkerDeps,
):
    question_text, image, manual_input, source, meta = task
    exam_preflight_id = str(meta.get("exam_preflight_id") or "") if meta.get("exam_preflight") else ""
    qa_id = str(meta.get("qa_id") or "") or f"qa-{seq}-{int(time.time() * 1000)}"
    early_cue_emitted = bool(meta.get("early_cue_emitted"))

    def _broadcast(data: dict) -> None:
        if exam_preflight_id:
            data = {**data, "exam_preflight_id": exam_preflight_id}
        deps.broadcast(data)
        if exam_preflight_id:
            try:
                from .exam_test import record_exam_preflight_answer_event

                record_exam_preflight_answer_event(data)
            except Exception as exc:  # noqa: BLE001
                deps.error_logger.warning("exam preflight event record failed: %s", exc)

    # Prefer the dispatch-time snapshot.  Falling back to get_config keeps
    # this worker usable from older callers/tests that invoke it directly.
    cfg = deps.config_snapshot if deps.config_snapshot is not None else get_config()
    model_cfg = deps.model_cfg_snapshot
    if model_cfg is None and (model_idx < 0 or model_idx >= len(cfg.models)):
        deps.error_logger.warning(
            "ANSWER_MODEL_STALE id=%s seq=%d model_idx=%d model_count=%d",
            qa_id,
            seq,
            model_idx,
            len(cfg.models),
        )
        _broadcast(
            {
                "type": "answer_error",
                "id": qa_id,
                "stage": "generation",
                "message": "答题模型配置已变更，请重新提交问题。",
            }
        )
        deps.mark_seq_skipped(seq)
        return
    if model_cfg is None:
        model_cfg = cfg.models[model_idx]
    if deps.start_abort_check is not None and deps.start_abort_check():
        deps.mark_seq_skipped(seq)
        return

    # R2 Stage F: the frozen InterviewPack is the ONLY source of candidate /
    # job context on the Live path (never latest_job_id / latest resume).
    live_session_id = _live_session_id()
    live_pack = _resolve_live_pack(live_session_id, cfg)
    if not early_cue_emitted or meta.get("provisional_relation"):
        # With an early cue the turn clock already started at Q1 (group
        # confirmed) and G0 is recorded; restarting it would hide the grace.
        # A provisional cue started it at the partial: the authoritative
        # confirmation only moves Q1 (start_turn never resets E / G0).
        try:
            from services.intelligence import latency_clock as _lat

            confirmed = meta.get("question_confirmed_mono")
            _lat.start_turn(
                live_session_id,
                qa_id,
                q1=float(confirmed) if confirmed is not None else None,
                source=str(source or ""),
            )
        except Exception:  # noqa: BLE001
            pass

    # Stage P: AI policy gate — AI_FORBIDDEN disables realtime AI guidance
    # server-side (never by hiding a UI button). Prepare/Mock/Review are
    # unaffected because they never call this path.
    try:
        from services.intelligence.policy import live_guidance_allowed_for_pack, policy_block_payload

        if not live_guidance_allowed_for_pack(live_pack, cfg):
            deps.logger.info("POLICY_BLOCK id=%s mode=%s", qa_id, getattr(cfg, "ai_policy_mode", ""))
            _broadcast({**policy_block_payload(), "id": qa_id})
            deps.mark_seq_skipped(seq)
            return
    except Exception:  # noqa: BLE001
        # A policy-module failure must never block the realtime path.
        pass

    written_exam = bool(getattr(cfg, "written_exam_mode", False))
    written_exam_think = bool(getattr(cfg, "written_exam_think", False))
    prompt_mode = prompt_mode_for_task(source, manual_input, written_exam=written_exam)
    high_churn_short_answer = bool(meta.get("high_churn_short_answer", False))
    question_cluster = meta.get("question_cluster")
    if not isinstance(question_cluster, dict):
        question_cluster = {}
    question_type = str(
        meta.get("question_type")
        or question_cluster.get("question_type")
        or ""
    ).strip()
    relation_hint = str(question_cluster.get("relation_to_previous") or "").strip()
    parser_followup = relation_hint in {"follow_up", "followup", "continuation"}

    pack_notes = _pack_notes(live_pack, cfg)
    experience_grounding = analyze_experience_grounding(
        question_text,
        resume_text=live_pack.profile_text,
        interview_notes=pack_notes,
    ) if not written_exam else analyze_experience_grounding("")
    grounding_uses_model = experience_grounding.applicable and experience_grounding.status != "supported"
    profile_context_available = bool(live_pack.profile_text.strip() or pack_notes.strip())
    answer_engine_name = (
        "候选人事实约束"
        if experience_grounding.status == "supported"
        else model_cfg.name
    )
    display_model_name = "" if experience_grounding.status == "supported" else model_cfg.name

    kb_hits: list = []
    kb_latency_ms = 0
    kb_degraded = False
    if (
        bool(getattr(cfg, "kb_enabled", False))
        and not experience_grounding.applicable
        and prompt_mode in set(getattr(cfg, "kb_trigger_modes", []) or [])
        and (question_text or "").strip()
    ):
        try:
            from services.kb.retriever import retrieve as _kb_retrieve

            deadline_ms = (
                int(getattr(cfg, "kb_asr_deadline_ms", 80) or 80)
                if prompt_mode == PROMPT_MODE_ASR_REALTIME
                else int(getattr(cfg, "kb_deadline_ms", 150) or 150)
            )
            t0 = time.monotonic()
            prefetched = None
            if prompt_mode == PROMPT_MODE_ASR_REALTIME:
                try:
                    from services.intelligence import predictive

                    prefetched = predictive.take(live_session_id, question_text)
                except Exception:  # noqa: BLE001
                    prefetched = None
            if prefetched is not None:
                # Predictive Start: KB warmed from the partial and the stable
                # question still matches the hypothesis.
                kb_hits = list(prefetched.get("hits") or [])
            else:
                kb_hits = _kb_retrieve(
                    question_text,
                    k=int(getattr(cfg, "kb_top_k", 4) or 4),
                    deadline_ms=deadline_ms,
                    mode=prompt_mode,
                )
            kb_latency_ms = int((time.monotonic() - t0) * 1000)
        except Exception as exc:
            deps.error_logger.warning("kb retrieve in answer worker failed: %s", exc)
            kb_hits = []
            kb_degraded = True

    images = _normalize_task_images(image)

    if images:
        user_for_llm: Any = [
            {"type": "text", "text": question_text},
        ]
        for data_url in images:
            user_for_llm.append({"type": "image_url", "image_url": {"url": data_url}})
    else:
        user_for_llm = question_text

    with conversation_lock:
        session_ref = get_session()
        if written_exam:
            base_messages = []
            history_stats = {"messages": 0, "history_messages": 0, "stripped_images": 0}
            written_followup_context = (
                ""
                if exam_preflight_id
                else _written_exam_followup_context(
                    session_ref,
                    source=source,
                    image_count=len(images),
                )
            )
        else:
            history_options = _history_context_options(prompt_mode, written_exam)
            base_messages = list(session_ref.get_conversation_messages_for_llm(**history_options))
            history_stats = dict(getattr(session_ref, "last_llm_history_stats", {}) or {})
            written_followup_context = ""
        last_qa = session_ref.get_last_qa()
        recent_qas = list(session_ref.qa_pairs[-5:])
        memo_context = _build_memo_context(session_ref)
        candidate_context_enabled, candidate_wait_ms, candidate_max_chars, candidate_min_chars = _candidate_context_settings(cfg)
        candidate_source_ok = _supports_candidate_context_source(source, meta)
        should_use_candidate_context = bool(
            not written_exam
            and not images
            and last_qa
            and candidate_source_ok
            and candidate_context_enabled
        )
        actual_spoken_answer = (
            session_ref.get_candidate_answer_for_qa(last_qa.id, max_chars=candidate_max_chars)
            if last_qa
            and should_use_candidate_context
            else ""
        )

    if should_use_candidate_context and last_qa:
        _wait_for_candidate_context_if_pending(session_ref, last_qa.id, candidate_wait_ms)
        with conversation_lock:
            actual_spoken_answer = session_ref.get_candidate_answer_for_qa(
                last_qa.id,
                max_chars=candidate_max_chars,
            )
    if len(actual_spoken_answer.strip()) < candidate_min_chars:
        actual_spoken_answer = ""
    candidate_context_chars = len(actual_spoken_answer[:candidate_max_chars]) if actual_spoken_answer else 0

    is_followup = False
    followup_needs_bridge = False
    if (
        not written_exam
        and not images
        and last_qa
        and _supports_candidate_context_source(source, meta)
        and (
            parser_followup
            or classify_followup(
                question_text,
                last_qa.question,
                actual_spoken_answer or last_qa.answer[:500],
            )
        )
    ):
        is_followup = True
        followup_needs_bridge = _followup_needs_bridge(question_text)
        prev_answer_budget = 0
        prev_answer_summary = ""
        if followup_needs_bridge:
            prev_answer_budget = max(160, min(280, candidate_max_chars // 3 if candidate_max_chars > 0 else 160))
            prev_answer_summary = _context_excerpt(last_qa.answer, prev_answer_budget)
        if not followup_needs_bridge:
            user_for_llm = (
                f"[追问上下文] 上一个问题：{last_qa.question}\n"
                "当前追问已经自带比较完整的对象、条件和要问点。只把上一轮当作主题锚点，"
                "不要重复上一轮助手建议答案，也不要硬套候选人上一轮项目细节、示例或量化结果。\n\n"
                f"现在面试官追问：{question_text}"
            )
        elif not candidate_context_enabled:
            user_for_llm = (
                f"[追问上下文] 上一个问题：{last_qa.question}\n"
                f"你上次回答的要点：{prev_answer_summary}\n\n"
                f"现在面试官追问：{question_text}"
            )
        else:
            actual_block = (
                f"候选人麦克风转写（辅助参考，可能有识别误差）：{actual_spoken_answer[:candidate_max_chars]}\n"
                if actual_spoken_answer
                else "候选人麦克风转写：未启用或未捕获到；本轮按旧逻辑仅参考助手建议答案。\n"
            )
            user_for_llm = (
                f"[追问上下文] 上一个问题：{last_qa.question}\n"
                f"{actual_block}"
                f"助手上一轮建议答案（参考候选人可能听到过的答题方向，不代表候选人照读）：{prev_answer_summary}\n"
                "追问回答规则：以当前面试官追问和会议音频识别出的题意为主；"
                "候选人麦克风转写用于理解上一轮回答大意，但不要当作逐字稿。"
                "如果转写内容明显识别错、与当前追问冲突或不自然，请降权使用，不要强行套入。\n\n"
                f"现在面试官追问：{question_text}"
            )
    elif (
        should_use_candidate_context
        and last_qa
        and actual_spoken_answer
        and _candidate_background_matches_current_question(question_text, last_qa, actual_spoken_answer)
    ):
        user_for_llm = (
            f"[候选人回答辅助背景] 上一个问题：{last_qa.question}\n"
            f"候选人上一轮麦克风转写（可能有识别误差）：{actual_spoken_answer[:candidate_max_chars]}\n"
            "使用规则：这段转写可帮助延续候选人上一轮回答的大意、项目线索和技术关键词；"
            "以当前面试官问题为主，如果当前问题与上一轮无关，或转写明显不准，请忽略或弱化它。"
            "不得假设候选人照读了助手上一轮建议答案，也不要把转写当成逐字事实。\n\n"
            f"现在面试官问题：{question_text}"
        )

    # Parser relation is useful when an ASR group starts with a short
    # continuation that the lexical follow-up classifier cannot score on its
    # own.  It still respects the existing self-contained-question rule: only
    # bridge the previous answer for a compact/ambiguous continuation, never
    # dump unrelated history into a complete new question.
    if parser_followup:
        is_followup = True
        followup_needs_bridge = followup_needs_bridge or _followup_needs_bridge(question_text)

    # Non-follow-up turns may still be a continuation of a topic discussed a
    # few questions ago.  Include a bounded bridge only when lexical anchors
    # agree; this lets the model connect the candidate's earlier answer and
    # the interviewer's wording without turning every turn into a long chat
    # history.  Follow-ups use the purpose-built branch above so existing
    # candidate-ASR safeguards remain intact.
    conversation_bridge = ""
    if not written_exam and not images and not is_followup:
        candidate_for_bridge = actual_spoken_answer
        if (
            actual_spoken_answer
            and last_qa
            and _candidate_background_matches_current_question(
                question_text,
                last_qa,
                actual_spoken_answer,
            )
        ):
            # The existing candidate-background block below already carries
            # this transcript with its stronger ASR caveat.  Avoid duplicating
            # it in the generic bridge while still bridging prior Q&A words.
            candidate_for_bridge = ""
        conversation_bridge = build_conversation_bridge(
            question_text,
            recent_qas=recent_qas,
            candidate_answer=candidate_for_bridge,
            relation_to_previous=relation_hint,
        )
        if conversation_bridge:
            if isinstance(user_for_llm, list):
                user_for_llm.insert(0, {"type": "text", "text": conversation_bridge})
            else:
                user_for_llm = f"{conversation_bridge}\n\n{user_for_llm}"

    if prompt_mode == PROMPT_MODE_ASR_REALTIME and is_followup:
        base_messages = []
        history_stats = _empty_history_stats(
            "asr_followup_bridge" if followup_needs_bridge else "asr_followup_anchor_only"
        )

    structured_question_prompt = str(meta.get("structured_question_prompt") or "").strip()
    if structured_question_prompt:
        if isinstance(user_for_llm, list):
            user_for_llm.insert(0, {"type": "text", "text": structured_question_prompt})
        else:
            user_for_llm = f"{structured_question_prompt}\n\n{user_for_llm}"

    grounding_contract = experience_grounding.prompt_contract()
    if grounding_contract:
        if isinstance(user_for_llm, list):
            user_for_llm.insert(0, {"type": "text", "text": grounding_contract})
        else:
            user_for_llm = f"{grounding_contract}\n{user_for_llm}"

    if written_followup_context:
        if isinstance(user_for_llm, list):
            if user_for_llm and isinstance(user_for_llm[0], dict) and user_for_llm[0].get("type") == "text":
                user_for_llm[0] = {
                    **user_for_llm[0],
                    "text": f"{written_followup_context}\n\n[当前截图/题面]\n{question_text}",
                }
            else:
                user_for_llm.insert(
                    0,
                    {
                        "type": "text",
                        "text": f"{written_followup_context}\n\n[当前截图/题面]\n{question_text}",
                    },
                )
        else:
            user_for_llm = f"{written_followup_context}\n\n[当前题面]\n{question_text}"

    with conversation_lock:
        session_ref.close_candidate_answer_window()

    answer_depth_profile = classify_answer_depth(
        question_text,
        question_type=question_type,
        relation_to_previous=("follow_up" if is_followup else relation_hint),
        high_churn_short_answer=high_churn_short_answer,
    )
    # ----------------- Intelligence Core (v1.0-R1) -----------------
    # Stage D/H/E: 21-type understanding + structured plan + incremental state.
    # Strictly additive: existing grounding/followup/candidate-ASR safeguards
    # above keep running; failures degrade to the legacy path.
    intelligence_layer: dict = {}
    compiler_authoritative_enabled = bool(getattr(cfg, "intelligence_context_compiler_v1", True)) and bool(
        getattr(cfg, "intelligence_compiler_authoritative", True)
    )
    if bool(getattr(cfg, "intelligence_answer_planner_v1", True)):
        try:
            from services.intelligence.realtime_bridge import build_intelligence_layer

            intelligence_layer = build_intelligence_layer(
                question_text,
                previous_question=last_qa.question if last_qa else "",
                relation_to_previous=("follow_up" if is_followup else relation_hint),
                session_ref=session_ref,
                session_id=live_session_id,
                grounding_status=experience_grounding.status,
                interviewer_state_enabled=bool(getattr(cfg, "interviewer_state_enabled", False)),
                pack=live_pack,
            )
            intel_plan_prompt = str(intelligence_layer.get("plan_prompt") or "")
            intel_state_context = str(intelligence_layer.get("state_context") or "")
            compiler_will_own_state = compiler_authoritative_enabled and not written_exam and not images
            if intel_state_context and not written_exam and not images and not compiler_will_own_state:
                if isinstance(user_for_llm, list):
                    user_for_llm.insert(0, {"type": "text", "text": intel_state_context})
                else:
                    user_for_llm = f"{intel_state_context}\n{user_for_llm}"
            # Written-exam keeps its fixed message contract (revision context +
            # 题面 only); the plan prompt is for the live spoken path.
            if intel_plan_prompt and not written_exam and not images:
                if isinstance(user_for_llm, list):
                    user_for_llm.insert(0, {"type": "text", "text": intel_plan_prompt})
                else:
                    user_for_llm = f"{intel_plan_prompt}\n{user_for_llm}"
        except Exception as exc:  # noqa: BLE001
            deps.error_logger.warning("intelligence layer failed id=%s: %s", qa_id, exc)
            intelligence_layer = {}

    # ----------------- Context Compiler (R2 Stage G: the one authority) -----------------
    # Providers read the frozen InterviewPack; the compiled package replaces
    # (not adds to) the legacy resume / KB / memo / JD prompt sections.
    compiler_ok = False
    compiler_fallback = False
    compiled_items: list = []
    compile_stats: dict = {}
    session_claim_block = ""
    if bool(getattr(cfg, "intelligence_context_compiler_v1", True)) and not written_exam and not images:
        try:
            from services.intelligence.context_compiler import compile_live_context
            from services.intelligence.session_claims import prompt_constraints

            intel_state = intelligence_layer.get("state") or {}
            compiled, compiled_sections = compile_live_context(
                live_pack,
                question_text,
                memo_context=str(memo_context or ""),
                compact_state=str(intelligence_layer.get("state_context") or ""),
                kb_hits=kb_hits,
                deep=answer_depth_profile in {"deep", "compact_deep"},
                active_topic=str(intel_state.get("current_topic", "") or ""),
                session_id=live_session_id,
            )
            compiled_items = list(compiled.items)
            session_claim_block = prompt_constraints(live_session_id)
            blocks = []
            if compiled_sections:
                blocks.append("[编译上下文：最小充分包]\n" + "\n".join(compiled_sections))
            if session_claim_block:
                blocks.append(session_claim_block)
            voice_line = _voice_line(live_pack)
            if voice_line:
                blocks.append(voice_line)
            if blocks:
                section_block = "\n".join(blocks)
                if isinstance(user_for_llm, list):
                    user_for_llm.insert(0, {"type": "text", "text": section_block})
                else:
                    user_for_llm = f"{section_block}\n{user_for_llm}"
            compiler_ok = compiler_authoritative_enabled
            compile_stats = {
                "items": len(compiled.items),
                "tokens": compiled.total_token_estimate,
                "duplicates_dropped": sum(1 for d in compiled.dropped if d.get("reason") == "duplicate_fragment"),
                "latency_ms": compiled.latency_ms,
                "pack_id": live_pack.id,
                "pack_frozen": live_pack.frozen,
            }
            deps.logger.info(
                "CONTEXT_COMPILED id=%s pack=%s frozen=%s items=%d tokens=%d dup_dropped=%d latency=%dms",
                qa_id,
                live_pack.id or "-",
                live_pack.frozen,
                len(compiled.items),
                compiled.total_token_estimate,
                compile_stats["duplicates_dropped"],
                compiled.latency_ms,
            )
        except Exception as exc:  # noqa: BLE001
            compiler_fallback = True
            deps.error_logger.warning("context compiler failed id=%s (compiler_fallback=true): %s", qa_id, exc)
            # Explicit failure only: restore the state context the compiler
            # would have carried, then let the legacy prompt sections run.
            fallback_state = str(intelligence_layer.get("state_context") or "")
            if fallback_state and compiler_authoritative_enabled:
                if isinstance(user_for_llm, list):
                    user_for_llm.insert(0, {"type": "text", "text": fallback_state})
                else:
                    user_for_llm = f"{fallback_state}\n{user_for_llm}"

    system_prompt = build_system_prompt(
        manual_input=manual_input,
        mode=prompt_mode,
        screen_region=getattr(cfg, "screen_capture_region", "left_half"),
        high_churn_short_answer=high_churn_short_answer,
        kb_hits=kb_hits or None,
        include_resume=(
            False
            if experience_grounding.status == "supported"
            else True
            if experience_grounding.applicable and profile_context_available
            else _should_include_resume_context(
                prompt_mode,
                question_text,
                last_qa=last_qa,
                is_followup=is_followup,
                followup_needs_bridge=followup_needs_bridge,
            )
        ),
        memo_context=memo_context,
        question_text=question_text,
        question_type=question_type,
        answer_depth_profile=answer_depth_profile,
        relation_to_previous=("follow_up" if is_followup else relation_hint),
        context_authoritative=compiler_ok,
        pack_notes=pack_notes,
        position_override=str(live_pack.job.get("title", "") or ""),
    )

    messages_for_llm = base_messages + [{"role": "user", "content": user_for_llm}]
    # DeepSeek 前缀缓存预热：与真实请求同前缀，仅 1 token，不阻塞回答链路。
    try:
        if experience_grounding.status != "supported":
            schedule_prefix_cache_warmup(
                [{"role": "system", "content": system_prompt}] + list(base_messages),
                model_cfg=model_cfg,
            )
    except Exception:  # noqa: BLE001
        pass
    deps.logger.info(
        "LLM_INPUT_STATS source=%s prompt_mode=%s written_exam=%s image_count=%d "
        "image_payload_chars=%d history_used=%s history_profile=%s history_messages=%d "
        "historical_images_stripped=%d history_text_raw_chars=%d "
        "history_text_trimmed_chars=%d candidate_context_chars=%d "
        "message_count=%d text_chars=%d grounding_status=%s grounding_subject=%r "
        "answer_depth=%s conversation_bridge_chars=%d",
        source,
        prompt_mode,
        written_exam,
        len(images),
        _image_payload_chars(images),
        bool(base_messages),
        str(history_stats.get("profile", "default")),
        int(history_stats.get("history_messages", 0) or 0),
        int(history_stats.get("stripped_images", 0) or 0),
        int(history_stats.get("raw_text_chars", 0) or 0),
        int(history_stats.get("trimmed_text_chars", 0) or 0),
        candidate_context_chars,
        len(messages_for_llm),
        _message_text_chars(messages_for_llm),
        experience_grounding.status,
        experience_grounding.subject,
        answer_depth_profile,
        len(conversation_bridge),
    )

    configured_display_question = str(meta.get("display_question") or "").strip()
    if configured_display_question:
        display_question = configured_display_question
    elif len(images) > 1:
        display_question = f"{question_text} [📷 多图 x{len(images)}]"
    else:
        display_question = question_text + (" [📷 附图]" if images else "")
    deps.logger.info(
        "ANSWER_START id=%s model=%s source=%s followup=%s q=%r",
        qa_id,
        answer_engine_name,
        source,
        is_followup,
        question_text[:120],
    )
    _broadcast(
        {
            "type": "answer_start",
            "id": qa_id,
            "question": display_question,
            "source": source,
            "model_name": display_model_name,
            "model_index": model_idx,
            "question_cluster": meta.get("question_cluster"),
            "question_type": meta.get("question_type"),
            "answer_depth": answer_depth_profile,
            "cluster_index": meta.get("cluster_index"),
            "cluster_count": meta.get("cluster_count"),
            "fact_grounding": experience_grounding.public_payload(),
        }
    )
    fast_cue_payload: dict = {}
    if bool(getattr(cfg, "intelligence_fast_cue_v2", True)) and not written_exam and not images:
        # Re-emitted even after an early cue: the resolved question may have
        # gained a late constraint; G0 keeps the first (earliest) timestamp.
        fast_cue_payload = _emit_fast_cue(
            qa_id=qa_id,
            question_text=question_text,
            intelligence_layer=intelligence_layer,
            compiled_items=compiled_items,
            kb_hits=kb_hits,
            live_pack=live_pack,
            session_claim_block=session_claim_block,
            cfg=cfg,
            broadcast=_broadcast,
            logger=deps.error_logger,
        )

    # 面试官问题内联翻译（可选，默认关）：并行翻一句，不阻塞回答。
    if (
        bool(getattr(cfg, "assist_inline_translation_enabled", False))
        and prompt_mode in (PROMPT_MODE_ASR_REALTIME, PROMPT_MODE_MANUAL_TEXT)
        and not images
        and (question_text or "").strip()
    ):
        _schedule_question_translation(qa_id, question_text, model_cfg, deps.broadcast)
    # 候选人回答窗口用于下一轮上下文、知识记录或后续手动复盘；只要候选人 ASR 开启就绑定 qa_id。
    should_open_candidate_window = (
        _supports_candidate_context_source(source, meta)
        and (
            candidate_context_enabled
            or bool(getattr(cfg, "candidate_asr_enabled", False))
        )
    )
    if should_open_candidate_window:
        with conversation_lock:
            get_session().open_candidate_answer_window(qa_id)

    if kb_hits or kb_degraded:
        try:
            from services.kb.ws import build_kb_hits_payload as _kb_payload

            deps.broadcast(
                _kb_payload(
                    qa_id=qa_id,
                    hits=kb_hits,
                    latency_ms=kb_latency_ms,
                    degraded=kb_degraded,
                    excerpt_chars=int(
                        getattr(cfg, "kb_prompt_excerpt_chars", 300) or 300
                    ),
                )
            )
        except Exception as exc:
            deps.error_logger.warning("broadcast kb_hits failed: %s", exc)

    raw_full_answer = ""
    stream_sanitizer = create_answer_stream_sanitizer(prompt_mode)
    # Model-backed experience answers are buffered until the factual guard has
    # checked the complete response; otherwise a hallucinated first sentence
    # could already have been shown to the candidate.
    strict_grounding_buffer = grounding_uses_model
    stream_guard = None
    if bool(getattr(cfg, "intelligence_fast_cue_v2", True)) and not written_exam and not images:
        try:
            from services.intelligence.stream_guard import StreamTruthGuard

            stream_guard = StreamTruthGuard(
                assertion_policy=str(((intelligence_layer.get("plan") or {}).get("metadata") or {}).get("assertion_policy", "REQUIRE_BOUNDARY")),
                boundary_subject=str(experience_grounding.subject or "") if grounding_uses_model else "",
                evidence_texts=[live_pack.profile_text, pack_notes, *[str(c.get("text", "")) for c in live_pack.claims], *[str(e.get("text", "")) for e in live_pack.evidence_refs]],
            )
            # Sentence-level guard replaces whole-answer buffering: risky
            # first-person spans are held per sentence, the rest streams.
            strict_grounding_buffer = False
        except Exception as exc:  # noqa: BLE001
            deps.error_logger.warning("stream guard init failed id=%s: %s", qa_id, exc)
            stream_guard = None
    full_think = ""
    token_prompt_delta = 0
    token_completion_delta = 0

    def _record_usage(prompt_tokens: int, completion_tokens: int, _model_name: str) -> None:
        nonlocal token_prompt_delta, token_completion_delta
        token_prompt_delta += int(prompt_tokens or 0)
        token_completion_delta += int(completion_tokens or 0)

    exam_think_notified = False
    gen_start = time.monotonic()
    # User-facing "首字" latency means the first answer token, not a hidden
    # reasoning token.  This matters for written-exam mode where Think output
    # may arrive seconds before any usable code/answer text.
    first_token_mono: Optional[float] = None
    chunk_buffer: list[str] = []
    batch_size = 5
    # Stage Q: fast_guidance_started — the deterministic layers (plan/state/
    # grounding) are already committed to the prompt; the LLM stream starts
    # now. first_useful_guidance is recorded after the first token below.
    if bool(getattr(cfg, "intelligence_live_cue_v1", True)):
        try:
            from services.intelligence.telemetry import record_guidance_event as _rec_fgs

            _rec_fgs(
                str((intelligence_layer.get("state") or {}).get("session_id", "") or "default"),
                "fast_guidance_started",
                route=str((intelligence_layer.get("plan") or {}).get("mode", "") or prompt_mode),
                provider=str(getattr(model_cfg, "name", "") or ""),
                model=str(getattr(model_cfg, "model", "") or ""),
            )
        except Exception:  # noqa: BLE001
            pass
    try:
        think_override = None
        if prompt_mode in (PROMPT_MODE_ASR_REALTIME, PROMPT_MODE_MANUAL_TEXT) and not bool(
            getattr(cfg, "assist_realtime_think_enabled", False)
        ):
            # Spoken answers must be fast and oral: disable hidden reasoning
            # unless the user explicitly enables it for realtime answers.
            think_override = False
        elif prompt_mode == PROMPT_MODE_WRITTEN_EXAM and (source or "").startswith("server_screen_"):
            think_override = written_exam_think
        if experience_grounding.status == "supported":
            # A concrete personal-history question is a factual lookup.  Emit
            # the naturalized evidence immediately; free-form model prose is
            # reserved for project deep-dives and technical questions, where
            # it adds value without deciding whether the candidate did it.
            answer_stream = [("text", experience_grounding.direct_answer())]
        else:
            answer_stream = chat_stream_single_model(
                model_cfg,
                messages_for_llm,
                system_prompt=system_prompt,
                abort_check=deps.abort_check,
                override_think_mode=think_override,
                usage_callback=_record_usage,
                override_max_tokens=_max_tokens_for_prompt(
                    prompt_mode,
                    cfg,
                    high_churn_short_answer=high_churn_short_answer,
                    answer_depth_profile=answer_depth_profile,
                ),
            )
        for chunk_type, chunk_text in answer_stream:
            if deps.abort_check():
                break
            if chunk_type == "think":
                full_think += chunk_text
                if prompt_mode == PROMPT_MODE_WRITTEN_EXAM:
                    if not exam_think_notified:
                        exam_think_notified = True
                        _broadcast(
                            {
                                "type": "answer_think_chunk",
                                "id": qa_id,
                                "chunk": "思考中...",
                            }
                        )
                else:
                    _broadcast(
                        {
                            "type": "answer_think_chunk",
                            "id": qa_id,
                            "chunk": chunk_text,
                        }
                    )
            else:
                if first_token_mono is None and chunk_text:
                    first_token_mono = time.monotonic()
                    _lat_mark(qa_id, "A0", first_token_mono)
                raw_full_answer += chunk_text
                if strict_grounding_buffer:
                    continue
                clean_chunk = stream_sanitizer.push(chunk_text)
                if stream_guard is not None and clean_chunk:
                    clean_chunk = stream_guard.feed(clean_chunk)
                if clean_chunk:
                    chunk_buffer.append(clean_chunk)
                    if len(chunk_buffer) >= batch_size:
                        _broadcast(
                            {"type": "answer_chunk", "id": qa_id, "chunk": "".join(chunk_buffer)}
                        )
                        chunk_buffer.clear()
        if chunk_buffer and not strict_grounding_buffer:
            _broadcast({"type": "answer_chunk", "id": qa_id, "chunk": "".join(chunk_buffer)})
            chunk_buffer.clear()
    except Exception as exc:
        deps.error_logger.error(
            "LLM stream error id=%s: %s",
            qa_id,
            exc,
            exc_info=not isinstance(exc, LLMError),
        )
        # Stage Q: provider_fallback telemetry event (generation failure).
        if bool(getattr(cfg, "intelligence_live_cue_v1", True)):
            try:
                from services.intelligence.telemetry import record_guidance_event as _rec_pf

                _rec_pf(
                    str((intelligence_layer.get("state") or {}).get("session_id", "") or "default"),
                    "provider_fallback",
                    route=str((intelligence_layer.get("plan") or {}).get("mode", "") or prompt_mode),
                    provider=str(getattr(model_cfg, "name", "") or ""),
                    model=str(getattr(model_cfg, "model", "") or ""),
                )
            except Exception:  # noqa: BLE001
                pass
        if chunk_buffer:
            _broadcast({"type": "answer_chunk", "id": qa_id, "chunk": "".join(chunk_buffer)})
            chunk_buffer.clear()
        tail = "" if strict_grounding_buffer else stream_sanitizer.finish()
        if tail:
            _broadcast({"type": "answer_chunk", "id": qa_id, "chunk": tail})
        message = (
            exc.user_msg
            if isinstance(exc, LLMError)
            else "生成答案失败，请稍后重试。"
        )
        _broadcast({
            "type": "answer_error",
            "id": qa_id,
            "stage": "generation",
            "message": message,
        })
        # The commit queue must advance past a failed generation, but the
        # failed answer itself must never be written as a successful QA pair.
        deps.mark_seq_skipped(seq)
        return

    gen_elapsed = (time.monotonic() - gen_start) * 1000
    _lat_mark(qa_id, "D0")
    latency_metrics = _lat_finish(qa_id)
    first_token_ms = (
        (first_token_mono - gen_start) * 1000 if first_token_mono else gen_elapsed
    )

    # Stage J/Q: TTFUG telemetry — first USEFUL guidance is the first answer
    # token for the candidate; deep completion is recorded separately in commit.
    if bool(getattr(cfg, "intelligence_live_cue_v1", True)):
        try:
            from services.intelligence.telemetry import record_guidance_event

            record_guidance_event(
                str((intelligence_layer.get("state") or {}).get("session_id", "") or "default"),
                "first_useful_guidance",
                route=str((intelligence_layer.get("plan") or {}).get("mode", "") or prompt_mode),
                provider=str(getattr(model_cfg, "name", "") or ""),
                model=str(getattr(model_cfg, "model", "") or ""),
                latency_ms=int(first_token_ms),
            )
        except Exception:  # noqa: BLE001
            pass

    if deps.abort_check():
        deps.logger.info("ANSWER_CANCEL id=%s after=%.0fms", qa_id, gen_elapsed)
        _broadcast({"type": "answer_cancelled", "id": qa_id})
        deps.mark_seq_skipped(seq)
        return

    guarded_post_audit = stream_guard is not None and grounding_uses_model
    if strict_grounding_buffer or guarded_post_audit:
        if guarded_post_audit:
            tail = stream_sanitizer.finish()
            tail = (stream_guard.feed(tail) if tail else "") + stream_guard.flush()
            if tail:
                _broadcast({"type": "answer_chunk", "id": qa_id, "chunk": tail})
        full_answer = postprocess_answer_for_mode(raw_full_answer, prompt_mode)
        full_answer, grounding_replaced = enforce_experience_answer(
            full_answer,
            experience_grounding,
        )
        if grounding_replaced:
            deps.logger.warning(
                "ANSWER_FACT_GUARD_REPLACED id=%s status=%s subject=%r",
                qa_id,
                experience_grounding.status,
                experience_grounding.subject,
            )
        # Unified Truth Boundary post-check (Stage B): additional violation
        # detection (internal leakage, unexpected metric, subject substitution)
        # WITHOUT weakening the deterministic grounding above — violations the
        # grounding already accepted are never re-flagged here.
        if bool(getattr(cfg, "intelligence_answer_planner_v1", True)):
            try:
                from services.intelligence.truth_boundary import (
                    TruthBoundary,
                    check_generated_answer,
                    classify_output_space,
                    map_grounding_status,
                )

                truth_result = check_generated_answer(
                    full_answer,
                    boundary=TruthBoundary(
                        grounding=experience_grounding,
                        output_space=classify_output_space(experience_grounding),
                        truth_status=map_grounding_status(experience_grounding.status),
                    ),
                    evidence_texts=[experience_grounding.evidence_excerpt] if experience_grounding.evidence_excerpt else [],
                    question_text=question_text,
                )
                if truth_result.fallback_used and truth_result.final_text:
                    full_answer = truth_result.final_text
                    grounding_replaced = True
                    deps.logger.warning(
                        "TRUTH_BOUNDARY_REWRITE id=%s violations=%s",
                        qa_id,
                        [v.get("kind") for v in truth_result.violations],
                    )
                    # Stage Q: truth_rewrite telemetry event.
                    try:
                        from services.intelligence.telemetry import record_guidance_event as _rec_tr

                        _rec_tr(
                            str((intelligence_layer.get("state") or {}).get("session_id", "") or "default"),
                            "truth_rewrite",
                            route=str((intelligence_layer.get("plan") or {}).get("mode", "") or prompt_mode),
                            truth_flags=[str(v.get("kind", "")) for v in truth_result.violations],
                        )
                    except Exception:  # noqa: BLE001
                        pass
            except Exception as exc:  # noqa: BLE001
                deps.error_logger.warning("truth boundary check failed id=%s: %s", qa_id, exc)
        if full_answer and not guarded_post_audit:
            _broadcast({"type": "answer_chunk", "id": qa_id, "chunk": full_answer})
    else:
        tail = stream_sanitizer.finish()
        if stream_guard is not None:
            tail = (stream_guard.feed(tail) if tail else "") + stream_guard.flush()
        if tail:
            _broadcast({"type": "answer_chunk", "id": qa_id, "chunk": tail})
        full_answer = postprocess_answer_for_mode(raw_full_answer, prompt_mode)
        if stream_guard is not None and stream_guard.rewrites:
            # The final text must match what the guard showed: apply the
            # same sentence rewrites to the committed answer.
            full_answer = _apply_guard_rewrites(full_answer, stream_guard)
    if not full_answer.strip():
        deps.error_logger.warning(
            "ANSWER_EMPTY id=%s model=%s source=%s think_len=%d raw_len=%d",
            qa_id,
            answer_engine_name,
            source,
            len(full_think),
            len(raw_full_answer),
        )
        _broadcast(
            {
                "type": "answer_error",
                "id": qa_id,
                "stage": "generation",
                "message": "模型未返回有效答案，请重试或更换模型。",
            }
        )
        deps.mark_seq_skipped(seq)
        return

    def _commit():
        if not deps.is_session_current(sess_v):
            return
        session = get_session()
        if exam_preflight_id:
            stats = get_token_stats()
            deps.logger.info(
                "EXAM_PREFLIGHT_ANSWER_DONE id=%s model=%s first_token=%.0fms total=%.0fms answer_len=%d",
                qa_id,
                answer_engine_name,
                first_token_ms,
                gen_elapsed,
                len(full_answer),
            )
            _broadcast(
                {
                    "type": "answer_done",
                    "id": qa_id,
                    "question": display_question,
                    "answer": full_answer,
                    "think": full_think,
                    "model_name": display_model_name,
                    "first_token_ms": int(first_token_ms),
                    "total_ms": int(gen_elapsed),
                }
            )
            deps.broadcast(
                {
                    "type": "token_update",
                    "prompt": stats["prompt"],
                    "completion": stats["completion"],
                    "total": stats["total"],
                    "by_model": stats.get("by_model", {}),
                }
            )
            return
        pre_user_len = len(session.conversation_history)
        pre_qa_len = len(session.qa_pairs)
        try:
            with conversation_lock:
                if images:
                    suffix = f" [图片已省略 x{len(images)}]"
                    session.add_user_message(question_text + suffix)
                else:
                    session.add_user_message(question_text)
                session.add_assistant_message(full_answer)
                session.add_qa(
                    display_question,
                    full_answer,
                    qa_id=qa_id,
                    source=source,
                    model_name=display_model_name,
                )
            stats = get_token_stats()
            deps.logger.info(
                "ANSWER_DONE id=%s model=%s first_token=%.0fms total=%.0fms "
                "answer_len=%d think_len=%d tokens_prompt_delta=%d tokens_completion_delta=%d "
                "tokens_prompt=%d tokens_completion=%d",
                qa_id,
                answer_engine_name,
                first_token_ms,
                gen_elapsed,
                len(full_answer),
                len(full_think),
                token_prompt_delta,
                token_completion_delta,
                stats["prompt"],
                stats["completion"],
            )
            _broadcast(
                {
                    "type": "answer_done",
                    "id": qa_id,
                    "question": display_question,
                    "answer": full_answer,
                    "think": full_think,
                    "model_name": display_model_name,
                    "first_token_ms": int(first_token_ms),
                    "total_ms": int(gen_elapsed),
                    # GuidanceViewModel payload (Stage K): glance-first data;
                    # components consume this instead of raw prompt responses.
                    "guidance": {
                        "core_ideas": list((intelligence_layer.get("plan") or {}).get("structure", []) or [])[:6],
                        "evidence": (
                            [experience_grounding.evidence_excerpt[:160]]
                            if experience_grounding.evidence_excerpt
                            else []
                        ),
                        "mode": str((intelligence_layer.get("plan") or {}).get("mode", "") or ""),
                        "intent": list((intelligence_layer.get("plan") or {}).get("intent", []) or [])[:3],
                        "resolved_question": str((intelligence_layer.get("understanding") or {}).get("resolved_question", "") or ""),
                        "state_context": str(intelligence_layer.get("state_context") or ""),
                        "fast_cue": fast_cue_payload,
                        "context": {**compile_stats, "compiler_fallback": compiler_fallback},
                        "stream_guard_rewrites": int(stream_guard.rewrites) if stream_guard is not None else 0,
                    },
                    "latency": latency_metrics,
                }
            )
            # Stage Q: committed turn telemetry + route event (never breaks the
            # realtime path); guidance is never written as a candidate fact.
            if bool(getattr(cfg, "intelligence_live_cue_v1", True)):
                try:
                    from services.intelligence.realtime_bridge import record_committed_turn

                    record_committed_turn(
                        str((intelligence_layer.get("state") or {}).get("session_id", "") or "default"),
                        seq=seq,
                        question_raw=question_text[:200],
                        question_resolved=str((intelligence_layer.get("understanding") or {}).get("resolved_question", "") or "")[:200],
                        question_type=str((intelligence_layer.get("understanding") or {}).get("question_type", "") or ""),
                        route=str((intelligence_layer.get("plan") or {}).get("mode", "") or ""),
                        guidance_text=full_answer[:200],
                        latency_ms=int(gen_elapsed),
                        answer_plan=intelligence_layer.get("plan") or {},
                    )
                except Exception:  # noqa: BLE001
                    pass
            _save_turn_trace(
                qa_id=qa_id,
                session_id=live_session_id,
                pack=live_pack,
                question_text=question_text,
                intelligence_layer=intelligence_layer,
                fast_cue_payload=fast_cue_payload,
                compiled_items=compiled_items,
                compile_stats={**compile_stats, "compiler_fallback": compiler_fallback},
                latency_metrics=latency_metrics,
                provider=str(display_model_name or answer_engine_name or ""),
                model=str(getattr(model_cfg, "model", "") or ""),
                stream_guard=stream_guard,
            )
            deps.broadcast(
                {
                    "type": "token_update",
                    "prompt": stats["prompt"],
                    "completion": stats["completion"],
                    "total": stats["total"],
                    "by_model": stats.get("by_model", {}),
                }
            )
            if (
                bool(getattr(cfg, "assist_suggestion_enabled", False))
                and not experience_grounding.applicable
            ):
                try:
                    _schedule_answer_suggestion(
                        qa_id,
                        display_question,
                        full_answer,
                        model_cfg,
                        deps.broadcast,
                    )
                except Exception:  # noqa: BLE001
                    pass
            candidate_answer_for_record = ""
            with conversation_lock:
                candidate_answer_for_record = session.get_candidate_answer_for_qa(
                    qa_id,
                    max_chars=2400,
                )
            if not deps.submit_knowledge_record(question_text, full_answer, qa_id, candidate_answer_for_record):
                deps.error_logger.warning(
                    "KNOWLEDGE_ENQUEUE_DROP id=%s question=%r",
                    qa_id,
                    question_text[:80],
                )
            if prompt_mode in (PROMPT_MODE_SERVER_SCREEN, PROMPT_MODE_WRITTEN_EXAM) and images:
                try:
                    from services.vision_verify import schedule_self_verify

                    schedule_self_verify(
                        qa_id=qa_id,
                        answer=full_answer,
                        image_data_url=images,
                        broadcast_callable=deps.broadcast,
                    )
                except Exception as exc: # noqa: BLE001
                    deps.error_logger.warning(
                        "VISION_VERIFY_SCHEDULE_FAIL id=%s err=%s",
                        qa_id,
                        exc,
                    )
        except Exception as exc:
            with conversation_lock:
                if len(session.qa_pairs) > pre_qa_len:
                    session.qa_pairs.pop()
                if len(session.conversation_history) > pre_user_len:
                    del session.conversation_history[pre_user_len:]
            deps.error_logger.error(
                "_commit failed for id=%s seq=%d: %s",
                qa_id, seq, exc, exc_info=True,
            )
            _broadcast({
                "type": "answer_error",
                "id": qa_id,
                "stage": "persistence",
                "message": "答案保存失败",
            })

    deps.flush_commit(seq, _commit)
