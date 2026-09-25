# 语音识别热词（豆包 ASR）

- **词表文件**：[doubao_hotwords_面试技术词表.txt](./doubao_hotwords_面试技术词表.txt)（每行一词，UTF-8）
- **配置与上传步骤**：见上级文档 [豆包语音识别.md](../豆包语音识别.md) 第三节「热词表」

本地 **Whisper** 使用的技术词库与纠错规则在代码中维护：`backend/services/stt.py` 内 `TECH_VOCAB`、`TERM_CORRECTIONS`（非本目录文件）。


## 本地流式 Whisper（成竹实时出字）

- **stt_provider=whisper** 时，实时辅助（面试官 + 候选人自己）默认走**本地 GPU 流式 Whisper 预览**：
  后台滑动窗口增量解码（beam_size=1、固定语言、带技术热词），边听边出字，目标 100~300ms/批。
  最终转录仍走权威批式路径（beam_size=3），流式只是"加法"预览，失败不回归。
- 相关配置（config.json）：
  - `whisper_stream_enabled`：总开关（默认 true）
  - `whisper_stream_interval_ms`：解码间隔 ms（默认 280）
  - `whisper_stream_min_sec` / `whisper_stream_window_sec`：最短/最长解码窗口（秒）
  - `whisper_model`：推荐 `small`（中文够用且快）~ `medium`/`large-v3`（更准更慢）
  - `whisper_language`：建议 `zh`（中文面试）；`auto` 会偏向英文
- 流式引擎复用工厂已加载的 whisper 模型 + 全局推理锁，**不会重复加载模型、不额外占显存**。
- CUDA 运行库（cuBLAS/cuDNN）由 `services/stt/_cuda.py` 自动定位（torch/lib、nvidia pip wheel、CUDA toolkit），
  无需手动设置 PATH。首次使用模型需联网下载（HF 直连不通时可用 `hf-mirror.com`，设环境变量 `HF_ENDPOINT`）。

## 麦克风自适应增益

- 麦克风路径默认启用自适应增益（`mic_agc_enabled=true`），解决低音量麦克风"完全不出字"的问题。
- `mic_agc_max_gain`（默认 40）与 `mic_agc_noise_gate`（默认 0.0006）可调；采集过低调大 max_gain，底噪大调高 noise_gate。
