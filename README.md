# 连环画 Skills

> 一张角色参考图，加一段文案、音频或视频，生成角色连续、画风统一的竖屏连环画短视频。

[English README](README_EN.md)

连环画 Skills 是一个面向 **OpenAI Codex** 的技能包。它让 Codex 负责导演工作：分析故事、建立角色和画风档案、规划分镜、导出图片提示词、组织素材，并用 Python 与 FFmpeg 完成音频、字幕、时间轴和视频合成。

这一版默认以“省 token”为优先：图片阶段会先让用户选择生图方式，默认不做逐图视觉校验，也不会偷偷调用 `$imagegen` 修图。

## 推荐工作流：省 token 外部生图

```text
文案/音频/视频 + 角色图
→ 旁白/时间轴/分镜
→ 导出 image_prompt_pack.md
→ 用户拿提示词包去 GPT 或其他工具一次性生成图片
→ 回传 panel_001.png、panel_002.png ...
→ Codex 做低成本文件校验和 FFmpeg 合成
```

默认校验只检查：

- 图片文件是否齐全；
- 图片是否能被读取；
- 宽高比例是否接近目标；
- JSON schema 是否正确；
- 最终视频是否通过 ffprobe。

默认不检查：

- 角色是否漂移；
- 画风是否漂移；
- 构图和情绪是否足够好；
- 是否需要重画。

这些由用户肉眼确认。只有用户明确要求“帮我看这张图”或选择严格校验时，Codex 才做视觉检查。

## 生图模式

`project.json` 支持：

```json
{
  "image_workflow": {
    "mode": "ask",
    "review": "none",
    "repair": "ask"
  }
}
```

- `mode: ask`：默认，到图片阶段前让用户选一次。
- `mode: external`：只导出提示词包，不调用 `$imagegen`。
- `mode: codex`：Codex 内置 `$imagegen` 自动生图。
- `mode: hybrid`：关键图用 Codex，其余外部生成。
- `review: none`：默认，不做视觉校验。
- `review: manual`：列出图片路径，让用户自己确认。
- `review: strict`：用户明确要求时才逐图视觉检查。
- `repair: ask`：默认，发现问题先问用户。
- `repair: prompt-only`：只给修图提示词。
- `repair: codex`：允许 Codex 调 `$imagegen` 修图。

## 安装到 Codex

直接给 Codex 这个 GitHub 地址即可：

```text
请从 https://github.com/littlewindy123/lianhuanhua-skills 安装 lianhuanhua skill，路径是 plugins/lianhuanhua/skills/lianhuanhua
```

本地开发时也可以指向仓库目录里的 skill 路径：

```text
请安装 C:/path/to/lianhuanhua-skills/plugins/lianhuanhua/skills/lianhuanhua 这个 skill
```

## 第一次运行

需要：

- Python 3.10+
- FFmpeg 与 ffprobe
- Codex CLI / Codex app
- 文案模式下需要豆包语音 API Key

安装 Python 依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r plugins/lianhuanhua/skills/lianhuanhua/scripts/requirements.txt
```

Windows PowerShell：

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r plugins\lianhuanhua\skills\lianhuanhua\scripts\requirements.txt
```

配置豆包语音：

```bash
export DOUBAO_API_KEY="your-api-key"
```

Windows PowerShell：

```powershell
$env:DOUBAO_API_KEY="your-api-key"
```

普通用户不需要先找音色 ID。Skill 内置截至 2026-06-25 官方列表中的 442 个豆包 TTS 2.0 音色，会根据文案、情绪、受众、语种和用户偏好自动选择。

如果想试听或复制指定音色 ID：

- [豆包语音官方音色列表](https://www.volcengine.com/docs/6561/1257544)
- [豆包语音控制台](https://console.volcengine.com/speech/app)

## 在 Codex 中调用

```text
使用 $lianhuanhua，把 character.png 和 story.txt 制作成 9:16 的情绪连环画短视频。图片阶段先让我选择省 token 模式。
```

外部生图模式下，Codex 会输出：

- `output/image_prompt_pack.md`
- `output/image_prompt_pack.json`

你可以把 `image_prompt_pack.md` 整个复制给 GPT，让它一次性生成 8～10 张图，再把图片按指定文件名放回工作区。

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
│   ├── image_prompt_pack.md
│   ├── image_prompt_pack.json
│   ├── silent_video.mp4
│   ├── narration.mp3
│   ├── subtitles.srt
│   ├── final_video.mp4
│   ├── timeline.json
│   ├── storyboard.json
│   └── panels/
└── logs/
```

## 能力边界

- 默认省 token，不承诺自动视觉审稿。
- 外部生图质量由用户选择的图片工具决定。
- Codex 内置 `$imagegen` 仍可用于全自动模式或单张修图。
- 第一版不做口型同步、骨骼动画或真正的视频生成。
- 使用他人声音、角色或图片时，请确保拥有授权。

## 项目结构

```text
lianhuanhua-skills/
├── plugins/lianhuanhua/
│   ├── .codex-plugin/plugin.json
│   └── skills/lianhuanhua/
│       ├── SKILL.md
│       ├── scripts/
│       ├── references/
│       └── assets/
├── examples/
├── docs/
├── README.md
├── README_EN.md
└── LICENSE
```

## License

MIT。第三方模型、服务和工具仍遵循其各自许可与服务条款。
