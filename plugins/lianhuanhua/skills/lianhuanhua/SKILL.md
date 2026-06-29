---
name: lianhuanhua
description: Create a narrated vertical comic-style short video from a story, audio file, or video plus one or more character reference images. Use for 连环画, comic slideshow, illustrated narration, emotional Douyin/TikTok/Reels videos, character-consistent image sequences, Doubao Speech 2.0 TTS, subtitle timelines, Codex image generation, and FFmpeg assembly. Do not use for fully generated cinematic video, lip-sync animation, or requests that require a text-to-video/image-to-video model.
---

# Lianhuanhua

Create a complete, reproducible comic-video project. Codex directs the story and images. Bundled scripts handle audio, timelines, validation, and FFmpeg rendering.

## Non-negotiable constraints

- Support Codex CLI workflow and local Studio V0.3.
- Use Doubao Speech 2.0 as the only hosted TTS provider.
- Use `X-Api-Resource-Id: seed-tts-2.0`.
- For TTS 2.0 timing, request `audio_params.enable_subtitle=true`; do not rely on the TTS 1.0-only `enable_timestamp` behavior.
- Default Studio image workflow is Codex automatic generation with node confirmations. Do not use visual inspection unless the user chooses strict review.
- Do not call text-to-video or image-to-video models.
- Never claim success until the final media passes ffprobe validation.
- Preserve raw service events and generated prompts for debugging and reproducibility.
- Do not generate all story panels in parallel when using Codex image generation. Generate anchors first, then panels sequentially.
- Default Studio image workflow is `mode=codex`, `review=none`, `repair=ask`.

## Resolve paths

Treat the directory containing this `SKILL.md` as `SKILL_ROOT`.

The CLI entry point is:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py"
```

Use an absolute path when the shell or operating system makes relative paths ambiguous.

Run the local Studio V0.3 web UI with:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" studio --workspace <workspace>
```

Studio is a local-only HTML/CSS/JavaScript interface backed by Python's standard library HTTP server. It is for local project work, not production hosting.

## Inputs

Require:

1. Either at least one character/reference image, or a concrete visual style description.
2. Exactly one story source:
   - written narration text, or
   - existing audio, or
   - existing video.

Optional:

- Desired mood and visual style.
- Desired voice in ordinary language, such as “温柔成熟女声” or “沉稳男声”.
- Advanced override: a Doubao speaker ID.
- Image workflow:
  - `external`: export prompts only; the user generates images elsewhere and returns files.
  - `codex`: Codex uses `$imagegen`.
  - `hybrid`: Codex generates key images only; the user generates the rest externally.
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
Studio also preserves:

1. `work/studio_state.json`
2. `output/prompts-package.zip`
3. `output/prompts.json`

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

## Studio V0.3 handoff protocol

When the user says "继续" in Codex while working from Studio:

1. Find the current project workspace.
2. Read `work/studio_state.json`.
3. Execute only the task named by `action`.
4. If `panel_id` exists, process only that one panel.
5. Stop at the next confirmation node and let the user return to Studio.
6. Do not score all images, repair all images, or retry unrelated panels unless the current action explicitly asks for it.

Studio V0.3 is a single creation cockpit. Users enter narration, Doubao key, voice, speech rate, aspect ratio, reference images or style text, and image density. The main flow is Codex automatic generation, with confirmations at `voice_ready`, `storyboard_ready`, `images_ready`, and `video_ready`.

Allowed stages are `create`, `voice`, `storyboard`, `images`, and `video`.

Allowed actions are:

- `generate_voice`
- `generate_full_project`
- `generate_storyboard_and_prompts`
- `generate_all_panels`
- `regenerate_panel`
- `validate_manual_panels`
- `render_video`
- `confirm_voice`
- `confirm_storyboard`
- `confirm_images`

Do not write Doubao API keys to `project.json`, `studio_state.json`, `prompts.json`, or exported packages. Studio may store the key only in `work/.secrets.json`, which is excluded by `.gitignore`.

## Phase 1A: Text narration mode

1. Read `references/doubao-tts-2.0.md`.
2. Normalize punctuation and line breaks without changing the story's meaning.
3. Create `work/narration_plan.json` from the bundled template.
4. Select the voice automatically from the story, mood, audience, language, and requested style. Do not ask ordinary users for a speaker ID.
5. Search the bundled official TTS 2.0 catalog when choosing:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" voices --query "<natural-language voice preference>"
```

6. The catalog contains all 442 official TTS 2.0 voices captured from the official voice list on 2026-06-25. Write the chosen voice name or natural-language preference to `project.tts.voice_preference`.
7. If the user explicitly supplies a speaker ID, write it to `project.tts.speaker`; it overrides automatic selection.
8. If the user asks where to find or create a voice, explain:
   - preset voices: audition and copy the ID from the Doubao Speech console's voice library,
   - custom voices: create an authorized voice through Voice Replication, then copy its speaker ID,
   - official voice list: `https://www.volcengine.com/docs/6561/1257544`,
   - console: `https://console.volcengine.com/speech/app`.
