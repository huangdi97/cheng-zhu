"""ASR merge and question-group state machine for interview assist."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Callable, Optional

from services.stt import (
    classify_asr_question_candidate,
    is_asr_question_constraint_tail,
    is_viable_asr_question_group,
    join_transcription_fragments,
    transcription_for_publish,
)
from services.question_turn_parser import is_auto_answer_enabled, parse_question_turn
from api.assist.scheduler import TaskPayload


@dataclass
class PendingASRGroup:
    source: str
    utterances: list[str] = field(default_factory=list)
    first_mono: float = 0.0
    last_mono: float = 0.0
    has_promote: bool = False


@dataclass
class ProvisionalCue:
    """A Fast Cue emitted from a stable streaming partial before the
    authoritative (batch) transcription confirmed the question."""
    qa_id: str
    question: str
    emitted_mono: float


_QUESTION_NOISE = re.compile(r"[\s\u3000，,。.？?！!、；;：:\"'\u201c\u201d\u2018\u2019]+")


def _norm_question(text: str) -> str:
    return _QUESTION_NOISE.sub("", (text or "").lower())


def reconcile_relation(provisional: str, final: str) -> str:
    """same | corrected (same question, better text) | replaced (different question)."""
    a, b = _norm_question(provisional), _norm_question(final)
    if not a or not b:
        return "replaced"
    if a == b:
        return "same"
    if a in b or b in a or SequenceMatcher(None, a, b).ratio() >= 0.6:
        return "corrected"
    return "replaced"


class AssistAsrStateMachine:
    def __init__(
        self,
        *,
        broadcast: Callable[[dict], None],
        submit_answer_task: Callable[[TaskPayload], bool],
        begin_asr_turn: Callable[[], int],
        record_asr_turn: Callable[[float], None],
        is_high_churn_submission: Callable[[Any, float], bool],
        logger,
        append_late_constraint_tail: Callable[[str, str, float], bool] | None = None,
        clock: Callable[[], float] = time.monotonic,
        early_cue: Callable[[str, str, dict], None] | None = None,
    ):
        self.early_cue = early_cue
        self.broadcast = broadcast
        self.submit_answer_task = submit_answer_task
        self.begin_asr_turn = begin_asr_turn
        self.record_asr_turn = record_asr_turn
        self.is_high_churn_submission = is_high_churn_submission
        self.append_late_constraint_tail = append_late_constraint_tail or (lambda _text, _source, _now: False)
        self.logger = logger
        self.clock = clock
        self.merge_parts: list[str] = []
        self.merge_mono_first: Optional[float] = None
        self.merge_mono_last: Optional[float] = None
        self.pending_group: Optional[PendingASRGroup] = None
        self.provisional: Optional[ProvisionalCue] = None
        self._provisional_seq = 0
        self.provisional_stats = {"emitted": 0, "same": 0, "corrected": 0, "replaced": 0, "retracted": 0}

    # ------------------------------------------------------------------
    # Provisional Fast Cue (streaming partial) + reconcile
    # ------------------------------------------------------------------

    def submit_provisional(self, cfg, session, partial: str, source: str, now_mono: float) -> Optional[str]:
        """Emit a Fast Cue from a stable, end-covering streaming partial.

        Read-only: no turn id, no interview-state event, no answer task. The
        authoritative transcription later confirms it on the same card
        (``same``), corrects the text (``corrected``) or replaces it
        (``replaced``); an unconfirmed cue is retracted.
        """
        if self.early_cue is None or not bool(getattr(cfg, "intelligence_early_cue", True)):
            return None
        if not bool(getattr(cfg, "assist_provisional_cue", True)) or not is_auto_answer_enabled(cfg):
            return None
        if self.provisional is not None:
            return None
        text = (partial or "").strip()
        kind, cleaned = classify_asr_question_candidate(text, getattr(cfg, "transcription_min_sig_chars", 2))
        if not cleaned or kind == "ignore":
            return None
        prefix = list(self.merge_parts)
        if self.pending_group is not None:
            prefix = list(self.pending_group.utterances) + prefix
        last_qa = session.get_last_qa() if hasattr(session, "get_last_qa") else None
        parsed = parse_question_turn(
            prefix + [text],
            previous_question=str(getattr(last_qa, "question", "") or ""),
        )
        if not parsed.clusters:
            return None
        # The partial is the newest speech: it belongs to the last cluster
        # (earlier clusters come from text already assembling in this turn).
        cluster = parsed.clusters[-1]
        self._provisional_seq += 1
        qa_id = f"qa-p{self._provisional_seq}-{int(time.time() * 1000)}"
        question = cluster.task_question()
        try:
            self.early_cue(question, qa_id, {
                "source": source,
                "question_type": cluster.question_type,
                "provisional": True,
                "display_question": cluster.display_question(),
            })
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("provisional cue failed: %s", exc)
            return None
        self.provisional = ProvisionalCue(qa_id=qa_id, question=question, emitted_mono=now_mono)
        self.provisional_stats["emitted"] += 1
        self.logger.info("ASR_PROVISIONAL_CUE qa_id=%s text=%r", qa_id, question[:120])
        return qa_id

    def _provisional_cluster_index(self, clusters) -> int:
        """The final cluster that confirms the provisional cue: the best
        textual match, else the last cluster (the newest speech)."""
        prov = self.provisional
        if prov is None or not clusters:
            return -1
        best, best_score = len(clusters) - 1, -1.0
        for index, cluster in enumerate(clusters):
            relation = reconcile_relation(prov.question, cluster.task_question())
            score = {"same": 2.0, "corrected": 1.0}.get(relation, 0.0) + SequenceMatcher(
                None, _norm_question(prov.question), _norm_question(cluster.task_question())
            ).ratio()
            if score > best_score:
                best, best_score = index, score
        return best

    def retract_provisional(self, reason: str) -> None:
        prov = self.provisional
        if prov is None:
            return
        self.provisional = None
        self.provisional_stats["retracted"] += 1
        self.logger.info("ASR_PROVISIONAL_RETRACT qa_id=%s reason=%s", prov.qa_id, reason)
        self.broadcast({"type": "guidance_fast_retract", "id": prov.qa_id, "reason": reason})

    def expire_provisional(self, cfg, now_mono: float) -> None:
        prov = self.provisional
        if prov is None or self.pending_group is not None or self.merge_parts:
            return
        ttl = float(getattr(cfg, "assist_provisional_ttl_sec", 8.0) or 8.0)
        if now_mono - prov.emitted_mono >= ttl:
            self.retract_provisional("not_confirmed")

    def reset_merge_buffer(self):
        self.merge_parts = []
        self.merge_mono_first = None
        self.merge_mono_last = None

    def reset_pending_group(self):
        self.pending_group = None

    def note_speech_activity(self, now_mono: float) -> None:
        """Keep provisional boundaries open while live ASR still hears speech.

        Final STT segments can arrive before a long interviewer turn is over.
        A newer streaming partial is direct evidence that the same speaker is
        still talking, so both the transcript merge window and question
        confirmation window must move forward.
        """
        if self.merge_parts:
            self.merge_mono_last = max(self.merge_mono_last or now_mono, now_mono)
        if self.pending_group is not None:
            self.pending_group.last_mono = max(self.pending_group.last_mono, now_mono)

    def flush_question_group_now(self, cfg, session) -> None:
        group = self.pending_group
        if group is None:
            return
        self.pending_group = None
        auto_mode = str(getattr(cfg, "assist_auto_answer_mode", "smart") or "smart").lower()
        if auto_mode != "always" and not is_viable_asr_question_group(
            group.utterances,
            getattr(cfg, "transcription_min_sig_chars", 2),
        ):
            self.broadcast({
                "type": "question_parse_status",
                "stage": "ignored",
                "message": "这段内容不像完整问题，已继续等待",
                "raw_text": " ".join(group.utterances),
            })
            self.retract_provisional("final_not_a_question")
            return
        last_qa = session.get_last_qa() if hasattr(session, "get_last_qa") else None
        parsed = parse_question_turn(
            group.utterances,
            previous_question=str(getattr(last_qa, "question", "") or ""),
        )
        if not parsed.clusters:
            self.broadcast({
                "type": "question_parse_status",
                "stage": "ignored",
                "message": "未识别到可回答的问题",
                **parsed.payload(),
            })
            self.retract_provisional("final_not_a_question")
            return
        now_mono = self.clock()
        high_churn_short = self.is_high_churn_submission(cfg, now_mono)
        turn_id = self.begin_asr_turn()
        self.record_asr_turn(now_mono)
        self.logger.info(
            "ASR_QUESTION turn=%d utterances=%d clusters=%d churn=%s text=%r",
            turn_id, len(group.utterances), len(parsed.clusters), high_churn_short,
            parsed.raw_text[:150],
        )
        self.broadcast({
            "type": "question_parse_status",
            "stage": "parsed",
            "message": (
                f"已识别 {len(parsed.clusters)} 个独立问题"
                if len(parsed.clusters) > 1
                else f"已识别问题，包含 {len(parsed.clusters[0].subquestions)} 个子问"
            ),
            "turn_id": turn_id,
            **parsed.payload(),
        })
        cluster_count = len(parsed.clusters)
        prov_index = self._provisional_cluster_index(parsed.clusters)
        for cluster_index, cluster in enumerate(parsed.clusters):
            # The answer id is assigned here so an early Fast Cue (emitted
            # before the late-constraint grace) and the later deep answer
            # land on the same card.
            qa_id = f"qa-t{turn_id}-{cluster_index}-{int(time.time() * 1000)}"
            early = bool(getattr(cfg, "intelligence_early_cue", True)) and self.early_cue is not None
            prov = self.provisional if cluster_index == prov_index else None
            relation = ""
            if prov is not None:
                # The authoritative transcription confirms the provisional cue
                # on the same card; a changed question re-renders the cue.
                self.provisional = None
                qa_id = prov.qa_id
                relation = reconcile_relation(prov.question, cluster.task_question())
                self.provisional_stats[relation] += 1
                self.logger.info("ASR_PROVISIONAL_RECONCILE qa_id=%s relation=%s", qa_id, relation)
            if early and relation != "same":
                try:
                    self.early_cue(cluster.task_question(), qa_id, {
                        "source": group.source,
                        "question_type": cluster.question_type,
                        "display_question": cluster.display_question(),
                        **({"reconciled": relation} if relation else {}),
                    })
                except Exception as exc:  # noqa: BLE001
                    early = False
                    self.logger.warning("early cue failed: %s", exc)
            self.submit_answer_task(
                (
                    cluster.task_question(),
                    None,
                    False,
                    group.source,
                    {
                        "qa_id": qa_id,
                        "early_cue_emitted": early,
                        "provisional_relation": relation,
                        "question_confirmed_mono": now_mono,
                        "origin": "asr",
                        "asr_kind": "promote" if group.has_promote else "candidate",
                        "asr_turn_id": turn_id,
                        "utterances": list(group.utterances),
                        "high_churn_short_answer": high_churn_short or cluster_count > 1,
                        "dispatch_after_mono": now_mono + _asr_late_constraint_grace_sec(cfg),
                        "asr_tail_grace_until_mono": now_mono + _asr_late_constraint_grace_sec(cfg),
                        "question_cluster": cluster.payload(),
                        "structured_question_prompt": cluster.answer_prompt(),
                        "display_question": cluster.display_question(),
                        "question_type": cluster.question_type,
                        "cluster_index": cluster_index,
                        "cluster_count": cluster_count,
                    },
                )
            )

    def try_flush_question_group(self, cfg, session, now_mono: float, force: bool = False) -> None:
        group = self.pending_group
        if group is None:
            self.expire_provisional(cfg, now_mono)
            return
        confirm = _asr_confirm_window_sec(cfg)
        fast_confirm = _asr_fast_confirm_sec(cfg)
        max_wait = _asr_group_max_wait_sec(cfg)
        if group.has_promote and len(group.utterances) == 1:
            max_wait = max(max_wait, fast_confirm + confirm)
        since_last = now_mono - group.last_mono
        age = now_mono - group.first_mono
        if force or age >= max_wait:
            self.flush_question_group_now(cfg, session)
        elif group.has_promote and len(group.utterances) == 1 and since_last >= fast_confirm:
            self.flush_question_group_now(cfg, session)
        elif group.has_promote and since_last >= confirm:
            self.flush_question_group_now(cfg, session)
        elif not group.has_promote and since_last >= confirm * 2:
            self.flush_question_group_now(cfg, session)

    def handle_auto_detect_asr_text(self, cfg, session, pub: str, source: str, now_mono: float) -> None:
        if not is_auto_answer_enabled(cfg):
            return
        kind, cleaned = classify_asr_question_candidate(
            pub,
            getattr(cfg, "transcription_min_sig_chars", 2),
        )
        if not cleaned:
            return
        # The classifier normalizes punctuation for scoring.  Keep the raw
        # separators for semantic turn parsing so two questions in one ASR
        # segment can still become two independent answer tasks.
        group_text = (pub or "").strip() if any(mark in (pub or "") for mark in "?？;；。") else cleaned
        if str(getattr(cfg, "assist_auto_answer_mode", "smart") or "smart").lower() == "always" and kind == "candidate":
            kind = "promote"
        if (
            self.pending_group is None
            and kind == "candidate"
            and is_asr_question_constraint_tail(cleaned)
            and self.append_late_constraint_tail(group_text, source, now_mono)
        ):
            return
        if (
            self.pending_group is not None
            and kind == "candidate"
            and is_asr_question_constraint_tail(cleaned)
        ):
            self.pending_group.utterances.append(group_text)
            self.pending_group.last_mono = now_mono
            self.pending_group.source = source
            return
        self.try_flush_question_group(cfg, session, now_mono, False)
        if kind == "ignore" and self.pending_group is None:
            return
        if self.pending_group is None:
            self.pending_group = PendingASRGroup(
                source=source,
                utterances=[group_text],
                first_mono=now_mono,
                last_mono=now_mono,
                has_promote=(kind == "promote"),
            )
        else:
            self.pending_group.utterances.append(group_text)
            self.pending_group.last_mono = now_mono
            self.pending_group.source = source
            self.pending_group.has_promote = self.pending_group.has_promote or kind == "promote"
        self.broadcast({
            "type": "question_parse_status",
            "stage": "assembling",
            "message": "正在判断问题边界",
            "raw_text": " ".join(self.pending_group.utterances),
            "utterance_count": len(self.pending_group.utterances),
        })

    def flush_merge_buffer_now(self, cfg, session) -> None:
        if not self.merge_parts:
            return
        parts = list(self.merge_parts)
        self.merge_parts.clear()
        self.merge_mono_first = None
        self.merge_mono_last = None
        merged_raw = join_transcription_fragments(parts)
        min_sig = getattr(cfg, "transcription_min_sig_chars", 2)
        pub = transcription_for_publish(merged_raw, min_sig)
        if not pub:
            return
        session.add_transcription(pub)
        self.broadcast({"type": "transcription", "text": pub})
        if is_auto_answer_enabled(cfg):
            source = (
                "conversation_loopback"
                if session.capture_is_loopback
                else "conversation_mic"
            )
            self.handle_auto_detect_asr_text(cfg, session, pub, source, self.clock())

    def try_flush_merge_buffer(self, cfg, session, now_mono: float, force: bool = False) -> None:
        if not self.merge_parts:
            return
        gap = float(getattr(cfg, "assist_transcription_merge_gap_sec", 2.0) or 0.0)
        max_wait = float(getattr(cfg, "assist_transcription_merge_max_sec", 12.0) or 12.0)
        if max_wait < 1.0:
            max_wait = 12.0
        if force:
            self.flush_merge_buffer_now(cfg, session)
            return
        if gap <= 0:
            return
        if self.merge_mono_last is None:
            return
        since_last = now_mono - self.merge_mono_last
        burst_age = (now_mono - self.merge_mono_first) if self.merge_mono_first is not None else 0.0
        if bool(getattr(cfg, "assist_eot_fast_flush", True)):
            from services.intelligence.eot import looks_like_complete_question

            # R2: when the merged text already reads as a finished question,
            # only a short quiet period is needed. Speech activity (a newer
            # streaming partial) still moves merge_mono_last forward, so a
            # speaker who keeps talking is never cut off.
            if looks_like_complete_question(" ".join(self.merge_parts)):
                eot_gap = float(getattr(cfg, "assist_eot_merge_gap_sec", 0.35) or 0.35)
                gap = min(gap, max(0.1, eot_gap))
        if since_last >= gap or burst_age >= max_wait:
            self.flush_merge_buffer_now(cfg, session)

    def append_transcription_fragment(
        self,
        cfg,
        session,
        pub: str,
        now_mono: float,
        force_flush_tail: bool = False,
    ) -> None:
        if (
            self.provisional is None
            and bool(getattr(cfg, "assist_final_provisional_cue", True))
            and _looks_like_complete_question(pub)
        ):
            # The authoritative text already reads as a finished question:
            # show the cue now; the merge / group windows (~0.8 s) that wait
            # for a continuation then confirm or correct it on the same card.
            source = "conversation_loopback" if getattr(session, "capture_is_loopback", False) else "conversation_mic"
            self.submit_provisional(cfg, session, pub, source, now_mono)
        gap = float(getattr(cfg, "assist_transcription_merge_gap_sec", 2.0) or 0.0)
        if gap <= 0:
            session.add_transcription(pub)
            self.broadcast({"type": "transcription", "text": pub})
            if is_auto_answer_enabled(cfg):
                source = (
                    "conversation_loopback"
                    if session.capture_is_loopback
                    else "conversation_mic"
                )
                self.handle_auto_detect_asr_text(cfg, session, pub, source, now_mono)
            return
        if not self.merge_parts:
            self.merge_mono_first = now_mono
        self.merge_parts.append(pub)
        self.merge_mono_last = now_mono
        if force_flush_tail:
            self.flush_merge_buffer_now(cfg, session)
        else:
            self.try_flush_merge_buffer(cfg, session, now_mono, False)


def _looks_like_complete_question(text: str) -> bool:
    from services.intelligence.eot import looks_like_complete_question

    return looks_like_complete_question(text)


def _asr_confirm_window_sec(cfg) -> float:
    confirm = float(getattr(cfg, "assist_asr_confirm_window_sec", 0.45) or 0.0)
    return max(0.0, min(5.0, confirm))


def _asr_group_max_wait_sec(cfg) -> float:
    max_wait = float(getattr(cfg, "assist_asr_group_max_wait_sec", 1.2) or 0.0)
    return max(0.2, min(8.0, max_wait))


def _asr_fast_confirm_sec(cfg) -> float:
    fast = float(getattr(cfg, "assist_asr_fast_confirm_sec", 1.15) or 0.0)
    return max(0.1, min(2.0, fast))


def _asr_late_constraint_grace_sec(cfg) -> float:
    grace = float(getattr(cfg, "assist_asr_late_constraint_grace_sec", 1.2) or 0.0)
    return max(0.0, min(3.0, grace))


def asr_interrupt_running(cfg) -> bool:
    return bool(getattr(cfg, "assist_asr_interrupt_running", True))
