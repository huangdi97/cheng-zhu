"""Content Coach and Delivery Coach (canonical §12) — kept strictly separate.

Content Coach judges *what* was said; Delivery Coach judges *how*. Neither
produces a single score.

 INVARIANTS:
  - Every content finding quotes the candidate's actual speech
    (``evidence_from_actual_speech`` is a substring of the answer). An AI
    answer / cue / reference is never passed in or quoted as the user's
    performance — callers pass only the candidate's transcript.
  - Delivery output is actionable sentences + raw local metrics, never a
    "delivery score". Delivery analytics run locally on text + timings;
    no audio leaves the device.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Optional

from services.product.rubrics import SIGNAL_TO_DIMENSION

CONTENT_SIGNALS = ("did_answer_question", "truth_boundary", "technical_depth", "structure",
                   "trade_off", "ownership", "evidence", "followup_resilience")

_SENTENCE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
_TOKEN = re.compile(r"[一-鿿]{2,}|[A-Za-z][A-Za-z0-9+#.\-]{1,}")
_NUMBER = re.compile(r"\d+(?:\.\d+)?\s*(?:%|倍|万|千|亿|ms|毫秒|秒|s\b|QPS|qps|TPS|x|X|人|天|周|个月|GB|MB|TB)?")
_TRADE = re.compile(r"(取舍|权衡|代价|trade[- ]?off|缺点|但是|不过|相比|而不是|选择了|放弃了|折中|成本)", re.I)
_STRUCTURE = re.compile(r"(首先|其次|最后|第一|第二|第三|一是|二是|总结|结论是|总的来说|简单说|分为|两点|三点|三个方面)")
_CONCLUSION = re.compile(r"(结论是|我的答案是|简单说|总的来说|核心是|我会|我选择|我们最终|关键在于|答案是)")
_OWN_I = re.compile(r"我(?!们)")
_OWN_WE = re.compile(r"我们")
_STRONG_OWNERSHIP = re.compile(r"(我负责|我主导|我设计|我搭建|我推动|由我|我独立|我牵头|我从零)")
_TECH = re.compile(
    r"(缓存|索引|事务|分布式|一致性|并发|锁|队列|分片|副本|延迟|吞吐|RAG|Agent|向量|检索|重排|微调|评测|"
    r"Redis|Kafka|MySQL|Postgre|Kubernetes|Docker|gRPC|HTTP|TCP|LLM|Transformer|Embedding|Prompt|"
    r"算法|复杂度|架构|服务|接口|数据库|模型|特征|指标|实验|召回|准确率)", re.I)
_FILLER_ZH = ("嗯", "呃", "那个", "就是说", "然后呢", "怎么说呢", "对吧", "其实吧")
_FILLER_EN = re.compile(r"\b(um+|uh+|erm|like|you know|i mean|basically|actually)\b", re.I)
_SCRIPT_MARKERS = re.compile(r"(综上所述|由此可见|值得注意的是|首先，|其次，|此外，|总而言之|与此同时)")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.findall(text or "") if len(s.strip()) >= 2]


def _first_match_sentence(sentences: list[str], pattern: re.Pattern[str]) -> Optional[str]:
    for sentence in sentences:
        if pattern.search(sentence):
            return sentence[:120]
    return None


def _quote(sentences: list[str], fallback: str) -> str:
    return (sentences[0] if sentences else fallback.strip())[:120]


def _keywords(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN.findall(text or "") if len(t) >= 2}


# ---------------------------------------------------------------------------
# Content Coach
# ---------------------------------------------------------------------------


def analyze_content(
    question: str,
    answer: str,
    *,
    move: str = "OPEN",
    known_claims: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Deterministic content analysis of the candidate's own answer.

    ``known_claims``: the candidate's claims with provenance; strong ownership
    language about a topic that has no supporting claim becomes a
    truth-boundary finding (not an accusation — a prompt to add a source or
    soften wording).
    """
    answer = (answer or "").strip()
    sentences = _sentences(answer)
    q_terms = _keywords(question)
    a_terms = _keywords(answer)
    overlap = len(q_terms & a_terms) / max(1, len(q_terms)) if q_terms else 0.5
    numbers = _NUMBER.findall(answer)
    numbers = [n for n in numbers if re.search(r"\d", n)]
    tech_hits = _TECH.findall(answer)
    i_count, we_count = len(_OWN_I.findall(answer)), len(_OWN_WE.findall(answer))

    levels: dict[str, int] = {}
    findings: list[dict[str, Any]] = []

    def finding(signal: str, level: int, text: str, quote: str, action: str) -> None:
        levels[signal] = level
        if level <= 2:
            findings.append({"signal": signal, "dimension": SIGNAL_TO_DIMENSION[signal], "level": level,
                             "finding": text, "evidence_from_actual_speech": quote, "action": action})

    if not answer:
        return {"signals": {s: 1 for s in CONTENT_SIGNALS}, "findings": [{
            "signal": "did_answer_question", "dimension": "technical_correctness", "level": 1,
            "finding": "这一题没有作答。", "evidence_from_actual_speech": "", "action": "先用一句话给出结论，再补一个例子。",
        }], "strengths": [], "kind": "CONTENT"}

    answered = 4 if overlap >= 0.5 else 3 if overlap >= 0.3 else 2 if overlap >= 0.12 else 1
    finding("did_answer_question", answered, "回答和问题的关键词重合较少，可能没有正面回答。",
            _quote(sentences, answer), "第一句直接回应问题里的关键词，再展开。")

    depth = 4 if len(tech_hits) >= 5 else 3 if len(tech_hits) >= 3 else 2 if tech_hits else 1
    finding("technical_depth", depth, "技术细节偏少，停留在概念层。", _quote(sentences, answer),
            "补一个具体机制（数据结构、参数、失败场景）说明你是怎么做的。")

    has_structure = bool(_STRUCTURE.search(answer)) or len(sentences) <= 3
    concl_first = bool(sentences) and bool(_CONCLUSION.search(" ".join(sentences[:2])))
    structure = 4 if has_structure and concl_first else 3 if has_structure or concl_first else 2
    finding("structure", structure, "结论出现得晚，结构不清晰。", _quote(sentences, answer),
            "先说结论，再用「第一 / 第二」展开两到三点。")

    trade_sentence = _first_match_sentence(sentences, _TRADE)
    trade = 4 if trade_sentence and len(_TRADE.findall(answer)) >= 2 else 3 if trade_sentence else 1
    finding("trade_off", trade, "没有说明方案的取舍或代价。", _quote(sentences, answer),
            "补一句：为什么选这个方案、放弃了什么、代价是什么。")

    strong_own = _first_match_sentence(sentences, _STRONG_OWNERSHIP)
    if strong_own:
        ownership = 4
    elif i_count >= we_count and i_count > 0:
        ownership = 3
    elif i_count > 0:
        ownership = 2
    else:
        ownership = 1
    finding("ownership", ownership, "多用「我们」，听不出你本人做了什么。",
            _first_match_sentence(sentences, _OWN_WE) or _quote(sentences, answer),
            "把「我们」换成你自己负责的动作：我设计了…、我决定…。")

    evidence = 4 if len(numbers) >= 2 else 3 if numbers else 1
    finding("evidence", evidence, "缺少可量化的结果或证据。", _quote(sentences, answer),
            "加一个数字：延迟、规模、提升比例或节省的时间。")

    truth_level = 4
    if strong_own and known_claims is not None:
        supported = any(_keywords(c.get("text", "")) & _keywords(strong_own) and
                        str(c.get("provenance_status") or c.get("truth_status") or "") in
                        ("DIRECT_EVIDENCE", "SUPPORTING_EVIDENCE", "SUPPORTED", "VERIFIED")
                        for c in known_claims)
        if not supported:
            truth_level = 2
    finding("truth_boundary", truth_level, "这句主导性表述在你的材料里还没有来源支持。",
            strong_own or "", "在「我的成竹 · 待确认」里补来源，或改成「我参与了…」。")

    if move in ("FOLLOW_UP", "CHALLENGE", "CONTRADICTION_PROBE", "CONSTRAINT_CHANGE", "OWNERSHIP_PROBE", "QUANTIFY"):
        resilient = 4 if answered >= 3 and (numbers or trade_sentence) else 3 if answered >= 3 else 2
        finding("followup_resilience", resilient, "被追问时回到了原有说法，没有补充新信息。",
                _quote(sentences, answer), "追问时先承认问题，再给一个新细节或边界。")
    else:
        levels["followup_resilience"] = levels.get("followup_resilience", 3)

    strengths = [
        {"signal": s, "dimension": SIGNAL_TO_DIMENSION[s],
         "evidence_from_actual_speech": (_first_match_sentence(sentences, _TRADE) if s == "trade_off" else
                                         strong_own if s == "ownership" and strong_own else _quote(sentences, answer))}
        for s, lvl in levels.items() if lvl >= 4
    ][:3]
    # every quote must come from the candidate's own speech
    for item in findings + strengths:
        quote = item.get("evidence_from_actual_speech") or ""
        if quote and quote not in answer:
            item["evidence_from_actual_speech"] = ""
    return {"signals": levels, "findings": findings, "strengths": strengths, "kind": "CONTENT"}


