---
name: lianhuanhua
description: Create a narrated vertical comic-style short video from a story, audio file, or video plus one or more character reference images. Use for 连环画, comic slideshow, illustrated narration, emotional Douyin/TikTok/Reels videos, character-consistent image sequences, Doubao Speech 2.0 TTS, subtitle timelines, Codex image generation, and FFmpeg assembly. Do not use for fully generated cinematic video, lip-sync animation, or requests that require a text-to-video/image-to-video model.
---

# Lianhuanhua

Create a complete, reproducible comic-video project. Codex directs the story and images. Bundled scripts handle audio, timelines, validation, and FFmpeg rendering.

## Non-negotiable constraints

- Support Codex only in version 0.1.
- Use Doubao Speech 2.0 as the only hosted TTS provider.
- Use `X-Api-Resource-Id: seed-tts-2.0`.
- For TTS 2.0 timing, request `audio_params.enable_subtitle=true`; do not rely on the TTS 1.0-only `enable_timestamp` behavior.
- Use Codex's built-in `$imagegen` skill to generate or edit panels.
- Do not call text-to-video or image-to-video models.
- Never claim success until the final media passes ffprobe validation.
- Preserve raw service events and generated prompts for debugging and reproducibility.
- Do not generate all story panels in parallel. Generate anchors first, then panels sequentially.

## Resolve paths

Treat the directory containing this `SKILL.md` as `SKILL_ROOT`.

The CLI entry point is:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py"
```

Use an absolute path when the shell or operating system makes relative paths ambiguous.

## Inputs

Require:

1. At least one character/reference image.
2. Exactly one story source:
   - written narration text, or
   - existing audio, or
   - existing video.

Optional:

- Desired mood and visual style.
- Doubao speaker ID.
- Existing SRT or timeline JSON.
- Background music.
- Output dimensions; default to 1080x1920, 30 fps.
- Target subtitle font.

## Outputs

Always preserve and return:

1. `output/silent_video.mp4`
2. `output/narration.*`
3. `output/subtitles.srt`
4. `output/final_video.mp4`
5. `output/timeline.json`
6. `output/storyboard.json`
7. `output/panels/`
8. `logs/`

Also preserve the character/style/continuity JSON files and panel prompts in `work/`.

## Read references progressively

Read only the reference needed for the current phase:

- Overall phases: `references/workflow.md`
- Doubao TTS: `references/doubao-tts-2.0.md`
- Existing audio/video: `references/audio-timeline.md`
- Character lock: `references/character-consistency.md`
- Storyboard creation: `references/storyboard-rules.md`
- Image generation: `references/image-generation.md`
- Rendering: `references/rendering.md`
- Output checks: `references/output-contract.md`
- Failures: `references/troubleshooting.md`

## Phase 0: Preflight

1. Inspect all supplied files.
2. Determine the source mode: `text`, `audio`, or `video`.
3. Confirm that reference images are readable and suitable for the requested aspect ratio.
4. Run:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" doctor
```

5. Initialize a workspace:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" init --workspace <workspace>
```

6. Copy inputs into the initialized `input/` directories without overwriting originals.
7. Do not continue when FFmpeg or ffprobe is missing.

## Phase 1A: Text narration mode

1. Read `references/doubao-tts-2.0.md`.
2. Normalize punctuation and line breaks without changing the story's meaning.
3. Create `work/narration_plan.json` from the bundled template.
4. Prefer one continuous TTS request for naturalness unless the story requires major voice-direction changes.
5. Use `seed-tts-2.0-expressive` when voice instructions are required and the selected voice supports it.
6. Put the primary voice direction in `additions.context_texts`; only its first item is relied upon.
7. Generate audio and subtitle events:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" tts --workspace <workspace>
```

8. Verify that `work/audio/narration.*`, `work/timeline.json`, and `work/subtitles.srt` exist.
9. If the API returns audio but no subtitles, keep the audio and raw event log, then use the media transcription fallback only after explaining the fallback in the project log.

## Phase 1B: Existing audio/video mode

