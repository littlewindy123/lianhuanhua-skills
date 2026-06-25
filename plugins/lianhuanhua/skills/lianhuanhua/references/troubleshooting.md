# Troubleshooting

## Doubao connection fails

- Confirm the API key. A speaker ID is optional when `project.tts.voice_preference` resolves through the bundled catalog.
- For a different preset or custom voice, copy the speaker ID from `https://console.volcengine.com/speech/app`.
- Confirm `X-Api-Resource-Id` is `seed-tts-2.0`.
- Generate a fresh connection and session ID.
- Preserve `X-Tt-Logid` when available.
- Inspect `logs/doubao_events.jsonl` without exposing credentials.

## Audio exists but no subtitle events

- Confirm `enable_subtitle` is true.
- Confirm the selected voice/resource is TTS 2.0.
- Avoid incompatible SSML/LaTeX settings.
- Fall back to local transcription rather than inventing times.

## Character changes between panels

- Verify immutable traits are specific.
- Regenerate the character sheet if it already drifted.
- Use an approved anchor and previous approved panel.
- Edit only the incorrect trait.
- Reduce simultaneous scene/style changes.

## FFmpeg render fails

- Run `doctor`.
- Inspect the exact command in logs.
- Check panel dimensions and file paths.
- Retry the failing shot, not the entire project.
- On Windows, use absolute paths when subtitle filters fail.
