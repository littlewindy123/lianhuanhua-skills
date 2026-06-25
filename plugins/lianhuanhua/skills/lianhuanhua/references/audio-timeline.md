# Existing audio/video timeline

Codex can inspect media metadata and run tools, but it does not create reliable speech timestamps by intuition. Use deterministic extraction and transcription.

## Preferred inputs

1. Existing `timeline.json`.
2. Existing SRT/VTT.
3. Audio/video plus local faster-whisper.

## Extraction

Normalize to mono 16 kHz PCM WAV for transcription:

```bash
ffmpeg -y -i input.mp4 -vn -ac 1 -ar 16000 -c:a pcm_s16le extracted.wav
```

## Transcription

The optional faster-whisper path uses word timestamps and VAD. CPU `int8` is the default for portability. Review names, numbers, and emotionally important words manually.

## Timeline requirements

- Times are seconds from the start of the final narration.
- Segment order is monotonic.
- Word times must remain inside their parent segment.
- Preserve pauses as real gaps rather than stretching words.
- Do not infer spoken text from silence detection alone.