1. Read `references/audio-timeline.md`.
2. Extract normalized WAV from the supplied file:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" extract-media --workspace <workspace> --input <audio-or-video>
```

3. Prefer a supplied SRT or timeline JSON.
4. Otherwise transcribe locally with faster-whisper:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" transcribe --workspace <workspace>
```

5. This transcription is a local alignment utility, not another TTS provider.
6. Review names and emotionally important wording against the user's source before continuing.

## Phase 2: Build the visual identity lock

1. Read `references/character-consistency.md`.
2. Inspect every reference image carefully.
3. Write `work/character_bible.json` using the schema in `assets/schemas/character_bible.schema.json`.
4. Separate:
   - immutable identity traits,
   - mutable pose/expression traits,
   - forbidden changes.
5. Write `work/style_bible.json` using the bundled schema.
6. Use `$imagegen` to create `work/character_sheet.png` from the original reference image.
7. The sheet should include front, profile, three-quarter, full-body, and key expressions when the source supports them.
8. Visually compare the sheet with the original. Reject it if defining traits drift.
9. Do not start story panels until the character sheet passes review.

## Phase 3: Create the storyboard

1. Read `references/storyboard-rules.md`.
2. Read `work/timeline.json` and preserve its absolute timing.
3. Split each narration segment into one to four visual beats based on actions, time changes, location changes, emotional turns, and duration.
4. Do not split merely by character count.
5. Create `work/storyboard.json` using `assets/schemas/storyboard.schema.json`.
6. Each shot must define:
   - absolute start/end,
   - source narration segment,
   - story action,
   - character state,
   - scene state,
   - composition,
   - motion preset,
   - transition,
   - whether it is an anchor frame.
7. Create `work/continuity_ledger.json` and carry state between shots.
8. Validate before image generation:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" validate --workspace <workspace>
```

## Phase 4: Generate consistent panels

1. Read `references/image-generation.md`.
2. Build deterministic prompt files:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" build-prompts --workspace <workspace>
```

3. Generate anchor frames first:
   - opening state,
   - major scene changes,
   - emotional turning point,
   - ending state.
4. Invoke `$imagegen` explicitly for every generated or edited image.
5. Attach, in this order when available:
   - original character reference,
   - approved character sheet,
   - current scene anchor,
   - previous approved panel.
6. Prefer editing the previous approved panel for small changes. Generate from references only when the scene changes substantially.
7. Save output exactly to the path assigned in `storyboard.json`.
8. After each image, inspect it visually and write/update `work/panel_reviews.json`.
9. Review:
   - character identity,
   - accessories and colors,
   - body proportions,
   - drawing style,
   - scene continuity,
   - direction of gaze and movement,
   - extra limbs/features/characters,
   - narration alignment.
10. If a panel fails, repair only that panel. Preserve correct parts. Retry at most twice before asking the user or simplifying the shot.
11. Never use a failed panel in rendering.

## Phase 5: Render

1. Read `references/rendering.md`.
2. Confirm every storyboard image exists.
3. Render the silent video:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" render --workspace <workspace> --silent-only
```

4. Render final video with narration and optional subtitles:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" render --workspace <workspace> --burn-subtitles
```

5. Use subtle motion. Emotional comic videos normally use slow zoom, pan, hold, and restrained crossfades.
6. Ensure video duration matches narration within 100 ms unless the project explicitly adds a post-roll.

## Phase 6: Validate and package

1. Read `references/output-contract.md`.
2. Run:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" validate-output --workspace <workspace>
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" export --workspace <workspace>
```

3. Inspect the final video visually at the beginning, middle, and end.
4. Report any known limitations honestly.
5. Return direct paths to every required deliverable.

## Recovery rules

- TTS failure: preserve request metadata without secrets, response logs, and log ID; retry with a new session ID.
- Missing subtitles: do not invent timings; use the local transcription fallback or ask for an SRT.
- Image drift: return to the last approved anchor or panel; do not regenerate the entire story.
- FFmpeg failure: preserve the full command and stderr; rerender the failing clip only.
- Schema failure: fix JSON before continuing. Do not let the renderer guess missing creative fields.
