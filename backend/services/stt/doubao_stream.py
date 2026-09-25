"""可复用的豆包流式 ASR 会话：feed 16k PCM 块，边收边回调部分结果。

供主页「候选人(自己)声音」等实时转录路径复用。
"""

from __future__ import annotations

import numpy as np
import queue
import threading
import time
from typing import Callable, Optional

from services.stt.engines import (
    DOUBAO_ASR_WS_URL,
    MSG_ERROR,
    MSG_FULL_SERVER_RESPONSE,
    _audio_to_pcm_int16,
    _build_ws_frame_audio,
    _build_ws_frame_full_request,
    _parse_doubao_result_payload,
    _parse_ws_response,
)
from services.stt.engines import DoubaoSTT


class DoubaoStreamSession:
    """一次豆包流式识别会话：start 后 feed 16k int16 PCM 字节，部分结果实时回调。

    使用 bigmodel_async（双向流式优化版）+ enable_nonstream 二遍识别：
    - 边说边出字：非 definite 的增量文本实时回调 on_partial（前端灰字）
    - 分句判停（end_window_size）后服务端返回 definite 分句，提交到已定稿文本，
      并通过 on_final 回调；on_partial 继续展示「已定稿 + 当前增量」。
    """

    def __init__(
        self,
        engine: DoubaoSTT,
        on_partial: Optional[Callable[[str], None]] = None,
        on_final: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        self._engine = engine
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_error = on_error
        self._ws = None
        self._feed_queue: queue.Queue[bytes] = queue.Queue(maxsize=2000)
        self._stop = threading.Event()
        self._committed: list[str] = []
        self._partial = ""
        self._last_shown = ""
        self._final_text = ""
        self._started = False
        self._reader_thread: Optional[threading.Thread] = None
        self._sender_thread: Optional[threading.Thread] = None
        self._last_error = ""

    def start(self) -> None:
        import websocket as _ws

        engine = self._engine
        app_key = engine.app_id or engine.access_token or engine.api_key
        boosting = engine.boosting_table_id or ""
        headers = [f"{k}: {v}" for k, v in engine._build_headers().items()]
        # Live previews must fail over quickly.  The authoritative batch STT
        # has its own longer timeout; waiting ten seconds here blocks the audio
        # worker and makes a transient network issue look like non-realtime STT.
        conn = _ws.create_connection(DOUBAO_ASR_WS_URL, header=headers, timeout=4)
        self._ws = conn
        try:
            conn.send_binary(
                _build_ws_frame_full_request(
                    app_key,
                    boosting,
                    language="",
                    result_type="single",
                    end_window_size=320,
                    force_to_speech_time=1000,
                )
            )
        except Exception:
            try:
                conn.close()
            finally:
                self._ws = None
            raise
        time.sleep(0.02)
        self._started = True
        self._sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self._sender_thread.start()
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def feed(self, audio) -> None:
        """Feed audio: float32 16k mono ndarray (converted to int16 PCM) or raw int16 bytes."""
        if not self._started or self._stop.is_set():
            return
        if isinstance(audio, np.ndarray):
            pcm = _audio_to_pcm_int16(audio).tobytes()
        else:
            pcm = bytes(audio or b"")
        if not pcm:
            return
        try:
            self._feed_queue.put_nowait(pcm)
        except queue.Full:
            pass

    def _sender_loop(self) -> None:
        ws = self._ws
        while not self._stop.is_set():
            try:
                data = self._feed_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                ws.send_binary(_build_ws_frame_audio(data, is_last=False))
            except Exception:
                break
        while True:
            try:
                data = self._feed_queue.get_nowait()
            except queue.Empty:
                break
            try:
                ws.send_binary(_build_ws_frame_audio(data, is_last=False))
            except Exception:
                break
        try:
            ws.send_binary(_build_ws_frame_audio(b"", is_last=True))
        except Exception:
            pass

    def _handle_result(self, payload: dict) -> None:
        info = _parse_doubao_result_payload(payload)
        changed = False
        if info["definite"]:
            for d in info["definite"]:
                if not self._committed or self._committed[-1] != d:
                    self._committed.append(d)
                    changed = True
            self._partial = ""
        if info["partial"]:
            self._partial = info["partial"]
            changed = True
        elif not info["definite"] and info["text"]:
            # No utterance-level info: fall back to result.text as live partial.
            self._partial = info["text"]
            changed = True
        self._final_text = "".join(self._committed)
        shown = self._final_text + self._partial
        if changed and shown and shown != self._last_shown:
            self._last_shown = shown
            if self._on_partial is not None:
                try:
                    self._on_partial(shown)
                except Exception:
                    pass
        if info["definite"] and self._on_final is not None:
            try:
                self._on_final(self._final_text)
            except Exception:
                pass

    def _reader_loop(self) -> None:
        ws = self._ws
        ws.settimeout(15)
        while True:
            try:
                raw = ws.recv()
            except Exception as exc:
                message = str(exc)
                is_timeout = isinstance(exc, TimeoutError) or "timed out" in message.lower() or "timeout" in message.lower()
                if is_timeout and not self._stop.is_set():
                    # Long interviewer pauses are normal. Keep the persistent
                    # stream alive instead of silently losing live partials.
                    continue
                if not self._stop.is_set():
                    self._report_error(message or type(exc).__name__)
                break
            if raw is None:
                break
            if isinstance(raw, str):
                raw = raw.encode("utf-8")
            msg_type, payload = _parse_ws_response(raw)
            if msg_type == MSG_ERROR:
                self._report_error("豆包流式识别服务返回错误")
                break
            if msg_type == MSG_FULL_SERVER_RESPONSE and payload:
                try:
                    self._handle_result(payload)
                except Exception:
                    pass

    def _report_error(self, message: str) -> None:
        self._last_error = (message or "豆包流式识别连接中断").strip()
        if self._on_error is not None:
            try:
                self._on_error(self._last_error)
            except Exception:
                pass

    def reset_segment(self) -> None:
        """段切换：只清空展示状态，保留同一 WS 连接继续流式识别。

        避免每个 VAD 段都重连 WebSocket（每次握手 ~100-300ms），
        让下一段第一个字能立刻出 partial。
        """
        self._committed = []
        self._partial = ""
        self._last_shown = ""
        self._final_text = ""

    def finish(self) -> str:
        if not self._started:
            return ""
        self._stop.set()
        if self._sender_thread is not None and self._sender_thread.is_alive():
            self._sender_thread.join(timeout=2)
        # The sender emits the last-audio frame. Give the reader a short tail
        # to receive the final server result, then close deterministically.
        if self._ws is not None:
            try:
                self._ws.settimeout(0.5)
            except Exception:
                pass
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2)
        try:
            if self._ws is not None:
                self._ws.close()
        except Exception:
            pass
        return self._final_text or self._last_shown
