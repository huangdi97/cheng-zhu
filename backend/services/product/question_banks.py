"""Question Banks (canonical §11).

Origins: CURATED (shipped role banks, generic — never presented as any
company's real interview), IMPORTED (user import, may carry source_url),
GENERATED (model output), PREVIOUS_SESSION (asked in one of the user's own
sessions), USER_ADDED.

 INVARIANT: a GENERATED or CURATED question is never labelled as a specific
 company's real interview experience. ``label_for`` only says "真实面经" when
 the item is IMPORTED with a source_url.
"""
from __future__ import annotations

from typing import Any, Optional

from services.storage import product as store

ORIGINS = ("CURATED", "IMPORTED", "GENERATED", "PREVIOUS_SESSION", "USER_ADDED")
DIFFICULTIES = ("WARMUP", "STANDARD", "PRESSURE")
SCOPES = ("ROLE", "USER", "GOAL")
ROUNDS = ("TECHNICAL", "PROJECT_DEEP_DIVE", "SYSTEM_DESIGN", "HIRING_MANAGER", "HR", "BEHAVIORAL", "PRODUCT_CASE")


class QuestionBankError(ValueError):
    pass


# (text, category, difficulty, rounds)
_ROLE_BANKS: dict[str, tuple[str, list[tuple[str, str, str, tuple[str, ...]]]]] = {
    "SWE": ("Software Engineer 通用题库", [
        ("介绍一个你主导的项目，你在其中具体负责什么？", "ownership", "WARMUP", ("PROJECT_DEEP_DIVE", "HIRING_MANAGER")),
        ("这个系统的瓶颈在哪里？你怎么定位的？", "performance", "STANDARD", ("TECHNICAL", "PROJECT_DEEP_DIVE")),
        ("如果流量涨 10 倍，你的设计哪里先出问题？", "scalability", "PRESSURE", ("SYSTEM_DESIGN",)),
        ("设计一个短链接服务，说说存储、发号和缓存的取舍。", "system_design", "STANDARD", ("SYSTEM_DESIGN",)),
        ("Redis 做缓存时如何处理缓存击穿、穿透和雪崩？", "cache", "STANDARD", ("TECHNICAL",)),
        ("数据库事务隔离级别有哪些？你的项目用的哪一个，为什么？", "database", "STANDARD", ("TECHNICAL",)),
        ("一次线上故障，你是怎么发现、止血和复盘的？", "incident", "STANDARD", ("BEHAVIORAL", "HIRING_MANAGER")),
        ("如何保证分布式系统中消息不丢不重？", "distributed", "PRESSURE", ("TECHNICAL", "SYSTEM_DESIGN")),
        ("讲一次你和同事在技术方案上有分歧的经历。", "conflict", "STANDARD", ("BEHAVIORAL",)),
        ("你怎么做 Code Review？最近一次你拦下了什么问题？", "engineering_practice", "WARMUP", ("HIRING_MANAGER",)),
        ("设计一个限流器，支持多机部署。", "system_design", "PRESSURE", ("SYSTEM_DESIGN",)),
        ("为什么想离开现在的团队？", "motivation", "WARMUP", ("HR",)),
    ]),
    "AI_ML": ("AI / ML Engineer 通用题库", [
        ("讲讲你做过的 RAG 系统：检索、重排和生成各自怎么评估？", "rag", "STANDARD", ("TECHNICAL", "PROJECT_DEEP_DIVE")),
        ("Agent 的工具调用失败或循环时你怎么兜底？", "agent", "PRESSURE", ("TECHNICAL", "SYSTEM_DESIGN")),
        ("如何降低大模型应用的端到端延迟？", "latency", "STANDARD", ("TECHNICAL",)),
        ("微调和提示工程/RAG 怎么选？举一个你做过的取舍。", "trade_off", "STANDARD", ("TECHNICAL", "HIRING_MANAGER")),
        ("设计一个企业知识库问答系统，说明数据更新与权限隔离。", "system_design", "PRESSURE", ("SYSTEM_DESIGN",)),
        ("模型上线后效果下降，你怎么排查？", "evaluation", "STANDARD", ("TECHNICAL",)),
        ("幻觉问题你在项目里怎么度量和缓解？", "hallucination", "STANDARD", ("TECHNICAL",)),
        ("你在项目中负责的部分里，最难的技术决策是什么？", "ownership", "STANDARD", ("PROJECT_DEEP_DIVE",)),
        ("如何构建离线评测集，避免评测集泄漏？", "evaluation", "PRESSURE", ("TECHNICAL",)),
        ("讲一次实验结果不符合预期的经历，你怎么处理的？", "failure", "STANDARD", ("BEHAVIORAL",)),
        ("向量检索的召回率不够时你会怎么做？", "retrieval", "STANDARD", ("TECHNICAL",)),
        ("你最近读过哪篇论文或技术报告，对你的工作有什么影响？", "learning", "WARMUP", ("HIRING_MANAGER",)),
    ]),
    "AI_PM": ("AI Product Manager 通用题库", [
        ("你负责的 AI 功能，成功指标是怎么定义的？", "metrics", "STANDARD", ("PRODUCT_CASE", "HIRING_MANAGER")),
        ("模型能力不稳定时，产品体验怎么设计兜底？", "ux_fallback", "STANDARD", ("PRODUCT_CASE",)),
        ("如何判断一个需求适不适合用大模型做？", "judgement", "STANDARD", ("PRODUCT_CASE",)),
        ("讲一次你推动研发、算法和业务对齐的经历。", "influence", "STANDARD", ("BEHAVIORAL", "HIRING_MANAGER")),
        ("如果 AI 功能上线后留存不涨，你怎么分析？", "analysis", "PRESSURE", ("PRODUCT_CASE",)),
        ("设计一个面向销售团队的 AI 助手，MVP 包含什么？", "product_design", "STANDARD", ("PRODUCT_CASE",)),
        ("如何平衡模型成本与体验？", "trade_off", "PRESSURE", ("PRODUCT_CASE", "HIRING_MANAGER")),
        ("讲一个你砍掉的需求，为什么砍？", "prioritization", "STANDARD", ("HIRING_MANAGER",)),
        ("你如何建立 AI 产品的评测与上线标准？", "evaluation", "STANDARD", ("PRODUCT_CASE",)),
        ("为什么想做 AI 产品经理？", "motivation", "WARMUP", ("HR",)),
    ]),
    "DATA_ML": ("Data / ML 通用题库", [
        ("讲一个你用数据推动决策的例子，结论如何验证？", "impact", "STANDARD", ("PROJECT_DEEP_DIVE", "HIRING_MANAGER")),
        ("A/B 实验样本量怎么估计？出现辛普森悖论怎么办？", "experiment", "PRESSURE", ("TECHNICAL",)),
        ("特征工程中如何避免数据泄漏？", "leakage", "STANDARD", ("TECHNICAL",)),
        ("模型指标提升但业务指标没变，可能是什么原因？", "metrics", "STANDARD", ("TECHNICAL", "PRODUCT_CASE")),
        ("设计一个实时特征平台，说说一致性与延迟取舍。", "system_design", "PRESSURE", ("SYSTEM_DESIGN",)),
        ("类别极不平衡时你会怎么建模和评估？", "modeling", "STANDARD", ("TECHNICAL",)),
        ("讲一次你的分析结论被质疑的经历。", "conflict", "STANDARD", ("BEHAVIORAL",)),
        ("数据质量问题你怎么发现和治理？", "data_quality", "STANDARD", ("TECHNICAL",)),
        ("给非技术同事解释一个模型结果，你会怎么讲？", "communication", "WARMUP", ("HIRING_MANAGER",)),
    ]),
    "PRODUCT": ("General Product 通用题库", [
        ("你最自豪的产品决策是什么？数据如何验证？", "impact", "STANDARD", ("HIRING_MANAGER",)),
        ("如何给需求排优先级？", "prioritization", "WARMUP", ("PRODUCT_CASE",)),
        ("设计一个提升新用户激活的方案。", "product_design", "STANDARD", ("PRODUCT_CASE",)),
        ("某核心指标下降 10%，你怎么排查？", "analysis", "PRESSURE", ("PRODUCT_CASE",)),
        ("讲一次跨团队冲突以及你如何推动解决。", "conflict", "STANDARD", ("BEHAVIORAL",)),
        ("一个失败的项目，你从中学到了什么？", "failure", "STANDARD", ("BEHAVIORAL",)),
        ("你如何和研发沟通一个模糊的需求？", "ambiguity", "STANDARD", ("HIRING_MANAGER",)),
        ("为什么选择我们公司？", "motivation", "WARMUP", ("HR",)),
    ]),
}

