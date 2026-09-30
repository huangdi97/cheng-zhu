"""Lexical end-of-turn cue (R2 Stage I, 12.2).

Used only to shorten waits that exist to catch "more speech is coming":
when the transcribed text already reads as a finished question, the merge
buffer is flushed immediately instead of waiting the full merge gap.
Rollback stays with the existing machinery: later fragments are still
grouped as late constraints / continuations, and an interrupting new turn
cancels a running answer.
"""
from __future__ import annotations

import re

_TERMINAL_PUNCT = re.compile(r"[？?]\s*$")
_ZH_QUESTION_TAIL = re.compile(r"(?:吗|呢|么|没有|是什么|为什么|怎么样|如何|哪些|多少|几个|怎么做|怎么办|区别|原理)[。.！!]?\s*$")
_ZH_REQUEST_HEAD = re.compile(r"^(?:请|麻烦)?(?:讲讲|讲一下|说说|说一下|介绍一下|谈谈|解释一下|描述一下|聊聊)")
_EN_QUESTION_HEAD = re.compile(r"^(?:what|why|how|when|where|which|who|can you|could you|would you|do you|did you|have you|tell me|explain|describe|walk me)\b", re.IGNORECASE)
# Dangling connectors mean the sentence is not finished yet.
_DANGLING = re.compile(r"(?:和|还有|以及|然后|比如|就是|那个|因为|所以|而且|但是|或者|的|and|or|but|because|like|the|a|an|of|to|with)[，,\s]*$", re.IGNORECASE)
_MIN_CHARS = 6
# Chinese questions often carry the interrogative mid-sentence and end on a
# noun ("消息队列怎么保证不丢消息"); a long enough sentence with one is done
# unless it ends on a connector (checked first).
_ZH_INTERROGATIVE = re.compile(r"怎么|怎样|为什么|为何|如何|哪些|哪个|哪里|什么|多少|是否|有没有|能不能|会不会|讲讲|说说|介绍一下|谈谈")
_MIN_INTERROGATIVE_CHARS = 8


def looks_like_complete_question(text: str) -> bool:
    value = (text or "").strip()
    if len(value) < _MIN_CHARS or _DANGLING.search(value):
        return False
    if _TERMINAL_PUNCT.search(value) or _ZH_QUESTION_TAIL.search(value):
        return True
    # A request-shaped sentence that ended with a full stop ("讲讲你的项目。").
    if re.search(r"[。.！!]\s*$", value) and (_ZH_REQUEST_HEAD.search(value) or _EN_QUESTION_HEAD.search(value)):
        return True
    if len(value) >= _MIN_INTERROGATIVE_CHARS and (_ZH_INTERROGATIVE.search(value) or _EN_QUESTION_HEAD.search(value)):
        return True
    return False
