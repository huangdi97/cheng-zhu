"""Stream Truth Guard (R2 Stage L): sentence / claim level buffering.

Knowledge prose streams through untouched. Only when a first-person span
starts ("我…", "我们…", "本人…") is that span held until its sentence ends;
the finished sentence is checked and either released as-is or rewritten to
a boundary phrasing. The whole answer is never held back.

    token stream -> current sentence buffer -> claim detector
      low risk  -> release
      high risk -> check -> safe release / boundary rewrite

A full post-audit still runs on the final text (answer_worker).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from services.intelligence.semantics import AssertionPolicy
from services.intelligence.truth_boundary import (
    _HYPOTHETICAL_MARKERS,
    _METRIC_RE,
    _NEGATION_PREFIX,
    _POSITIVE_CLAIM,
    _downgrade_to_boundary,
)

_TERMINATORS = "。！？!?\n；;"
_TRIGGER = re.compile(r"我|本人")
# Broader than truth_boundary._POSITIVE_CLAIM: allows several adverbs /
# a location phrase between the subject and the experience verb
# ("我之前在生产环境用过 X").
_CLAIM_SPAN = re.compile(
    r"(?:我|我们|本人)[^，,。！？!?；;]{0,18}?"
    r"(?:用过|用了|使用过|使用了|做过|做了|负责过|负责|参与过|实现过|实现了|落地过|落地了|部署过|部署了|"
    r"上线过|上线了|搭建过|搭建了|维护过|开发过|设计过|主导过|主导了|引入了|带领)"
)
_OWNERSHIP = re.compile(r"(?:我|本人)(?:们)?.{0,6}(?:负责|主导|带领|牵头|owner|上线了|落地了)", re.IGNORECASE)
_NEGATED = re.compile(r"没有|没|未|从未|不曾|并不|不是")
_ASCII_TERM = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]{1,}")
_CJK_TERM = re.compile(r"[一-鿿]{2,}")
_GENERIC_TERMS = {
    "我们", "项目", "当时", "之前", "实际", "负责", "使用", "用了", "做过", "用过", "部署", "上线", "主要", "这个",
    "那个", "一个", "然后", "因为", "所以", "可以", "需要", "进行", "通过", "方案", "系统", "问题", "生产", "环境",
}


@dataclass
class GuardEvent:
    sentence: str
    released: str
    kind: str


@dataclass
class StreamTruthGuard:
    """Feed model text chunks; get back text that is safe to show now."""

    assertion_policy: AssertionPolicy | str = AssertionPolicy.REQUIRE_BOUNDARY
    evidence_texts: list[str] = field(default_factory=list)
    # Experience route: the asked subject ("Redis"). The whole claim sentence
    # is personal there, so it becomes a boundary sentence about that
    # subject instead of keeping any remainder (which could be a substituted
    # subject such as "Kafka 项目").
    boundary_subject: str = ""
    events: list[GuardEvent] = field(default_factory=list)
    _held: str = ""
    _sentence_prefix: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.assertion_policy, AssertionPolicy):
            try:
                self.assertion_policy = AssertionPolicy(str(self.assertion_policy))
            except ValueError:
                self.assertion_policy = AssertionPolicy.REQUIRE_BOUNDARY
        self._corpus = " ".join(self.evidence_texts).lower()

    # -- public API ---------------------------------------------------------
    def feed(self, chunk: str) -> str:
        out: list[str] = []
        for ch in chunk or "":
            out.append(self._feed_char(ch))
        return "".join(out)

    def flush(self) -> str:
        if not self._held:
            return ""
        released = self._check(self._held)
        self._held = ""
        self._sentence_prefix = ""
        return released

    @property
    def rewrites(self) -> int:
        return sum(1 for e in self.events if e.kind == "rewrite")

    # -- internals ----------------------------------------------------------
    def _feed_char(self, ch: str) -> str:
        if self._held:
            self._held += ch
            if ch in _TERMINATORS:
                released = self._check(self._held)
                self._held = ""
                self._sentence_prefix = ""
                return released
            return ""
        if _TRIGGER.match(ch) or (ch == "本"):
            self._held = ch
            return ""
        if ch in _TERMINATORS:
            self._sentence_prefix = ""
        else:
            self._sentence_prefix += ch
        return ch

    def _is_risky(self, span: str) -> bool:
        if span.startswith("本") and not span.startswith("本人"):
            return False
        context = self._sentence_prefix[-12:] + span
        if any(marker in context for marker in _HYPOTHETICAL_MARKERS):
            return False
        for match in [*_CLAIM_SPAN.finditer(span), *_POSITIVE_CLAIM.finditer(span)]:
            prefix = span[: match.start()]
            if _NEGATED.search(match.group(0)):
                continue
            if not _NEGATION_PREFIX.search(self._sentence_prefix[-8:] + prefix):
                return True
        if _OWNERSHIP.search(span):
            return True
        return bool(_METRIC_RE.search(span)) and bool(re.search(r"(?:提升|降低|减少|增长|优化|达到|QPS|ms|%)", span, re.IGNORECASE))

    def _supported(self, span: str) -> bool:
        policy = self.assertion_policy
        if policy in {AssertionPolicy.BLOCK_ASSERTION, AssertionPolicy.KNOWLEDGE_ONLY, AssertionPolicy.REQUIRE_BOUNDARY}:
            return False
        if not self._corpus:
            return False
        terms = [t.lower() for t in _ASCII_TERM.findall(span)]
        terms += [t for t in _CJK_TERM.findall(span) if t not in _GENERIC_TERMS and len(t) <= 8]
        metrics = _METRIC_RE.findall(span)
        if policy == AssertionPolicy.ALLOW_WITH_QUALIFIER and any(m not in self._corpus for m in metrics):
            # Qualified assertion must not add numbers the sources lack.
            return False
        ascii_terms = [t for t in terms if re.match(r"[a-z]", t)]
        check = ascii_terms or terms
        if not check:
            return policy == AssertionPolicy.ALLOW_PERSONAL_ASSERTION
        return all(term in self._corpus for term in check)

    def _check(self, span: str) -> str:
        if not self._is_risky(span):
            self.events.append(GuardEvent(span, span, "release"))
            return span
        if self._supported(span):
            self.events.append(GuardEvent(span, span, "supported"))
            return span
        if self.boundary_subject:
            rewritten = f"我没有直接做过 {self.boundary_subject} 的项目，下面按通用做法说。"
            self.events.append(GuardEvent(span, rewritten, "rewrite"))
            return rewritten
        rewritten = _downgrade_to_boundary(span)
        if rewritten.startswith("（事实边界"):
            # The legacy downgrade could not rewrite in place; strip the
            # first-person claim and keep only the technical remainder.
            match = _CLAIM_SPAN.search(span)
            rest = span[match.end():].strip() if match else ""
            rewritten = f"（这部分没有可确认的亲历）通用做法：{rest}" if rest else "（这部分没有可确认的亲历，按通用做法说明。）"
        self.events.append(GuardEvent(span, rewritten, "rewrite"))
        return rewritten
