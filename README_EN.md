# Lianhuanhua Skills

> Turn one character reference and a story, audio file, or video into a consistent narrated vertical comic video.

[中文说明](README.md)

Lianhuanhua Skills is an OpenAI Codex skill package. Codex acts as the director: it analyzes the story, creates character and style bibles, plans panels, exports image prompts, organizes assets, and lets Python plus FFmpeg handle audio, subtitles, timelines, and video assembly.

This version defaults to a low-token workflow. Before image generation, Codex asks the user to choose a mode. It does not visually review every panel or silently call `$imagegen` unless the user chooses that path.

## Recommended low-token workflow

```text
story/audio/video + character image
→ narration/timeline/storyboard
→ export image_prompt_pack.md
→ user generates all panels in GPT or another image tool
→ user returns panel_001.png, panel_002.png ...
→ Codex performs low-cost checks and FFmpeg assembly
```

Default validation checks only:

- panel files exist,
- images are readable,
- aspect ratios are close to target,
- JSON schemas pass,
- final media passes ffprobe.

Default validation does not judge character drift, style drift, composition, or emotional quality. The user reviews images visually. Codex performs strict visual review only when explicitly requested.

## Image workflow

`project.json` supports:

```json
{
  "image_workflow": {
    "mode": "ask",
    "review": "none",
    "repair": "ask"
  }
}
```

- `mode: ask`: default; ask once before image generation.
- `mode: external`: export prompts only; do not call `$imagegen`.
- `mode: codex`: use Codex's built-in `$imagegen`.
- `mode: hybrid`: Codex generates anchors/key panels; the user generates the rest externally.
- `review: none`: default; no visual review.
- `review: manual`: list panel paths for the user to review.
- `review: strict`: visually inspect panels and write `panel_reviews.json`.
- `repair: ask`: default; ask before repair.
- `repair: prompt-only`: export repair prompts only.
- `repair: codex`: allow Codex to repair with `$imagegen`.

## Install in Codex

Give Codex the GitHub repo and skill path:

```text
Install the lianhuanhua skill from https://github.com/littlewindy123/lianhuanhua-skills at plugins/lianhuanhua/skills/lianhuanhua
```

For local development:

```text
Install the skill from C:/path/to/lianhuanhua-skills/plugins/lianhuanhua/skills/lianhuanhua
```

## Requirements

- Python 3.10+
- FFmpeg and ffprobe
- Codex CLI/app
- Doubao Speech API key for text narration mode

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r plugins/lianhuanhua/skills/lianhuanhua/scripts/requirements.txt
```

For bundled voices, configure only `DOUBAO_API_KEY`. The skill includes all 442 official TTS 2.0 voices captured on June 25, 2026 and selects one from the content and natural-language preference. `DOUBAO_SPEAKER` is an optional advanced override.

- [Official Doubao voice list](https://www.volcengine.com/docs/6561/1257544)
- [Doubao Speech console](https://console.volcengine.com/speech/app)

## Example prompt

```text
Use $lianhuanhua to turn character.png and story.txt into a 9:16 emotional comic video. Ask me before image generation so I can choose the low-token workflow.
```

External mode writes:

- `output/image_prompt_pack.md`
- `output/image_prompt_pack.json`

Copy `image_prompt_pack.md` into GPT or another image generator, generate all panels, then place the returned images at the exact output paths.

## License

MIT. Third-party tools, models, and hosted services retain their own licenses and terms.