_COMMON_BEHAVIORAL = [
    ("讲一次你承担超出职责范围的事情。", "ownership", "STANDARD", ("BEHAVIORAL",)),
    ("讲一次失败经历，以及你之后做了什么改变。", "failure", "STANDARD", ("BEHAVIORAL",)),
    ("在信息不完整时你怎么做决定？", "ambiguity", "STANDARD", ("BEHAVIORAL", "HIRING_MANAGER")),
    ("你最近一次主动学习新领域是什么？", "learning", "WARMUP", ("BEHAVIORAL", "HR")),
    ("你有什么想问我们的？", "closing", "WARMUP", ("HR", "HIRING_MANAGER")),
]


def label_for(item: dict[str, Any]) -> str:
    origin = item.get("origin")
    if origin == "IMPORTED" and item.get("source_url"):
        return "导入（有来源）"
    return {
        "CURATED": "成竹通用题",
        "IMPORTED": "导入（无来源，非真实面经）",
        "GENERATED": "AI 生成（非真实面经）",
        "PREVIOUS_SESSION": "来自你的历史场次",
        "USER_ADDED": "你添加的",
    }.get(str(origin), "题目")


def ensure_builtin_banks() -> int:
    """Seed curated role banks once; returns the number of banks created."""
    created = 0
    for family, (name, items) in _ROLE_BANKS.items():
        bank_id = f"qb_role_{family.lower()}"
        if store.get("question_bank", bank_id) is not None:
            continue
        now = store.now()
        store.insert("question_bank", {"id": bank_id, "name": name, "scope": "ROLE", "role": family,
                                       "company": "", "source_type": "CURATED", "goal_id": None,
                                       "builtin": True, "created_at": now, "updated_at": now})
        for text, category, difficulty, rounds in [*items, *_COMMON_BEHAVIORAL]:
            _insert_item(bank_id, text, category, difficulty, "CURATED", "", list(rounds))
        created += 1
    return created