def rubric_levels(content: dict[str, Any]) -> dict[str, int]:
    return {SIGNAL_TO_DIMENSION[s]: int(v) for s, v in (content.get("signals") or {}).items()
            if s in SIGNAL_TO_DIMENSION}


# ---------------------------------------------------------------------------
# Delivery Coach
# ---------------------------------------------------------------------------


def analyze_delivery(
    answer: str,
    *,
    duration_ms: Optional[int] = None,
    word_timestamps: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Local delivery metrics + actionable advice. No score."""
    text = (answer or "").strip()
    chars = len(re.sub(r"\s+", "", text))
    duration_s = (duration_ms or 0) / 1000.0
    if duration_s <= 0 and chars:
        duration_s = chars / 4.0  # ~240 chars/min conversational Mandarin when timing is unknown
        timing_estimated = True
    else:
        timing_estimated = False
    rate_cpm = round(chars / duration_s * 60, 0) if duration_s > 0 else 0.0

    sentences = _sentences(text)
    conclusion_idx = next((i for i, s in enumerate(sentences) if _CONCLUSION.search(s)), None)
    if conclusion_idx is None:
        time_to_conclusion = None
    else:
        before = sum(len(s) for s in sentences[:conclusion_idx])
        time_to_conclusion = round(before / max(1, chars) * duration_s, 1)

    fillers = sum(text.count(f) for f in _FILLER_ZH) + len(_FILLER_EN.findall(text))
    grams = Counter(text[i:i + 4] for i in range(max(0, len(text) - 3)) if not re.search(r"\s", text[i:i + 4]))
    repetition = sum(c - 1 for g, c in grams.items() if c >= 3 and len(set(g)) > 1)

    pauses_long = 0
    if word_timestamps:
        for prev, cur in zip(word_timestamps, word_timestamps[1:]):
            gap = float(cur.get("start", 0)) - float(prev.get("end", 0))
            if gap >= 1.5:
                pauses_long += 1
    else:
        pauses_long = text.count("……") + text.count("...")

    overlong = duration_s > 150 or chars > 700
    script_markers = len(_SCRIPT_MARKERS.findall(text))
    possible_script = chars > 250 and fillers == 0 and script_markers >= 2

    metrics = {
        "answer_duration_s": round(duration_s, 1),
        "timing_estimated": timing_estimated,
        "chars": chars,
        "speech_rate_cpm": rate_cpm,
        "time_to_conclusion_s": time_to_conclusion,
        "long_pauses": pauses_long,
        "fillers": fillers,
        "repetition": repetition,
        "overlong_answer": overlong,
        "possible_script_reading": possible_script,
    }
    advice: list[str] = []
    if time_to_conclusion is None and chars > 80:
        advice.append("没有听到明确的结论句；下一题先用一句「结论是…」开头。")
    elif time_to_conclusion is not None and time_to_conclusion > 15:
        advice.append(f"结论在约 {time_to_conclusion:.0f} 秒后才出现；做一次 15 秒结论训练。")
    if rate_cpm and rate_cpm > 320:
        advice.append("语速偏快，关键数字前停半拍。")
    elif rate_cpm and 0 < rate_cpm < 140 and not timing_estimated:
        advice.append("语速偏慢，可以先说结论再补细节，减少思考停顿。")
    if fillers >= 5:
        advice.append(f"口头填充词出现 {fillers} 次；用短暂停顿代替「嗯 / 那个」。")
    if repetition >= 3:
        advice.append("有重复表述，一个要点说一次即可。")
    if overlong:
        advice.append("回答偏长（超过 2.5 分钟），控制在 90 秒内，细节留给追问。")
    if possible_script:
        advice.append("听起来可能在照稿读；试着只看要点，用自己的话说。")
    return {"kind": "DELIVERY", "metrics": metrics, "advice": advice}


def summarize_delivery(per_turn: list[dict[str, Any]]) -> list[str]:
    """Cross-turn actionable delivery summary (e.g. average time to conclusion)."""
    ttcs = [m["metrics"]["time_to_conclusion_s"] for m in per_turn
            if m.get("metrics", {}).get("time_to_conclusion_s") is not None]
    out: list[str] = []
    if len(ttcs) >= 2:
        avg = sum(ttcs[:3]) / len(ttcs[:3])
        if avg > 12:
            out.append(f"前 {min(3, len(ttcs))} 次回答结论平均在 {avg:.0f} 秒后出现；下一轮做 15 秒结论训练。")
    missing = sum(1 for m in per_turn if m.get("metrics", {}).get("time_to_conclusion_s") is None
                  and m.get("metrics", {}).get("chars", 0) > 80)
    if missing >= 2:
        out.append(f"{missing} 次回答没有明确结论句。")
    fillers = sum(m.get("metrics", {}).get("fillers", 0) for m in per_turn)
    if fillers >= 8:
        out.append(f"整场口头填充词 {fillers} 次。")
    if sum(1 for m in per_turn if m.get("metrics", {}).get("overlong_answer")) >= 2:
        out.append("多次回答超过 2.5 分钟。")
    return out
