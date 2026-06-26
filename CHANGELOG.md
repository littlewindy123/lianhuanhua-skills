# Changelog

## Unreleased

- Add low-token image workflow configuration: `ask`, `external`, `codex`, and `hybrid`.
- Export `output/image_prompt_pack.md` and `output/image_prompt_pack.json` from `build-prompts`.
- Make visual panel review optional; default validation checks files, readability, aspect ratio, schemas, and ffprobe only.
- Make GitHub's default README Chinese-first and move English docs to `README_EN.md`.

## 0.1.2

- Bundle all 442 official Doubao Speech TTS 2.0 voices captured on 2026-06-25.
- Add natural-language catalog search through the `voices` CLI command.
- Resolve voice names and preferences to speaker IDs without exposing IDs to ordinary users.
- Keep explicit project or environment speaker IDs as advanced overrides.

## 0.1.1

- Let Codex automatically select a natural-language voice profile from the story.
- Add built-in Doubao Speech 2.0 profiles for reflective and caring narration.
- Make speaker IDs optional for ordinary users while preserving explicit overrides.
- Document where to audition preset voices and create authorized replicated voices.

## 0.1.0

- Initial Codex-only plugin structure.
- Doubao Speech 2.0 WebSocket V3 client scaffold.
- Subtitle/timeline normalization.
- Optional local faster-whisper transcription for existing media.
- Character bible, style bible, continuity ledger, and storyboard schemas.
- Sequential `$imagegen` workflow for consistent panels.
- FFmpeg silent-video rendering and final audio muxing.
