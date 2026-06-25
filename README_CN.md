# 连环画 Skills

> 一张角色参考图，加一段文案、音频或视频，自动生成角色连续、画风统一的竖屏连环画短视频。

连环画 Skills 是一个仅适配 **OpenAI Codex** 的可安装插件。它把 Codex 当作导演：分析故事、建立角色档案、规划分镜、调用内置 `$imagegen` 顺序生成连续画面；把 Python 和 FFmpeg 当作剪辑工具：生成/提取音频、建立时间轴、拼接无声视频、合成最终成片。

## 第一版能力

- 文案模式：文案 + 角色图 → 豆包语音合成 2.0 → 字幕时间轴 → 连环画分镜 → 视频。
- 媒体模式：已有音频/视频 + 角色图 → 抽取音频 → 可选本地 faster-whisper 转写 → 时间轴 → 视频。
- 豆包语音：只支持 `seed-tts-2.0`，使用 WebSocket 双向流式 V3。
- 图片生成：使用 Codex 内置 `$imagegen`（GPT Image 2）生成或编辑图片。
- 一致性流程：角色档案、角色设定图、画风档案、场景状态、关键帧、顺序生图、逐图复核、失败重试。
- 视频输出：FFmpeg 生成无声视频、旁白音频、字幕、最终完整视频及全部中间图片。

## 它不是普通的“图片转视频”

核心思路是：

```text
语音决定真实时间
        ↓
一句旁白可以拆成 1～4 个视觉画面
        ↓
每张画面继承同一个角色和场景状态
        ↓
静态图通过推近、平移、轻微呼吸和转场形成动态感
```

## 安装到 Codex

仓库上传 GitHub 后：

```bash
codex plugin marketplace add littlewindy123/lianhuanhua-skills
```

然后在 Codex 中打开 `/plugins`，选择 **连环画 Skills** 安装。

本地测试：

```bash
codex plugin marketplace add /absolute/path/to/lianhuanhua-skills
```

## 第一次运行

### 1. 安装基础依赖

需要：

- Python 3.10+
- FFmpeg 与 ffprobe
- Codex CLI / Codex app

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r plugins/lianhuanhua/skills/lianhuanhua/scripts/requirements.txt
```

Windows：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r plugins\lianhuanhua\skills\lianhuanhua\scripts\requirements.txt
```

### 2. 配置豆包语音

普通用户不需要先寻找音色 ID。Skill 内置了截至 2026-06-25 官方列表中的 442 个豆包 TTS 2.0 音色，会根据文案、情绪、受众、语种和用户偏好自动选择。

也可以搜索目录：

```bash
python plugins/lianhuanhua/skills/lianhuanhua/scripts/lianhuanhua_cli.py voices --query "温柔 成熟 克制 女声"
```

只需配置 API Key：

```bash
export DOUBAO_API_KEY="your-api-key"
```

Windows PowerShell：

```powershell
$env:DOUBAO_API_KEY="your-api-key"
```

如果想换成其他预设音色，可前往：

- [豆包语音官方音色列表](https://www.volcengine.com/docs/6561/1257544)
- [豆包语音控制台](https://console.volcengine.com/speech/app)：试听音色并复制音色 ID

如果想使用自己的声音，可在控制台进入“声音复刻”，上传已获授权的声音样本，训练完成后复制音色 ID。随后把 ID 写入 `project.json` 的 `tts.speaker`，或设置：

```powershell
$env:DOUBAO_SPEAKER="your-speaker-id"
```

`DOUBAO_SPEAKER` 是高级覆盖项，不是普通用户的必填配置。官方列表更新后，应重新同步 `assets/voice-catalog.json`。

### 3. 在 Codex 中调用

上传一张角色图和一份文案，然后说：

```text
使用 $lianhuanhua，把 character.png 和 story.txt 制作成 9:16 的伤感连环画短视频。
```

Codex 会按照阶段执行，并在需要调用图片生成时显式使用 `$imagegen`。

## 输出目录

```text
workspace/
├── input/
│   ├── story.txt
│   ├── character/
│   └── media/
├── work/
│   ├── audio/
│   ├── timeline.json
│   ├── subtitles.srt
│   ├── character_bible.json
│   ├── style_bible.json
│   ├── continuity_ledger.json
│   ├── storyboard.json
│   ├── prompts/
│   └── panels/
├── output/
│   ├── silent_video.mp4
│   ├── narration.mp3
│   ├── subtitles.srt
│   ├── final_video.mp4
│   ├── timeline.json
│   ├── storyboard.json
│   └── panels/
└── logs/
```

## 两种输入模式

### 文案模式

```text
story.txt + character.png
→ 豆包 TTS 2.0
→ narration.mp3 + TTSSubtitle
→ timeline.json
```

TTS 2.0 使用 `enable_subtitle: true` 获取基于原文的字幕和字词时间，不使用只适用于 TTS 1.0 的 `enable_timestamp`。

### 已有音频/视频模式

```text
input.mp4
→ FFmpeg 抽取 16k 单声道 WAV
→ faster-whisper（可选、本地 CPU 可运行）
→ timeline.json
```

安装媒体转写扩展：

```bash
pip install -r plugins/lianhuanhua/skills/lianhuanhua/scripts/requirements-asr.txt
```

也可以跳过 ASR，直接提供 SRT 或已经整理好的 `timeline.json`。

## 角色一致性的核心规则

1. 先读取参考图，写 `character_bible.json`，明确不可变特征。
2. 先生成并确认 `character_sheet.png`，再开始剧情画面。
3. 先生成场景关键帧，再生成中间画面。
4. 不并发生成全部图片；后图参考原图、角色设定图、最近关键帧和上一张通过审核的画面。
5. 优先“编辑上一张”，不要每一张从零生成。
6. 每张生成后由 Codex 视觉检查；不合格只修当前图，最多重试两次。
7. 所有 Prompt 自动保存，方便复现和继续扩展。

## 当前边界

- 图片模型仍有随机性，无法承诺 100% 一致；Skill 通过参考图链、固定角色档案和复核重试降低漂移。
- 豆包 WebSocket V3 的事件格式可能随服务更新而变化；客户端保留原始事件日志，方便 Codex 根据最新返回修正解析器。
- 第一版不做口型同步、骨骼动画或真正的视频生成。
- 使用他人声音、角色或图片时，请确保拥有授权。

## 项目结构

```text
lianhuanhua-skills/
├── .agents/plugins/marketplace.json
├── plugins/lianhuanhua/
│   ├── .codex-plugin/plugin.json
│   ├── assets/
│   └── skills/lianhuanhua/
│       ├── SKILL.md
│       ├── agents/openai.yaml
│       ├── scripts/
│       ├── references/
│       └── assets/
├── examples/
├── docs/
├── README.md
├── README_CN.md
└── LICENSE
```

## License

MIT。第三方模型、服务和工具仍遵循其各自许可与服务条款。