9. Require only `DOUBAO_API_KEY` for a bundled catalog voice. Treat `DOUBAO_SPEAKER` as an advanced optional override.
10. Prefer one continuous TTS request for naturalness unless the story requires major voice-direction changes.
11. Use `seed-tts-2.0-expressive` when voice instructions are required and the selected voice supports it.
12. Put the primary voice direction in `additions.context_texts`; only its first item is relied upon.
13. Generate audio and subtitle events:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" tts --workspace <workspace>
```

14. Verify that `work/audio/narration.*`, `work/timeline.json`, and `work/subtitles.srt` exist.
15. If the API returns audio but no subtitles, keep the audio and raw event log, then use the media transcription fallback only after explaining the fallback in the project log.

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
6. If the user chose `codex` or `hybrid`, use `$imagegen` to create `work/character_sheet.png` from the original reference image.
7. If the user chose `external`, do not call `$imagegen`; keep the original reference images as the visual lock and let the exported prompt pack describe the desired panels.
8. Only visually inspect the character sheet when the user chose `codex`, `hybrid`, or explicitly asked for visual checking.

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
2. If `project.image_workflow.mode` is missing or `ask`, Studio V0.3 should default to `codex`. In CLI-only workflows, stop once and ask the user to choose:
   - `external`: cheapest; export prompt pack only, user generates images in GPT or another image tool.
   - `codex`: most automatic; use `$imagegen` inside Codex.
   - `hybrid`: Codex generates anchors/key images, user generates ordinary panels externally.
3. Save the choice to `project.image_workflow.mode`. Studio defaults to `codex`; default review is `none`; default repair is `ask`.
4. Build deterministic prompt files and the external prompt pack:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" build-prompts --workspace <workspace>
```

This writes both `work/prompts/*.md` and:

- `output/image_prompt_pack.md`
- `output/image_prompt_pack.json`
- `output/prompts-package.zip`
- `output/prompts.json`

5. For `external` mode:
   - Do not call `$imagegen`.
   - Return `output/image_prompt_pack.md` to the user.
   - Tell the user they can paste the pack into GPT or another image generator, create all panels in one batch, save files with the exact `Output path`, then return them.
   - When the user returns images, run low-cost validation only: existence, readability, target aspect ratio, schema checks, and later ffprobe.
   - Do not inspect visual quality, character drift, or style drift unless the user explicitly asks.
6. For `codex` mode, generate anchor frames first:
   - opening state,
   - major scene changes,
   - emotional turning point,
   - ending state.
7. Invoke `$imagegen` explicitly for every generated or edited image only in `codex` or selected `hybrid` steps.
8. Attach, in this order when available:
   - original character reference,
   - approved character sheet,
   - current scene anchor,
   - previous approved panel.
9. Prefer editing the previous approved panel for small changes. Generate from references only when the scene changes substantially.
10. Save output exactly to the path assigned in `storyboard.json`.
11. Do not write `work/panel_reviews.json` by default. If `project.image_workflow.review` is `manual`, list generated image paths for the user to inspect. If it is `strict`, visually inspect panels and write/update `work/panel_reviews.json`.
12. If a file is missing or unreadable, report the exact path. Do not auto-generate or auto-repair unless `project.image_workflow.repair` is `codex` or the user explicitly asks.
13. If the user says a panel is wrong, either export a targeted repair prompt (`prompt-only`) or use `$imagegen` to repair only that panel when the user chooses Codex repair.

## Studio Phase 4A: Manual image package

For manual image generation, provide `output/prompts-package.zip`.

The ZIP must contain:

- `README.md`
- `prompts.md`
- `prompts.csv`
- `prompts.json`
- `panels/panel_001.txt`, `panels/panel_002.txt`, and so on.

When manual images are returned, perform deterministic checks only: filenames, duplicates, missing panels, file size, readability, target aspect ratio, schema checks, and later ffprobe. Do not judge image quality or style drift unless explicitly asked.

## Phase 5: Render

1. Read `references/rendering.md`.
2. Confirm every storyboard image exists.
3. Use low-cost image checks only unless the user requested strict visual review:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" validate --workspace <workspace> --require-images
```

4. Render the silent video:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" render --workspace <workspace> --silent-only
```

5. Render final video with narration and optional subtitles:

```bash
python "$SKILL_ROOT/scripts/lianhuanhua_cli.py" render --workspace <workspace> --burn-subtitles
```

6. Use subtle motion. Emotional comic videos normally use slow zoom, pan, hold, and restrained crossfades.
7. Ensure video duration matches narration within 100 ms unless the project explicitly adds a post-roll.

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
- Image drift: in default low-token mode, ask the user which panel to fix and whether to export a repair prompt or use `$imagegen`; do not regenerate the entire story.
- FFmpeg failure: preserve the full command and stderr; rerender the failing clip only.
- Schema failure: fix JSON before continuing. Do not let the renderer guess missing creative fields.
