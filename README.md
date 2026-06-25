# Lianhuanhua Skills

> Turn one character reference and a story, audio file, or video into a consistent narrated vertical comic video.

Lianhuanhua Skills is a Codex-only installable plugin. Codex acts as the director: it analyzes the story, creates character and style bibles, plans panels, invokes the built-in `$imagegen` skill sequentially, and reviews every panel. Python and FFmpeg provide deterministic media processing.

## Highlights

- Story mode: text + character image → Doubao Speech 2.0 → subtitle timeline → comic panels → video.
- Media mode: audio/video + character image → audio extraction → optional local faster-whisper → timeline → video.
- Character consistency workflow: immutable traits, character sheet, style bible, anchor frames, continuity ledger, sequential edits, review and retry.
- Codex built-in image generation via `$imagegen`.
- Outputs silent video, narration audio, subtitles, all panels, timeline, storyboard, logs, and final MP4.
- No text-to-video or image-to-video model required.

Chinese documentation: [README_CN.md](README_CN.md)

## Install

After pushing this repository to GitHub:

```bash
codex plugin marketplace add littlewindy123/lianhuanhua-skills
```

Open `/plugins` in Codex and install **Lianhuanhua Skills**.

For local testing:

```bash
codex plugin marketplace add /absolute/path/to/lianhuanhua-skills
```

## Example prompt

```text
Use $lianhuanhua to turn character.png and story.txt into a 9:16 emotional comic video.
```

## Requirements

- Python 3.10+
- FFmpeg and ffprobe
- Codex CLI/app
- Doubao Speech API key for text-to-speech mode

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r plugins/lianhuanhua/skills/lianhuanhua/scripts/requirements.txt
```

For built-in voices, configure only `DOUBAO_API_KEY`. The skill automatically selects a voice profile from the content. `DOUBAO_SPEAKER` is an optional advanced override.

- [Official Doubao voice list](https://www.volcengine.com/docs/6561/1257544)
- [Doubao Speech console](https://console.volcengine.com/speech/app) for auditioning preset voices or creating an authorized replicated voice

## Status

Alpha. The deterministic pipeline and schemas are ready for iteration. Doubao's binary WebSocket protocol is implemented from the V3 specification, while raw event logging is retained so Codex can quickly adapt the parser if the service response changes.

## License

MIT. Third-party tools, models, and hosted services retain their own licenses and terms.
