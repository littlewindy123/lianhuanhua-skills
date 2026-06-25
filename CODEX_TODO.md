# Codex follow-up checklist

This scaffold is ready for Codex to refine. The following items require live environments or product decisions.

## P0: live Doubao verification

- Test the WebSocket V3 binary client against a real `seed-tts-2.0` speaker.
- Save a sanitized raw event sample as a test fixture.
- Confirm the event code and payload nesting used for `TTSSubtitle`.
- Confirm whether `model=seed-tts-2.0-expressive` is accepted by every intended 2.0 voice.
- Confirm `context_texts` placement in the JSON-string `additions` field.
- Add response `X-Tt-Logid` capture when exposed by the installed websockets version.

## P0: Codex `$imagegen` workflow

- Test exact file-save behavior in Codex CLI and Codex app.
- Confirm how multiple local references are attached in one imagegen turn.
- Add one real end-to-end example with an original, reusable character reference.
- Record which prompt/reference order gives the best identity stability.

## P1: rendering portability

- Test subtitle burning on Windows paths and macOS.
- Add automatic discovery of an installed Chinese font.
- Add blurred-background layout for landscape or square source art.
- Add background-music ducking as an optional feature.

## P1: media input

- Test faster-whisper CPU performance on a 1–2 minute Chinese clip.
- Add VTT import.
- Add optional transcript-assisted alignment for difficult audio.

## P2: open-source launch

- Replace GitHub owner placeholders.
- Add a 10–20 second demo GIF to README.
- Publish repeatable benchmark examples rather than marketing estimates.
- Add GitHub Actions for tests and JSON validation.
- Tag release `v0.1.0` after one real Doubao + imagegen + FFmpeg run.
