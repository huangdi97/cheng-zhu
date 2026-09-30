"""Controlled audio benchmark corpus (v1.2-R2 latency closure, Stage B).

    python scripts/latency_corpus.py            # (re)generate missing fixtures
    python scripts/latency_corpus.py --force    # regenerate everything

Speech is synthesized offline with Windows SAPI voices (Huihui zh-CN,
Zira / David en-US). Noise conditions are mixed in deterministically
(seeded): light background noise, keyboard clicks, speaker echo, and a
no-speech clip. Ground truth comes from the *clean* synthesized speech, so
noise can move the VAD but never the truth.

Each fixture in ``backend/evals/latency_corpus/manifest.json`` has:
  audio, transcript_expected, speech_end_ground_truth (s), question_expected
  (keywords the confirmed question must contain), content_type, lang,
  condition, previous_question (for follow-ups), pause_ms (internal pauses).

Honest limits: SAPI voices are synthetic and clean-studio; real human
recordings with accents, disfluency and room acoustics are not in this
corpus (real multi-hour audio is listed as BLOCKED-EXTERNAL).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "evals" / "latency_corpus"
SR = 16000
ZH, ZIRA, DAVID = "Microsoft Huihui Desktop", "Microsoft Zira Desktop", "Microsoft David Desktop"

# id, voice, rate, ssml text, expected keywords, content type, extra
CASES: list[dict] = [
    # --- Chinese ---
    {"id": "zh-short", "voice": ZH, "text": "Redis 是单线程的吗？", "expect": ["单线程"], "type": "KNOWLEDGE"},
    {"id": "zh-long", "voice": ZH, "text": "你之前负责的订单系统，在大促的时候峰值流量大概是平时的几倍，你们当时是怎么做容量评估和限流降级的？", "expect": ["限流"], "type": "SYSTEM_DESIGN"},
    {"id": "zh-internal-pause", "voice": ZH, "text": "如果流量扩大十倍<break time=\"700ms\"/>你的系统哪里会先扛不住？", "expect": ["扛不住"], "type": "SYSTEM_DESIGN", "pause_ms": 700},
    {"id": "zh-long-pause", "voice": ZH, "text": "我们先聊聊缓存<break time=\"1400ms\"/>为什么选择 Redis 而不是 Memcached？", "expect": ["Memcached"], "type": "KNOWLEDGE", "pause_ms": 1400},
    {"id": "zh-dangling-pause", "voice": ZH, "text": "你们的服务拆分之后，然后<break time=\"900ms\"/>调用链路是怎么做监控的？", "expect": ["监控"], "type": "SYSTEM_DESIGN", "pause_ms": 900},
    {"id": "zh-slow", "voice": ZH, "rate": -4, "text": "消息队列怎么保证不丢消息？", "expect": ["消息"], "type": "KNOWLEDGE"},
    {"id": "zh-fast", "voice": ZH, "rate": 5, "text": "数据库索引为什么用 B 加树？", "expect": ["索引"], "type": "KNOWLEDGE"},
    {"id": "zh-ne", "voice": ZH, "text": "那你们的缓存一致性是怎么做的呢？", "expect": ["一致性"], "type": "FOLLOW_UP", "previous_question": "你们的缓存是怎么设计的？"},
    {"id": "zh-ma", "voice": ZH, "text": "你在生产环境用过 Kubernetes 吗？", "expect": ["生产环境"], "type": "EXPERIENCE"},
    {"id": "zh-zenme", "voice": ZH, "text": "线上出现慢查询的时候你一般怎么排查？", "expect": ["慢查询"], "type": "EXPERIENCE"},
    {"id": "zh-weishenme", "voice": ZH, "text": "为什么你当时没有选择分库分表？", "expect": ["分库分表"], "type": "EXPERIENCE"},
    {"id": "zh-request", "voice": ZH, "text": "讲讲你做过的订单系统重构。", "expect": ["订单"], "type": "EXPERIENCE"},
    {"id": "zh-request-2", "voice": ZH, "text": "介绍一下你最有挑战的一个项目。", "expect": ["项目"], "type": "EXPERIENCE"},
    {"id": "zh-followup-short", "voice": ZH, "text": "为什么？", "expect": ["为什么"], "type": "FOLLOW_UP", "previous_question": "你们为什么选择 Kafka？"},
    {"id": "zh-coding", "voice": ZH, "text": "写一个函数判断链表有没有环，说一下你的思路。", "expect": ["链表"], "type": "CODING"},
    {"id": "zh-clarify", "voice": ZH, "text": "你刚才说的最终一致性，具体是指什么？", "expect": ["一致性"], "type": "CLARIFICATION"},
    # --- English ---
    {"id": "en-short", "voice": ZIRA, "text": "What is a deadlock?", "expect": ["deadlock"], "type": "KNOWLEDGE"},
    {"id": "en-long", "voice": ZIRA, "text": "Walk me through how you would design a URL shortener that handles a billion requests per day, including storage and caching.", "expect": ["shortener"], "type": "SYSTEM_DESIGN"},
    {"id": "en-pause", "voice": DAVID, "text": "If the database becomes the bottleneck,<break time=\"800ms\"/> what would you change first?", "expect": ["change first"], "type": "SYSTEM_DESIGN", "pause_ms": 800},
    {"id": "en-technical", "voice": ZIRA, "text": "How does Kafka guarantee exactly once semantics with idempotent producers?", "expect": ["exactly once"], "type": "KNOWLEDGE"},
    {"id": "en-followup", "voice": DAVID, "text": "Why did you choose that approach?", "expect": ["approach"], "type": "FOLLOW_UP", "previous_question": "How did you shard the user table?"},
    {"id": "en-behavioral", "voice": DAVID, "rate": -3, "text": "Tell me about a time you disagreed with your team.", "expect": ["disagree"], "type": "EXPERIENCE"},
    {"id": "en-coding", "voice": ZIRA, "text": "Can you write a function to reverse a linked list?", "expect": ["linked list"], "type": "CODING"},
    {"id": "en-clarify", "voice": DAVID, "text": "What do you mean by eventual consistency here?", "expect": ["consistency"], "type": "CLARIFICATION"},
    {"id": "en-rate-limiter", "voice": ZIRA, "text": "How would you design a rate limiter for a public API?", "expect": ["rate limit"], "type": "SYSTEM_DESIGN"},
    # --- Mixed ---
    {"id": "mixed-rag", "voice": ZH, "text": "这个 RAG pipeline 如果 QPS 扩大一百倍，你会怎么 scale？", "expect": ["一百倍"], "type": "SYSTEM_DESIGN"},
    {"id": "mixed-kafka", "voice": ZH, "text": "你在项目里用 Kafka 做过 exactly once 吗？", "expect": ["exactly once"], "type": "EXPERIENCE"},
    {"id": "mixed-k8s", "voice": ZH, "text": "你们的 Kubernetes 集群是怎么做 autoscaling 的？", "expect": ["集群"], "type": "SYSTEM_DESIGN"},
    # --- Noise conditions (same speech, different room) ---
    {"id": "noise-bg-zh", "voice": ZH, "text": "消息队列的消费者挂了会发生什么？", "expect": ["消费者"], "type": "KNOWLEDGE", "condition": "background"},
    {"id": "noise-bg-en", "voice": ZIRA, "text": "How would you monitor a distributed system?", "expect": ["monitor"], "type": "SYSTEM_DESIGN", "condition": "background"},
    {"id": "noise-keyboard", "voice": ZH, "text": "你是怎么定位内存泄漏的？", "expect": ["内存泄漏"], "type": "EXPERIENCE", "condition": "keyboard"},
    {"id": "noise-echo-mixed", "voice": ZH, "text": "你们的 Redis cluster 是怎么做 failover 的？", "expect": ["failover"], "type": "SYSTEM_DESIGN", "condition": "echo"},
    {"id": "noise-echo-en", "voice": DAVID, "text": "What trade offs did you make in the cache design?", "expect": ["trade"], "type": "EXPERIENCE", "condition": "echo"},
    {"id": "silence-only", "voice": None, "text": "", "expect": [], "type": "NONE", "condition": "silence"},
]


def _plain(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text).strip()


def _synthesize(case: dict, path: Path) -> None:
    lang = "en-US" if case["voice"] in (ZIRA, DAVID) else "zh-CN"
    ssml = (
        f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{lang}'>"
        f"<voice name='{case['voice']}'>{case['text']}</voice></speak>"
    )
    ssml_file = path.with_suffix(".ssml")
    ssml_file.write_text(ssml, encoding="utf-8")
    ps = (
        "Add-Type -AssemblyName System.Speech;"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.Rate={int(case.get('rate', 0))};"
        "$f=New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono);"
        f"$s.SetOutputToWaveFile('{path}',$f);"
        f"$s.SpeakSsml([IO.File]::ReadAllText('{ssml_file}',[Text.Encoding]::UTF8));$s.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    ssml_file.unlink()


def _read(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def _write(path: Path, audio: np.ndarray) -> None:
    pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _speech_bounds(clean: np.ndarray, threshold: float = 0.004) -> tuple[float, float]:
    frame = 320
    voiced = [i for i in range(0, len(clean) - frame, frame) if float(np.sqrt(np.mean(clean[i:i + frame] ** 2))) > threshold]
    if not voiced:
        return 0.0, 0.0
    return voiced[0] / SR, (voiced[-1] + frame) / SR


def _pink(n: int, rng: np.random.Generator) -> np.ndarray:
    white = rng.standard_normal(n)
    spectrum = np.fft.rfft(white)
    freqs = np.arange(len(spectrum))
    spectrum[1:] /= np.sqrt(freqs[1:])
    pink = np.fft.irfft(spectrum, n)
    return (pink / (np.sqrt(np.mean(pink ** 2)) + 1e-9)).astype(np.float32)


def _apply_condition(clean: np.ndarray, condition: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    audio = clean.copy()
    if condition == "background":
        audio = audio + 0.0035 * _pink(len(audio), rng)  # ~-49 dBFS office hum, below the VAD threshold
    elif condition == "keyboard":
        # key clicks: short decaying bursts during speech and 0.15-0.9 s after it
        clicks = np.zeros_like(audio)
        _, end = _speech_bounds(clean)
        times = list(rng.uniform(0.3, max(0.4, end - 0.2), 6)) + list(end + rng.uniform(0.15, 0.9, 3))
        for t in times:
            i = int(t * SR)
            n = int(0.012 * SR)
            if i + n < len(clicks):
                clicks[i:i + n] += (rng.standard_normal(n) * np.exp(-np.arange(n) / 40.0) * 0.25).astype(np.float32)
        audio = audio + clicks + 0.002 * _pink(len(audio), rng)
    elif condition == "echo":
        # loudspeaker echo into the mic: 120 ms delayed copy at -12 dB + a later -20 dB tap
        delay1, delay2 = int(0.12 * SR), int(0.26 * SR)
        echo = np.zeros_like(audio)
        echo[delay1:] += 0.25 * clean[:-delay1]
        echo[delay2:] += 0.1 * clean[:-delay2]
        audio = audio + echo
    return audio.astype(np.float32)


def build(force: bool = False) -> list[dict]:
    OUT.mkdir(parents=True, exist_ok=True)
    previous = {}
    if (OUT / "manifest.json").exists() and not force:
        previous = {row["id"]: row for row in json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))}
    manifest = []
    for index, case in enumerate(CASES):
        wav = OUT / f"{case['id']}.wav"
        condition = case.get("condition", "clean")
        if wav.exists() and case["id"] in previous:
            # Ground truth was measured on the clean speech when generated.
            manifest.append(previous[case["id"]])
            continue
        if condition == "silence":
            if force or not wav.exists():
                rng = np.random.default_rng(index)
                _write(wav, 0.003 * _pink(int(SR * 3.0), rng))
            manifest.append({
                "id": case["id"], "audio": wav.name, "transcript_expected": "", "speech_end_ground_truth": None,
                "question_expected": [], "content_type": "NONE", "lang": "none", "condition": "silence",
            })
            continue
        clean_path = OUT / f"_{case['id']}.clean.wav"
        if force or not wav.exists():
            _synthesize(case, clean_path)
            # 0.3 s lead-in and a 2.5 s tail so noise / clicks after the question are real input
            clean = np.concatenate([np.zeros(int(0.3 * SR), dtype=np.float32), _read(clean_path), np.zeros(int(2.5 * SR), dtype=np.float32)])
            _write(wav, _apply_condition(clean, condition, index))
            _write(clean_path, clean)
        clean = _read(clean_path) if clean_path.exists() else _read(wav)
        start, end = _speech_bounds(clean)
        manifest.append({
            "id": case["id"],
            "audio": wav.name,
            "transcript_expected": _plain(case["text"]),
            "speech_start_ground_truth": round(start, 3),
            "speech_end_ground_truth": round(end, 3),
            "question_expected": case["expect"],
            "content_type": case["type"],
            "lang": "en" if case["voice"] in (ZIRA, DAVID) else ("mixed" if case["id"].startswith(("mixed", "noise-echo-mixed")) else "zh"),
            "condition": condition,
            "rate": case.get("rate", 0),
            "pause_ms": case.get("pause_ms", 0),
            "previous_question": case.get("previous_question", ""),
        })
    for leftover in OUT.glob("_*.clean.wav"):
        leftover.unlink()
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    rows = build(force=args.force)
    print(f"{len(rows)} fixtures -> {OUT}")
