---
name: transcribe
description: |
  中文播客音频转 SRT 字幕。使用 OpenAI Whisper API（whisper-1，原生 SRT 输出），
  自动用 ffmpeg 切片处理 25MB 以上的大文件，时间戳偏移后拼接为单一 SRT。
  触发词: transcribe, 转录, 转字幕, 生成字幕, srt, 播客转录, baihua transcribe, 百花 transcribe
---

# 播客音频转 SRT

Plugin root: `transcript/`. 所有命令从该目录运行。

## 触发条件

用户提供一个音频文件路径（`.mp3` / `.m4a` / `.wav`），或者说"转录 episodes/xxx.mp3"。

## 前置依赖

1. **Python 包**：`pip install -r requirements.txt`（首次运行前）
2. **ffmpeg**：系统级依赖。检查：`which ffmpeg && which ffprobe`。macOS 安装：`brew install ffmpeg`
3. **API key**：从 `transcript/.env` 读取 `OPENAI_API_KEY`（gitignored）

## 执行步骤

### Step 1：确认文件存在 + 大小

```bash
ls -lh <audio_path>
```

如果文件 > 25MB，提示用户脚本会自动切片处理（无需用户操作）。

### Step 2：构造 vocabulary prompt（强烈建议）

Whisper 接受 `prompt` 参数来偏置专有名词识别。对中文播客，先问用户：
- 节目名（如「美轮美换」）
- 主持人 / 常出现人物
- 节目里反复出现的英文术语或缩写

**关键：用自然句子，而不是关键词列表。** Whisper 的 prompt 是软偏置——它从 prompt 的语境推断后文风格。空格分隔的关键词列表对**同音词纠正能力很弱**（典型反例：节目名「美轮美换」会被纠回成语「美轮美奂」，即使 prompt 里写了正确版本）。

**好的 prompt 写法**：
```
--prompt "这是一档名叫'美轮美换'的中文政治播客，主持人小华、王浩南、Tanish。常讨论川普、哈里斯、拜登、马斯克、美联储、白宫、国土安全部（DHS）等话题。"
```

**避免的写法**（弱偏置）：
```
--prompt "美轮美换 川普 哈里斯 美联储"   ← 关键词列表，效果差
```

如果用户没提供，跳过这一步——Whisper 仍然能跑，只是专有名词可能识别不准。

### Step 3：运行转录

```bash
cd transcript
python3 transcribe.py <audio_path> --prompt "<natural sentence>"
```

**默认行为**：等时长切片 + 6 路并发上传。85 分钟播客约 3 分钟跑完。

**可选参数**：
- `--out path/to/file.srt`：自定义输出路径（默认音频同目录同名 `.srt`）
- `--workers N`：并发数（默认 6）
- `--silence-aware`：在静音处切片，避免句中切断。会先跑一遍 ffmpeg `silencedetect`，多花 5-10 秒，但字幕边界更干净
- `--max-chunk-mb FLOAT`：调整切片大小上限（默认 24，Whisper 限 25）

### Step 4：报告结果

```
✓ 转录完成：<srt_path>
  时长 X 分钟，切成 N 片，用时约 Y 秒。
```

如果用户希望预览，读 SRT 前 20 行展示。

## 故障排查

- **`NotImplementedError: chunk_audio()`** — 切片函数还没实现，提示用户先填 `transcribe.py` 里的 `chunk_audio()`。
- **`ffmpeg: command not found`** — 提示 `brew install ffmpeg`。
- **`OPENAI_API_KEY not set`** — 检查 `transcript/.env` 是否存在且包含 `OPENAI_API_KEY=...`。
- **API 报 413 / "file too large"** — 切片产物超过 24MB；调小 `MAX_CHUNK_BYTES` 或检查 `chunk_audio()` 实现。

## 设计说明

- **为什么是 Whisper 不是 Gemini**：中文识别更稳，原生 `response_format="srt"` 输出，2 小时播客 ~$0.72。
- **为什么必须切片**：Whisper API 单次上传上限 25MB，2 小时 MP3 通常 100MB+。
- **时间戳偏移**：每片返回的 SRT 时间从 0 开始。`stitch_srt()` 根据 `Chunk.start_offset_s` 把每片的时间戳加上偏移再重新编号。