def _insert_item(bank_id: str, text: str, category: str, difficulty: str, origin: str,
                 source_url: str, rounds: list[str]) -> dict[str, Any]:
    row = {"id": store.new_id("qi_"), "bank_id": bank_id, "text": text.strip(), "category": category,
           "difficulty": difficulty, "origin": origin, "source_url": source_url,
           "rounds": [r for r in rounds if r in ROUNDS], "created_at": store.now()}
    store.insert("question_bank_item", row)
    return row


def create_bank(name: str, *, scope: str = "USER", role: str = "", company: str = "",
                source_type: str = "USER_ADDED", goal_id: Optional[str] = None) -> dict[str, Any]:
    name = (name or "").strip()
    if not name:
        raise QuestionBankError("题库名称不能为空")
    if scope not in SCOPES:
        raise QuestionBankError(f"未知范围：{scope}")
    if source_type not in ORIGINS:
        raise QuestionBankError(f"未知来源：{source_type}")
    now = store.now()
    bank = {"id": store.new_id("qb_"), "name": name[:80], "scope": scope, "role": role, "company": company,
            "source_type": source_type, "goal_id": goal_id, "builtin": False, "created_at": now, "updated_at": now}
    store.insert("question_bank", bank)
    return bank


def add_item(bank_id: str, text: str, *, category: str = "", difficulty: str = "STANDARD",
             origin: str = "USER_ADDED", source_url: str = "", rounds: Optional[list[str]] = None) -> dict[str, Any]:
    bank = store.get("question_bank", bank_id)
    if bank is None:
        raise QuestionBankError("题库不存在")
    if bank["builtin"]:
        raise QuestionBankError("内置题库只读；请复制到你的题库后编辑")
    if not (text or "").strip():
        raise QuestionBankError("题目不能为空")
    if difficulty not in DIFFICULTIES:
        raise QuestionBankError(f"未知难度：{difficulty}")
    if origin not in ORIGINS or origin == "CURATED":
        raise QuestionBankError(f"来源无效：{origin}")
    if source_url and not source_url.startswith(("http://", "https://")):
        raise QuestionBankError("来源链接需以 http(s):// 开头")
    item = _insert_item(bank_id, text[:600], category[:40], difficulty, origin, source_url[:500], rounds or [])
    store.update("question_bank", bank_id, {"updated_at": store.now()})
    return item


