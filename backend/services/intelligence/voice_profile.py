"""Personal voice profile built from REAL candidate speech (never from
assistant-generated answers, which would teach the model to imitate itself).
Statistics are deterministic aggregations; no LLM calls, no fabricated facts.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, fields

from core.logger import get_logger
from services.intelligence.types import VoiceProfileData

_log = get_logger(__name__)

_VOICE_BOUNDARY_LINE = "以下仅为表达风格要求，不得改变事实边界与个人经历的真实性。"
# Deterministic defaults; the user may extend them via explicit_preferences.
_DEFAULT_CLICHES: tuple[str, ...] = ("作为一个AI", "总的来说", "综上所述")
_CLICHE_LIST_CAP = 8
# First-sentence markers: conclusion-style vs context-first openings.
_CONCLUSION_MARKERS: tuple[str, ...] = ("我", "直接回答", "结论", "用过", "做过", "是")
_CONTEXT_MARKERS: tuple[str, ...] = ("背景", "当时", "首先", "嗯", "那个")
# First-person + verb starts counting as direct speech ("我用了/我负责").
_FIRST_PERSON_VERB_STARTS: tuple[str, ...] = ("我用了", "我做了", "我负责", "我实现", "我设计", "我搭建", "我主导", "我写")
_FILLER_WORDS: tuple[str, ...] = ("嗯", "呃", "那个", "就是", "uh", "um", "like")
_TECH_TOKEN_RE = re.compile(
    r"python|java|javascript|typescript|sql|api|docker|kubernetes|k8s|redis|mysql"
    r"|postgres|linux|git|react|vue|spring|django|fastapi|torch|grpc|http|aws",
    re.IGNORECASE,
)
_ASCII_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#]*")
_LENGTH_HINTS = {"short": "尽量简短（60字以内）", "medium": "中等篇幅（60-180字）", "long": "可以充分展开（180字以上）"}


def _first_sentence(sample: str) -> str:
    """First non-empty sentence of one sample."""
    for part in re.split(r"[。！？!?\n；;]", sample):
        if part.strip():
            return part.strip()
    return sample.strip()


def _first_sentence_style(samples: list[str]) -> str:
    conclusion = sum(1 for s in samples if _first_sentence(s).startswith(_CONCLUSION_MARKERS))
    context = sum(1 for s in samples if _first_sentence(s).startswith(_CONTEXT_MARKERS))
    return "context_first" if context > conclusion else "conclusion_first"


def _directness(samples: list[str]) -> float:
    """Ratio of samples whose first sentence starts first-person + verb."""
    hits = sum(1 for s in samples if _first_sentence(s).startswith(_FIRST_PERSON_VERB_STARTS))
    return hits / len(samples)


def _technical_density(samples: list[str]) -> float:
    """ASCII-alnum character share blended with explicit tech-term hits;
    pure-CJK small talk stays near 0, English-heavy tech talk near 1."""
    total = sum(len(s) for s in samples)
    ascii_chars = sum(1 for s in samples for ch in s if ch.isascii() and not ch.isspace())
    tech_hits = sum(len(_TECH_TOKEN_RE.findall(s)) for s in samples)
    return min(1.0, ascii_chars / total + 0.3 * min(1.0, tech_hits / len(samples)))


def _filler_tendency(samples: list[str]) -> float:
    """Filler occurrences over CJK-char + ascii-word token count; in [0, 1]."""
    filler = sum(sample.count(word) for sample in samples for word in _FILLER_WORDS)
    tokens = sum(sum(1 for ch in sample if "\u4e00" <= ch <= "\u9fff") + len(_ASCII_WORD_RE.findall(sample)) for sample in samples)
    return min(1.0, filler / tokens) if tokens else 0.0


def _language(samples: list[str]) -> str:
    """Language by CJK/ASCII letter ratio; precondition: samples non-empty."""
    total = sum(len(s) for s in samples)
    cjk = sum(1 for s in samples for ch in s if "\u4e00" <= ch <= "\u9fff")
    ascii_letters = sum(1 for s in samples for ch in s if ch.isascii() and ch.isalpha())
    if cjk / total >= 0.7:
        return "zh-CN"
    if ascii_letters / total >= 0.7:
        return "en"
    return "mixed"


def _merged_cliches(explicit: dict | None) -> list[str]:
    merged = list(_DEFAULT_CLICHES)
    for item in (explicit or {}).get("forbidden_cliches", []):
        if item and item not in merged:
            merged.append(item)
    return merged


def build_voice_profile(samples: list[str], *, candidate_id: str,
                        explicit_preferences: dict | None = None) -> VoiceProfileData:
    """Aggregate voice statistics over real candidate speech samples only
    (Chinese + English). Blank samples are dropped; no samples yields the
    dataclass defaults with sample_count=0."""
    clean = [sample for sample in samples if sample and sample.strip()]
    explicit = dict(explicit_preferences or {})
    cliches = _merged_cliches(explicit)
    if not clean:
        return VoiceProfileData(candidate_id=candidate_id, forbidden_cliches=cliches,
                                explicit_preferences=explicit, sample_count=0, enabled=False)
    avg_length = sum(len(sample) for sample in clean) / len(clean)
    length_hint = "short" if avg_length < 60 else "medium" if avg_length <= 180 else "long"
    return VoiceProfileData(
        candidate_id=candidate_id, answer_length_hint=length_hint,
        first_sentence_style=_first_sentence_style(clean), directness=_directness(clean),
        technical_density=_technical_density(clean), filler_tendency=_filler_tendency(clean),
        language=_language(clean), forbidden_cliches=cliches,
        explicit_preferences=explicit, sample_count=len(clean), enabled=False,
    )


def apply_voice(profile: VoiceProfileData | None, plan_prompt: str) -> str:
    """Append a bounded style-only directive block when the profile is enabled;
    otherwise return plan_prompt unchanged. The block itself states the fact
    boundary and never rewrites facts."""
    if profile is None or not profile.enabled:
        return plan_prompt
    style_hint = "结论先行，直接回答" if profile.first_sentence_style == "conclusion_first" else "先简短铺垫背景，再给结论"
    lines = [
        "[表达风格要求]",
        _VOICE_BOUNDARY_LINE,
        f"- 首句习惯：{style_hint}",
        f"- 长度提示：{_LENGTH_HINTS.get(profile.answer_length_hint, _LENGTH_HINTS['medium'])}",
        f"- 直接度：{profile.directness:.1f}（越高越先给结论）",
    ]
    if profile.forbidden_cliches:
        lines.append("- 禁用模板短语：" + "、".join(profile.forbidden_cliches[:_CLICHE_LIST_CAP]))
    block = "\n".join(lines)
    return (plan_prompt + "\n" + block) if plan_prompt else block


def save_voice_profile(candidate_id: str, profile: VoiceProfileData) -> None:
    """Persist via storage.intelligence; failures log a warning, never raise."""
    from services.storage.intelligence import save_voice_profile as _storage_save

    try:
        _storage_save(candidate_id, json.dumps(asdict(profile), ensure_ascii=False),
                      profile.sample_count, profile.enabled)
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        _log.warning("voice profile save failed (candidate=%s): %s", candidate_id, exc)


def load_voice_profile(candidate_id: str) -> VoiceProfileData | None:
    """Load the stored profile; None when absent or unreadable."""
    from services.storage.intelligence import get_voice_profile as _storage_get

    try:
        row = _storage_get(candidate_id)
    except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
        _log.warning("voice profile load failed (candidate=%s): %s", candidate_id, exc)
        return None
    data = (row or {}).get("profile")
    if not isinstance(data, dict):
        return None
    known = {f.name for f in fields(VoiceProfileData)} - {"candidate_id"}
    payload = {key: value for key, value in data.items() if key in known}
    stored_id = str(data.get("candidate_id") or (row or {}).get("candidate_id") or candidate_id)
    return VoiceProfileData(candidate_id=stored_id, **payload)
