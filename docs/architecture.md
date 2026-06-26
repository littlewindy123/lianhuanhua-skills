# Architecture

## Responsibility split

### Codex

- Understand the user's intent and emotional tone.
- Normalize narration text.
- Build character, style, and continuity specifications.
- Split narration into visual beats.
- Export a complete image prompt pack for low-token external generation by default.
- Invoke `$imagegen` only when the user chooses Codex or hybrid image generation.
- Use strict visual review only when requested; default validation is file/schema/aspect/ffprobe based.
- Decide when to retry or repair a panel.

### Python

- Create and validate the workspace.
- Call Doubao Speech 2.0.
- Parse subtitle events and normalize timestamps.
- Extract audio from user media.
- Optionally transcribe existing media using faster-whisper.
- Build prompt files from structured JSON.
- Validate schemas and file existence.
- Call FFmpeg and ffprobe.

### FFmpeg

- Extract and normalize audio.
- Render Ken Burns-style panel motions.
- Crossfade or cut panels.
- Produce silent video.
- Burn optional subtitles.
- Mux narration into final MP4.

## State files

- `project.json`: user choices and paths.
- `narration_plan.json`: TTS text, voice direction, and pauses.
- `timeline.json`: normalized narration segments and words.
- `character_bible.json`: immutable identity traits and allowed variations.
- `style_bible.json`: fixed visual direction.
- `continuity_ledger.json`: state carried between panels.
- `storyboard.json`: absolute shot timing, prompts, motion, and transitions.
- `panel_reviews.json`: optional strict visual review results and retries.

The JSON files are the contract between creative agent work and deterministic scripts.
