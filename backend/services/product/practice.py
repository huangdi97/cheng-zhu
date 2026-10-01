"""Practice 3.0 — adaptive interviewer, personas, panel turn-taking (canonical §10).

The next question is decided by Goal, round, persona, demeanor, difficulty,
the content of the current answer, the Goal's Question Graph, recent
weakness (Next Focus) and open threads. It is never a fixed playlist: each
answer is analysed (Content Coach) and the weakest signal picks a move —
follow-up, challenge, constraint change, ownership probe, quantify, clarify,
contradiction probe — within a follow-up budget set by demeanor and
difficulty. The final question is a closing question.

Panel: 2–3 personas share one session. Exactly one persona speaks per turn;
a follow-up stays with the persona that asked, a new topic passes to the
next persona whose domain fits, and each persona keeps its own concern.

Sessions are persisted in product.db (practice_session / practice_turn) so a
restart does not lose a practice in progress.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from core.logger import get_logger
from services.product import coach, events
from services.product import question_banks as banks
from services.storage import product as store

_log = get_logger("product.practice")

ROUNDS = banks.ROUNDS
ROUND_LABELS = {"TECHNICAL": "技术面", "PROJECT_DEEP_DIVE": "项目深挖", "SYSTEM_DESIGN": "系统设计",
                "HIRING_MANAGER": "Hiring Manager", "HR": "HR 面", "BEHAVIORAL": "行为面", "PRODUCT_CASE": "产品 / Case"}
DEMEANORS = ("NEUTRAL", "FRIENDLY", "SKEPTICAL", "STRONG_FOLLOWUP", "FAST_PACED")
DIFFICULTIES = ("WARMUP", "STANDARD", "PRESSURE")
SOURCES = ("GOAL_GRAPH", "RECENT_WEAKNESS", "MY_BANK", "ROLE_BANK")
MOVES = ("OPEN", "FOLLOW_UP", "CHALLENGE", "CONSTRAINT_CHANGE", "OWNERSHIP_PROBE", "QUANTIFY", "CLARIFY",
         "CONTRADICTION_PROBE", "CLOSING")
MIN_QUESTIONS, MAX_QUESTIONS = 1, 15

PERSONAS: dict[str, dict[str, Any]] = {
    "TECH_LEAD": {"label": "技术负责人", "priority": 1, "demeanor": "SKEPTICAL",
                  "domain": ("system_design", "performance", "scalability", "cache", "database", "distributed", "rag",
                             "agent", "latency", "retrieval", "evaluation", "incident", "modeling", "technical"),
                  "followup_style": "追问实现细节、失败场景和取舍", "concern": "技术深度是否经得起追问"},
    "HIRING_MANAGER": {"label": "招聘经理", "priority": 2, "demeanor": "NEUTRAL",
                       "domain": ("ownership", "impact", "conflict", "influence", "prioritization", "learning",
                                  "engineering_practice", "failure", "ambiguity"),
                       "followup_style": "追问你本人的贡献和结果", "concern": "是否真正独立负责过、能否带来结果"},
    "PRODUCT_PARTNER": {"label": "产品合作方", "priority": 3, "demeanor": "FRIENDLY",
                        "domain": ("metrics", "product_design", "trade_off", "ux_fallback", "judgement", "analysis",
                                   "communication"),
                        "followup_style": "追问用户价值、指标和取舍", "concern": "能否把技术和业务价值连起来"},
    "HR_PARTNER": {"label": "HR", "priority": 4, "demeanor": "FRIENDLY",
                   "domain": ("motivation", "closing", "learning"),
                   "followup_style": "了解动机和期望", "concern": "动机和稳定性"},
    "PEER_ENGINEER": {"label": "同级工程师", "priority": 2, "demeanor": "NEUTRAL",
                      "domain": ("coding", "debugging", "engineering_practice", "testing", "database", "cache"),
                      "followup_style": "追问代码和调试细节", "concern": "日常协作中的工程质量"},
    "BAR_RAISER": {"label": "交叉面试官", "priority": 2, "demeanor": "STRONG_FOLLOWUP",
                   "domain": ("failure", "ambiguity", "learning", "conflict", "ownership"),
                   "followup_style": "连续追问直到具体", "concern": "标准是否高于团队平均"},
}
_ROUND_PERSONA = {"TECHNICAL": "TECH_LEAD", "PROJECT_DEEP_DIVE": "TECH_LEAD", "SYSTEM_DESIGN": "TECH_LEAD",
                  "HIRING_MANAGER": "HIRING_MANAGER", "HR": "HR_PARTNER", "BEHAVIORAL": "HIRING_MANAGER",
                  "PRODUCT_CASE": "PRODUCT_PARTNER"}
_FOLLOWUP_BUDGET = {"FRIENDLY": 1, "NEUTRAL": 1, "SKEPTICAL": 2, "STRONG_FOLLOWUP": 3, "FAST_PACED": 1}
_DIFFICULTY_BUDGET = {"WARMUP": -1, "STANDARD": 0, "PRESSURE": 1}
_FOLLOWUP_MOVES = set(MOVES) - {"OPEN", "CLOSING"}

_TEMPLATES_ZH = {
    "FOLLOW_UP": "你提到了{term}，具体是怎么做的？当时遇到的最大问题是什么？",
    "CHALLENGE": "为什么一定要用{term}？换一个更简单的方案，会差在哪里？",
    "CONSTRAINT_CHANGE": "假设流量再涨 10 倍、预算砍半，你刚才的方案哪里要改？",
    "OWNERSHIP_PROBE": "这件事里，哪些决定是你本人做的？其他同事各负责什么？",
    "QUANTIFY": "能给一个具体数字吗？比如{term}前后的延迟、规模或提升比例。",
    "CLARIFY": "我想确认一下：对于「{topic}」，你的直接回答是什么？",
    "CONTRADICTION_PROBE": "你刚才说「{quote}」，前面听起来是团队一起做的——你具体主导的是哪一块？",
    "CLOSING": "我这边差不多了，你有什么想问我们的吗？",
    "OPEN_THREAD": "前面你提到过{term}，可以展开讲讲吗？",
}
_TEMPLATES_EN = {
    "FOLLOW_UP": "You mentioned {term}. How exactly did you do it, and what was the hardest part?",
    "CHALLENGE": "Why {term} specifically? What would a simpler alternative lose?",
    "CONSTRAINT_CHANGE": "Suppose traffic grows 10x and the budget is halved. What changes in your design?",
    "OWNERSHIP_PROBE": "Which decisions here were yours personally, and what did others own?",
    "QUANTIFY": "Can you put a number on it, e.g. latency, scale or improvement around {term}?",
    "CLARIFY": "Just to confirm: what is your direct answer on \"{topic}\"?",
    "CONTRADICTION_PROBE": "You said \"{quote}\", but earlier it sounded like a team effort. Which part did you lead?",
    "CLOSING": "That's all from my side. Do you have any questions for us?",
    "OPEN_THREAD": "Earlier you mentioned {term}. Could you expand on that?",
}
_DEMEANOR_PREFIX_ZH = {"FRIENDLY": "好的，", "SKEPTICAL": "嗯，我有点疑问。", "STRONG_FOLLOWUP": "继续往下说。",
                       "FAST_PACED": "", "NEUTRAL": ""}
_TERM = re.compile(r"(Redis|Kafka|MySQL|PostgreSQL|RAG|Agent|向量检索|向量|重排|微调|缓存|分布式锁|消息队列|一致性|分库分表|"
                   r"索引|事务|限流|降级|熔断|Kubernetes|K8s|Docker|Embedding|Prompt|评测|A/B|实验|指标|召回|"
                   r"[A-Z][A-Za-z0-9+#.]{2,})")
_WEAKNESS_TEMPLATES = {
    "KNOWLEDGE_GAP": "谈谈你对「{title}」的理解；如果让你落地，你会怎么做？",
    "SYSTEM_DESIGN": "围绕「{title}」设计一个方案，说明关键取舍。",
    "OWNERSHIP": "挑一个你最有把握的项目，讲讲其中完全由你负责的那部分。",
    "STORY_GAP": "讲一个体现「{title}」的真实经历。",
    "FACT_BOUNDARY": "关于「{title}」，你具体做到了哪一步？哪些是团队完成的？",
    "DELIVERY": "用 30 秒介绍你最近的一个项目，第一句先说结论。",
    "FOLLOWUP_RESILIENCE": "讲讲「{title}」，我会连续追问。",
    "CODING": "说说你会怎么实现「{title}」，时间和空间复杂度是多少？",
    "CLOSING_QUESTION": "假设面试进入尾声，你准备反问面试官哪两个问题？为什么是这两个？",
    "USER_PIN": "{title}",
    "RUBRIC": "讲一个能体现「{title}」的项目细节。",
}
_GRAPH_KIND_ROUND = {"PROJECT_DEEP_DIVE": "PROJECT_DEEP_DIVE", "KNOWLEDGE": "TECHNICAL",
                     "EXPERIENCE_BOUNDARY": "PROJECT_DEEP_DIVE", "OPEN_DESIGN": "SYSTEM_DESIGN"}


class PracticeError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def normalize_config(raw: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(raw or {})
    round_name = cfg.get("round") or "TECHNICAL"
    if round_name not in ROUNDS:
        raise PracticeError(f"未知轮次：{round_name}")
    demeanor = cfg.get("demeanor") or "NEUTRAL"
    if demeanor not in DEMEANORS:
        raise PracticeError(f"未知面试官风格：{demeanor}")
    difficulty = cfg.get("difficulty") or "STANDARD"
    if difficulty not in DIFFICULTIES:
        raise PracticeError(f"未知难度：{difficulty}")
    sources = [s for s in (cfg.get("sources") or ["GOAL_GRAPH", "RECENT_WEAKNESS", "ROLE_BANK"]) if s in SOURCES]
    if not sources:
        raise PracticeError("至少选择一个题目来源")
    personas = [p for p in (cfg.get("personas") or []) if p in PERSONAS]
    if not personas:
        personas = [_ROUND_PERSONA.get(round_name, "TECH_LEAD")]
    if len(personas) > 3:
        raise PracticeError("面试官最多 3 位")
    questions = int(cfg.get("questions") or 5)
    if not MIN_QUESTIONS <= questions <= MAX_QUESTIONS:
        raise PracticeError(f"题目数量需在 {MIN_QUESTIONS}–{MAX_QUESTIONS} 之间")
    language = cfg.get("language") or "zh"
    if language not in ("zh", "en"):
        raise PracticeError("练习语言只支持 zh / en")
    return {"goal_id": cfg.get("goal_id") or None, "round": round_name, "demeanor": demeanor,
            "difficulty": difficulty, "sources": sources, "personas": list(dict.fromkeys(personas)),
            "questions": questions, "language": language, "human_coach": bool(cfg.get("human_coach")),
            "focus": cfg.get("focus") or None, "guided": bool(cfg.get("guided")),
            "delivery_analytics": bool(cfg.get("delivery_analytics", True)),
            "closing": bool(cfg.get("closing", questions >= 3))}


def _item(text: str, source: str, category: str = "", label: str = "", round_hint: str = "") -> dict[str, Any]:
    return {"text": text.strip(), "source": source, "category": category, "label": label, "round": round_hint}


def _focus_item(focus: dict[str, Any]) -> Optional[dict[str, Any]]:
    template = _WEAKNESS_TEMPLATES.get(str(focus.get("type") or ""), _WEAKNESS_TEMPLATES["RUBRIC"])
    title = str(focus.get("title") or "").strip()
    if not title:
        return None
    return _item(template.format(title=title[:40]), "RECENT_WEAKNESS", str(focus.get("type") or "").lower(),
                 f"Next Focus：{title[:30]}")


def build_pool(cfg: dict[str, Any], goal: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    round_name, difficulty = cfg["round"], cfg["difficulty"]
    if cfg.get("focus"):
        item = _focus_item(cfg["focus"])
        if item:
            pool.append(item)
    if "RECENT_WEAKNESS" in cfg["sources"] and goal:
        from services.product.next_focus import active_items

        for focus in active_items(goal["id"]):
            item = _focus_item(focus)
            if item:
                pool.append(item)
    if "GOAL_GRAPH" in cfg["sources"] and goal:
        pool.extend(_graph_items(goal, round_name))
    if "MY_BANK" in cfg["sources"]:
        bank_ids = list((goal or {}).get("active_question_bank_ids") or [])
        bank_ids += [b["id"] for b in banks.list_banks(goal_id=(goal or {}).get("id", "")) if not b["builtin"]
                     and b["id"] not in bank_ids]
        for q in banks.pool(bank_ids, round_name, difficulty):
            pool.append(_item(q["text"], "MY_BANK", q["category"], q["label"]))
    if "ROLE_BANK" in cfg["sources"]:
        family = (goal or {}).get("role_family") or "SWE"
        for q in banks.pool([banks.role_bank_id(family)], round_name, difficulty):
            pool.append(_item(q["text"], "ROLE_BANK", q["category"], q["label"]))
    if not pool:
        # the role bank has nothing tagged for this round: use it unfiltered rather than fail
        family = (goal or {}).get("role_family") or "SWE"
        for q in banks.pool([banks.role_bank_id(family)], "", difficulty):
            pool.append(_item(q["text"], "ROLE_BANK", q["category"], q["label"]))
    seen: set[str] = set()
    unique = []
    for item in pool:
        key = re.sub(r"\s+", "", item["text"])
        if item["text"] and key not in seen and not re.search(r"(想问我们|想问的)", item["text"]):
            seen.add(key)
            unique.append(item)
    return unique


def _graph_items(goal: dict[str, Any], round_name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from services.product.workspace import goal_workspace

        for node in goal_workspace(goal).get("question_graph") or []:
            if node.get("parent_id"):
                continue
            node_round = _GRAPH_KIND_ROUND.get(str(node.get("kind")), "")
            if node_round and round_name in ("TECHNICAL", "PROJECT_DEEP_DIVE", "SYSTEM_DESIGN") and \
                    node_round != round_name and round_name != "TECHNICAL":
                continue
            out.append(_item(str(node.get("text") or ""), "GOAL_GRAPH", str(node.get("kind") or "").lower(),
                             "来自目标的 Question Graph"))
    except Exception as exc:  # noqa: BLE001
        _log.debug("question graph unavailable: %s", exc)
    space_id = goal.get("legacy_prep_space_id")
    if space_id:
        try:
            from services.storage import prep_space

            for q in (prep_space.get_space(int(space_id)) or {}).get("questions") or []:
                text = str(q.get("question") or "") if isinstance(q, dict) else ""
                if text:
                    out.append(_item(text, "GOAL_GRAPH", str(q.get("type") or ""), "目标预测题（AI 生成，非真实面经）"))
        except Exception as exc:  # noqa: BLE001
            _log.debug("prep questions unavailable: %s", exc)
    return out


# ---------------------------------------------------------------------------
# Panel turn-taking
# ---------------------------------------------------------------------------


def _persona_for(item: dict[str, Any], personas: list[str], current: str) -> str:
    """Next speaker for a *new* topic: domain fit first, then rotation."""
    if len(personas) == 1:
        return personas[0]
    order = sorted(personas, key=lambda p: PERSONAS[p]["priority"])
    start = (order.index(current) + 1) % len(order) if current in order else 0
    rotated = order[start:] + order[:start]
    category = item.get("category") or ""
    for persona in rotated:
        if category and category in PERSONAS[persona]["domain"]:
            return persona
    return rotated[0]


def _panel_state(state: dict[str, Any]) -> dict[str, Any]:
    personas = state["personas"]
    return {
        "personas": [{"id": p, "label": PERSONAS[p]["label"], "concern": PERSONAS[p]["concern"],
                      "followup_style": PERSONAS[p]["followup_style"],
                      "demeanor": state["persona_demeanor"].get(p, PERSONAS[p]["demeanor"])} for p in personas],
        "current_speaker": state["current_speaker"],
        "next_speaker": state.get("next_speaker") or state["current_speaker"],
        "shared_topic": state.get("topic", ""),
        "concerns": state.get("concerns", {}),
        "is_panel": len(personas) > 1,
    }


# ---------------------------------------------------------------------------
# Adaptive move selection
# ---------------------------------------------------------------------------


def followup_budget(demeanor: str, difficulty: str) -> int:
    return max(0, _FOLLOWUP_BUDGET.get(demeanor, 1) + _DIFFICULTY_BUDGET.get(difficulty, 0))


def choose_move(signals: dict[str, int], *, demeanor: str, difficulty: str, followups_on_topic: int,
                round_name: str) -> Optional[str]:
    """Follow-up move for the weakest signal, or None to move to a new topic."""
    if followups_on_topic >= followup_budget(demeanor, difficulty):
        return None
    if signals.get("truth_boundary", 4) <= 2:
        return "CONTRADICTION_PROBE"
    if signals.get("did_answer_question", 4) <= 1:
        return "CLARIFY"
    if signals.get("ownership", 4) <= 2 and round_name in ("PROJECT_DEEP_DIVE", "HIRING_MANAGER", "BEHAVIORAL"):
        return "OWNERSHIP_PROBE"
    if signals.get("trade_off", 4) <= 1 and (demeanor == "SKEPTICAL" or round_name == "SYSTEM_DESIGN"):
        return "CHALLENGE"
    if signals.get("evidence", 4) <= 1 and round_name in ("PROJECT_DEEP_DIVE", "HIRING_MANAGER", "BEHAVIORAL", "PRODUCT_CASE"):
        return "QUANTIFY"
    if signals.get("ownership", 4) <= 2:
        return "OWNERSHIP_PROBE"
    if signals.get("did_answer_question", 4) <= 2:
        return "CLARIFY"
    if signals.get("trade_off", 4) <= 1:
        return "CHALLENGE"
    if signals.get("evidence", 4) <= 1:
        return "QUANTIFY"
    if difficulty == "PRESSURE":
        return "CONSTRAINT_CHANGE"
    if demeanor in ("STRONG_FOLLOWUP", "SKEPTICAL"):
        return "FOLLOW_UP"
    return None


def _first_term(text: str) -> str:
    match = _TERM.search(text or "")
    return match.group(0) if match else ""


def phrase(move: str, *, answer: str, question: str, demeanor: str, language: str,
           quote: str = "", term: str = "") -> str:
    templates = _TEMPLATES_EN if language == "en" else _TEMPLATES_ZH
    term = term or _first_term(answer) or (("this approach" if language == "en" else "这个方案"))
    topic = re.sub(r"[？?。]+$", "", question.strip())[:30]
    text = templates[move].format(term=term, topic=topic, quote=(quote or answer[:24]).strip())
    if language != "en" and move not in ("CLOSING",):
        text = _DEMEANOR_PREFIX_ZH.get(demeanor, "") + text
    if demeanor == "FAST_PACED":
        text = re.sub(r"(？|\?).*$", r"\1", text)
    return text


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


def _load(practice_id: str) -> dict[str, Any]:
    row = store.get("practice_session", practice_id)
    if row is None:
        raise PracticeError("练习不存在")
    return row


def _save_state(practice_id: str, state: dict[str, Any]) -> None:
    store.update("practice_session", practice_id, {"state": state})


def _known_claims() -> list[dict[str, Any]]:
    try:
        from services.intelligence.job_workspace import active_claims

        return active_claims()
    except Exception:  # noqa: BLE001
        return []


def _insert_turn(practice_id: str, seq: int, persona: str, move: str, text: str, source: str) -> dict[str, Any]:
    turn = {"id": store.new_id("pt_"), "practice_id": practice_id, "seq": seq, "persona_id": persona, "move": move,
            "question": text, "question_source": source, "answer": "", "created_at": store.now()}
    store.insert("practice_turn", turn)
    return turn


def _public_turn(turn: dict[str, Any]) -> dict[str, Any]:
    persona = PERSONAS.get(turn.get("persona_id") or "", {})
    return {"id": turn["id"], "seq": turn["seq"], "question": turn["question"], "move": turn["move"],
            "source": turn.get("question_source", ""), "persona_id": turn.get("persona_id", ""),
            "persona_label": persona.get("label", "")}


def start(raw_config: dict[str, Any]) -> dict[str, Any]:
    cfg = normalize_config(raw_config)
    goal = None
    if cfg["goal_id"]:
        from services.product.goals import require_goal

        goal = require_goal(cfg["goal_id"])
    pool = build_pool(cfg, goal)
    if not pool:
        raise PracticeError("没有可用的题目：请为目标补充 JD，或选择「岗位题库」作为来源")
    personas = cfg["personas"]
    persona_demeanor = {p: (cfg["demeanor"] if len(personas) == 1 else PERSONAS[p]["demeanor"]) for p in personas}
    first_speaker = sorted(personas, key=lambda p: PERSONAS[p]["priority"])[0]
    first = pool[0]
    state = {"pool": pool, "cursor": 1, "topic": first["text"][:40], "followups_on_topic": 0,
             "open_threads": [], "asked": [first["text"]], "personas": personas,
             "persona_demeanor": persona_demeanor, "current_speaker": first_speaker,
             "next_speaker": first_speaker, "concerns": {p: PERSONAS[p]["concern"] for p in personas}}
    practice_id = store.new_id("pr_")
    store.insert("practice_session", {"id": practice_id, "goal_id": cfg["goal_id"], "config": cfg, "state": state,
                                      "status": "ACTIVE", "guided": cfg["guided"], "started_at": store.now()})
    turn = _insert_turn(practice_id, 1, first_speaker, "OPEN", first["text"], first["source"])
    if goal:
        from services.product.goals import link_session

        link_session(goal["id"], "GUIDED" if cfg["guided"] else "PRACTICE", practice_id=practice_id,
                     round_name=cfg["round"])
    events.record("practice_started", goal_id=cfg["goal_id"] or "", session_id=practice_id, round=cfg["round"],
                  demeanor=cfg["demeanor"], difficulty=cfg["difficulty"], panel=len(personas) > 1,
                  focus=bool(cfg["focus"]), guided=cfg["guided"])
    return {"practice_id": practice_id, "config": cfg, "question": _public_turn(turn),
            "panel": _panel_state(state), "pool_size": len(pool), "total": cfg["questions"]}


def _turns(practice_id: str) -> list[dict[str, Any]]:
    return store.select("practice_turn", "practice_id = ?", (practice_id,), "seq ASC")


def answer(practice_id: str, answer_text: str, *, duration_ms: Optional[int] = None,
           word_timestamps: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
    session = _load(practice_id)
    if session["status"] != "ACTIVE":
        raise PracticeError("练习已结束")
    answer_text = (answer_text or "").strip()
    if not answer_text:
        raise PracticeError("回答不能为空")
    cfg, state = session["config"], session["state"]
    turns = _turns(practice_id)
    current = turns[-1]
    if current["answer"]:
        raise PracticeError("这一题已经回答过了")

    content = {"signals": {}, "findings": [], "strengths": [], "kind": "CONTENT"}
    if current["move"] != "CLOSING":
        content = coach.analyze_content(current["question"], answer_text, move=current["move"],
                                        known_claims=_known_claims())
    delivery = None
    if cfg.get("delivery_analytics", True):
        delivery = coach.analyze_delivery(answer_text, duration_ms=duration_ms, word_timestamps=word_timestamps)
    store.update("practice_turn", current["id"], {
        "answer": answer_text, "answer_duration_ms": duration_ms, "content": content,
        "delivery": delivery or {}, "answered_at": store.now()})
    _observe(session, current, content)

    for term in dict.fromkeys(m.group(0) for m in _TERM.finditer(answer_text)):
        if term not in state["open_threads"] and term.lower() not in current["question"].lower():
            state["open_threads"].append(term)
    state["open_threads"] = state["open_threads"][-6:]

    answered = sum(1 for t in turns if t["answer"]) + 1
    feedback = {"content": content, "delivery": delivery}
    if current["move"] == "CLOSING" or answered >= cfg["questions"] + (1 if cfg.get("closing") else 0):
        _save_state(practice_id, state)
        return {"done": True, "answered": answered, "feedback": feedback, "report": finish(practice_id)}

    next_turn = _next_turn(practice_id, cfg, state, current, answer_text, content, answered, len(turns) + 1)
    _save_state(practice_id, state)
    return {"done": False, "answered": answered, "feedback": feedback, "next_question": _public_turn(next_turn),
            "panel": _panel_state(state)}


def _next_turn(practice_id: str, cfg: dict[str, Any], state: dict[str, Any], current: dict[str, Any],
               answer_text: str, content: dict[str, Any], answered: int, seq: int) -> dict[str, Any]:
    speaker = state["current_speaker"]
    demeanor = state["persona_demeanor"].get(speaker, cfg["demeanor"])
    remaining_main = cfg["questions"] - answered
    if remaining_main <= 0 and cfg.get("closing"):
        closer = sorted(state["personas"], key=lambda p: PERSONAS[p]["priority"])[-1] if len(state["personas"]) > 1 \
            else speaker
        state.update(current_speaker=closer, next_speaker=closer)
        text = phrase("CLOSING", answer=answer_text, question=current["question"], demeanor=demeanor,
                      language=cfg["language"])
        return _insert_turn(practice_id, seq, closer, "CLOSING", text, "CLOSING")

    move = choose_move(content.get("signals") or {}, demeanor=demeanor, difficulty=cfg["difficulty"],
                       followups_on_topic=state["followups_on_topic"], round_name=cfg["round"])
    if move:
        # a follow-up stays with the persona who asked; ownership concerns go to the hiring manager in a panel
        if move == "OWNERSHIP_PROBE" and "HIRING_MANAGER" in state["personas"]:
            speaker = "HIRING_MANAGER"
        quote = ""
        if move == "CONTRADICTION_PROBE":
            quote = next((f["evidence_from_actual_speech"] for f in content.get("findings", [])
                          if f["signal"] == "truth_boundary" and f["evidence_from_actual_speech"]), "")
        text = phrase(move, answer=answer_text, question=current["question"],
                      demeanor=state["persona_demeanor"].get(speaker, demeanor), language=cfg["language"], quote=quote)
        state["followups_on_topic"] += 1
        state.update(current_speaker=speaker, next_speaker=speaker)
        return _insert_turn(practice_id, seq, speaker, move, text, "ADAPTIVE")

    # move to a new topic: next unasked pool item, else an open thread
    item = None
    while state["cursor"] < len(state["pool"]):
        candidate = state["pool"][state["cursor"]]
        state["cursor"] += 1
        if candidate["text"] not in state["asked"]:
            item = candidate
            break
    if item is None and state["open_threads"]:
        term = state["open_threads"].pop(0)
        text = (_TEMPLATES_EN if cfg["language"] == "en" else _TEMPLATES_ZH)["OPEN_THREAD"].format(term=term)
        item = _item(text, "OPEN_THREAD", "technical")
    if item is None:
        item = _item(phrase("CONSTRAINT_CHANGE", answer=answer_text, question=current["question"], demeanor=demeanor,
                            language=cfg["language"]), "ADAPTIVE", "scalability")
    next_speaker = _persona_for(item, state["personas"], state["current_speaker"])
    state.update(current_speaker=next_speaker, next_speaker=next_speaker, topic=item["text"][:40],
                 followups_on_topic=0)
    state["asked"].append(item["text"])
    return _insert_turn(practice_id, seq, next_speaker, "OPEN", item["text"], item["source"])


def _observe(session: dict[str, Any], turn: dict[str, Any], content: dict[str, Any]) -> None:
    levels = coach.rubric_levels(content)
    now = store.now()
    with store.connect() as conn:
        for dimension, level in levels.items():
            store.insert("rubric_observation", {
                "id": store.new_id("ro_"), "goal_id": session.get("goal_id"), "session_kind": "PRACTICE",
                "session_ref": session["id"], "turn_ref": turn["id"], "dimension": dimension, "level": level,
                "note": turn["move"], "created_at": now}, conn=conn)


def get(practice_id: str) -> dict[str, Any]:
    session = _load(practice_id)
    turns = _turns(practice_id)
    return {"practice_id": practice_id, "status": session["status"], "config": session["config"],
            "goal_id": session.get("goal_id"), "panel": _panel_state(session["state"]),
            "turns": [{**_public_turn(t), "answer": t["answer"], "content": t.get("content") or {},
                       "delivery": t.get("delivery") or {}} for t in turns],
            "review_session_id": session.get("review_session_id"), "started_at": session["started_at"],
            "ended_at": session.get("ended_at")}


def finish(practice_id: str) -> dict[str, Any]:
    session = _load(practice_id)
    turns = [t for t in _turns(practice_id) if t["answer"]]
    if session["status"] == "DONE":
        return report(practice_id)
    if not turns:
        raise PracticeError("还没有任何回答，无法结束")
    store.update("practice_session", practice_id, {"status": "DONE", "ended_at": store.now()})
    review_id = _write_review(session, turns)
    if review_id is not None:
        store.update("practice_session", practice_id, {"review_session_id": review_id})
        from services.product.goals import attach_review_to_practice

        attach_review_to_practice(practice_id, review_id)
    if session.get("goal_id"):
        banks.remember_session_questions(session["goal_id"], [t["question"] for t in turns if t["move"] == "OPEN"])
        try:
            from services.product.next_focus import recompute

            recompute(session["goal_id"])
        except Exception as exc:  # noqa: BLE001
            _log.warning("next focus recompute after practice failed: %s", exc)
    events.record("practice_completed", goal_id=session.get("goal_id") or "", session_id=practice_id,
                  turns=len(turns), guided=bool(session.get("guided")))
    if session.get("guided"):
        events.record("guided_practice_completed", session_id=practice_id)
    return report(practice_id)


def _write_review(session: dict[str, Any], turns: list[dict[str, Any]]) -> Optional[int]:
    """Land the practice in the existing Review store (one row, never copied)."""
    try:
        from services.storage import review as review_storage

        goal = None
        if session.get("goal_id"):
            from services.product.goals import get_goal

            goal = get_goal(session["goal_id"])
        cfg = session["config"]
        title = f"练习 · {ROUND_LABELS.get(cfg['round'], cfg['round'])}" + (f" · {goal['title']}" if goal else "")
        rid = review_storage.create_session(
            started_at=session["started_at"], interviewer_enabled=True, candidate_enabled=True, source="practice",
            title=title, company=(goal or {}).get("company", ""), role=(goal or {}).get("role", ""),
            application_id=(goal or {}).get("application_id"),
        )
        for idx, t in enumerate(turns, start=1):
            content = t.get("content") or {}
            review_storage.add_turn(
                session_id=rid, qa_id=f"practice3-{session['id']}-{idx}", seq=idx,
                question_text=t["question"], candidate_answer_text=t["answer"], analysis_status="completed",
                strengths=[s.get("evidence_from_actual_speech", "") for s in content.get("strengths", [])],
                risks=[f["finding"] for f in content.get("findings", [])],
                evidence={"content_findings": content.get("findings", []), "delivery": t.get("delivery") or {},
                          "move": t["move"], "persona": t.get("persona_id", "")},
                scorecard={},
            )
        summary = summarize(session, turns)
        review_storage.end_session(rid, status="completed", ended_at=store.now(),
                                   summary_markdown=summary["markdown"], strong_points=summary["went_well"],
                                   weak_points=summary["to_improve"])
        return int(rid)
    except Exception as exc:  # noqa: BLE001 — practice result stays in product.db even if review store fails
        _log.warning("practice review write failed: %s", exc)
        return None


def summarize(session: dict[str, Any], turns: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter

    weak = Counter()
    strong = Counter()
    for t in turns:
        for f in (t.get("content") or {}).get("findings", []):
            weak[f["dimension"]] += 1
        for s in (t.get("content") or {}).get("strengths", []):
            strong[s["dimension"]] += 1
    from services.product.rubrics import DIMENSIONS

    to_improve = [f"{DIMENSIONS[d]}（{n} 题）" for d, n in weak.most_common(3)]
    went_well = [f"{DIMENSIONS[d]}（{n} 题）" for d, n in strong.most_common(3)]
    delivery = coach.summarize_delivery([t.get("delivery") or {} for t in turns if t.get("delivery")])
    lines = ["## 练习小结", ""]
    if went_well:
        lines.append("做得好：" + "、".join(went_well))
    if to_improve:
        lines.append("需要改进：" + "、".join(to_improve))
    lines += [f"- {d}" for d in delivery]
    return {"went_well": went_well, "to_improve": to_improve, "delivery": delivery, "markdown": "\n".join(lines)}


def report(practice_id: str) -> dict[str, Any]:
    session = _load(practice_id)
    turns = [t for t in _turns(practice_id) if t["answer"]]
    summary = summarize(session, turns)
    return {"practice_id": practice_id, "review_session_id": session.get("review_session_id"),
            "goal_id": session.get("goal_id"), "turn_count": len(turns), **summary}


def list_sessions(goal_id: str = "", limit: int = 50) -> list[dict[str, Any]]:
    where, params = ("goal_id = ?", (goal_id,)) if goal_id else ("", ())
    rows = store.select("practice_session", where, params, "started_at DESC", limit)
    return [{"practice_id": r["id"], "goal_id": r.get("goal_id"), "status": r["status"],
             "round": (r.get("config") or {}).get("round"), "guided": r["guided"],
             "panel": len((r.get("config") or {}).get("personas") or []) > 1,
             "review_session_id": r.get("review_session_id"), "started_at": r["started_at"],
             "ended_at": r.get("ended_at")} for r in rows]


def options() -> dict[str, Any]:
    return {
        "rounds": [{"key": r, "label": ROUND_LABELS[r]} for r in ROUNDS],
        "demeanors": [{"key": "NEUTRAL", "label": "中性"}, {"key": "FRIENDLY", "label": "友好"},
                      {"key": "SKEPTICAL", "label": "质疑"}, {"key": "STRONG_FOLLOWUP", "label": "强追问"},
                      {"key": "FAST_PACED", "label": "快节奏"}],
        "difficulties": [{"key": "WARMUP", "label": "热身"}, {"key": "STANDARD", "label": "标准"},
                         {"key": "PRESSURE", "label": "压力"}],
        "sources": [{"key": "GOAL_GRAPH", "label": "目标 Question Graph"},
                    {"key": "RECENT_WEAKNESS", "label": "最近的薄弱点"},
                    {"key": "MY_BANK", "label": "我的题库"}, {"key": "ROLE_BANK", "label": "岗位题库"}],
        "personas": [{"key": k, "label": v["label"], "concern": v["concern"], "followup_style": v["followup_style"],
                      "demeanor": v["demeanor"]} for k, v in PERSONAS.items()],
    }