def import_items(bank_id: str, lines: list[str], source_url: str = "") -> int:
    count = 0
    for line in lines:
        text = (line or "").strip().lstrip("-*0123456789.、) ").strip()
        if len(text) >= 4:
            add_item(bank_id, text, origin="IMPORTED", source_url=source_url)
            count += 1
    return count


def delete_item(item_id: str) -> bool:
    item = store.get("question_bank_item", item_id)
    if item is None:
        return False
    bank = store.get("question_bank", item["bank_id"])
    if bank and bank["builtin"]:
        raise QuestionBankError("内置题库只读")
    return store.delete("question_bank_item", item_id)


def delete_bank(bank_id: str) -> bool:
    bank = store.get("question_bank", bank_id)
    if bank is None:
        return False
    if bank["builtin"]:
        raise QuestionBankError("内置题库不能删除")
    store.delete("question_bank", bank_id)
    for goal in store.select("goal", "active_question_bank_ids_json LIKE ?", (f"%{bank_id}%",)):
        ids = [i for i in (goal.get("active_question_bank_ids") or []) if i != bank_id]
        store.update("goal", goal["id"], {"active_question_bank_ids": ids})
    return True


def list_banks(role: str = "", goal_id: str = "") -> list[dict[str, Any]]:
    ensure_builtin_banks()
    banks = store.select("question_bank", "", (), "builtin DESC, updated_at DESC")
    if role:
        banks = [b for b in banks if not b["builtin"] or b["role"] == role]
    if goal_id:
        banks = [b for b in banks if b["scope"] != "GOAL" or b["goal_id"] == goal_id]
    for bank in banks:
        bank["item_count"] = store.scalar("SELECT COUNT(*) FROM question_bank_item WHERE bank_id = ?", (bank["id"],))
    return banks


def list_items(bank_id: str) -> list[dict[str, Any]]:
    items = store.select("question_bank_item", "bank_id = ?", (bank_id,), "created_at ASC")
    for item in items:
        item["label"] = label_for(item)
    return items


def role_bank_id(role_family: str) -> str:
    return f"qb_role_{(role_family or 'SWE').lower()}"


def pool(bank_ids: list[str], round_name: str = "", difficulty: str = "") -> list[dict[str, Any]]:
    """Items from the given banks, filtered by round (if tagged) and difficulty band."""
    ensure_builtin_banks()
    out: list[dict[str, Any]] = []
    for bank_id in bank_ids:
        for item in list_items(bank_id):
            if round_name and item.get("rounds") and round_name not in item["rounds"]:
                continue
            if difficulty == "WARMUP" and item["difficulty"] == "PRESSURE":
                continue
            if difficulty == "PRESSURE" and item["difficulty"] == "WARMUP":
                continue
            out.append(item)
    return out


def remember_session_questions(goal_id: Optional[str], questions: list[str]) -> int:
    """PREVIOUS_SESSION bank per goal: questions actually asked in the user's sessions."""
    if not questions:
        return 0
    bank_id = f"qb_prev_{goal_id or 'global'}"
    if store.get("question_bank", bank_id) is None:
        now = store.now()
        store.insert("question_bank", {"id": bank_id, "name": "历史场次中被问到的题", "scope": "GOAL" if goal_id else "USER",
                                       "role": "", "company": "", "source_type": "PREVIOUS_SESSION",
                                       "goal_id": goal_id, "builtin": False, "created_at": now, "updated_at": now})
    existing = {i["text"] for i in list_items(bank_id)}
    added = 0
    for q in questions:
        text = (q or "").strip()
        if len(text) >= 4 and text not in existing:
            _insert_item(bank_id, text[:600], "", "STANDARD", "PREVIOUS_SESSION", "", [])
            existing.add(text)
            added += 1
    return added
