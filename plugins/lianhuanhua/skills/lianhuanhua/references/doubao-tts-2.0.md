# Doubao Speech 2.0 integration

## V1 contract

- Endpoint: `wss://openspeech.bytedance.com/api/v3/tts/bidirection`
- Resource header: `X-Api-Resource-Id: seed-tts-2.0`
- New-console authentication: `X-Api-Key`
- Optional trace header: `X-Api-Connect-Id`, always unique for a new connection.
- Audio formats: use MP3 for final narration or PCM while debugging streaming audio.
- Set MP3 bit rate explicitly; the service documentation warns that an unsuitable default can cause quality loss.

## Timing

For TTS 2.0 use:

```json
{
  "audio_params": {
    "enable_subtitle": true
  }
}
```

The service can emit multiple subtitle events while audio generation continues. Do not assume subtitle events arrive before later audio frames. Collect events until `SessionFinished`, then sort by timestamps.

`enable_timestamp` belongs to the TTS 1.0/ICL 1.0 behavior and is not the V1 timing path for this plugin.

## Expressive direction

The V3 documentation describes:

- `model`: standard or expressive mode.
- `audio_params.emotion` and `emotion_scale` for voices that support them.
- `audio_params.speech_rate` and `loudness_rate`.
- `additions.context_texts` for a natural-language voice instruction; rely on the first list item.
- `additions.section_id` for related serial requests.
- `additions.silence_duration` for final trailing silence.

Prefer a restrained instruction such as:

```text
Please narrate slowly and gently, with restrained sadness and clear pauses. Do not sound theatrical.
```

Do not blindly apply unsupported emotions to every speaker. Keep speaker capabilities in project configuration.

## Connection sequence

1. WebSocket upgrade.
2. Send `StartConnection` event 1.
3. Wait for `ConnectionStarted` event 50.
4. Send `StartSession` event 100 with voice/audio configuration.
5. Wait for `SessionStarted` event 150.
6. Send one or more `TaskRequest` events 200 containing text.
7. Send `FinishSession` event 102 when no more text remains.
8. Collect audio/subtitle events until `SessionFinished` event 152.
9. Send `FinishConnection` event 2.

The bundled client stores raw decoded events in JSONL. Never log API keys.
