from __future__ import annotations

from lianhuanhua.timeline import normalize_doubao_subtitles, normalize_timeline


def test_normalize_doubao_subtitles() -> None:
    payloads = [
        {
            "data": {
                "text": "后来我才明白",
                "words": [
                    {"word": "后来", "startTime": 0.1, "endTime": 0.5, "confidence": 0.9},
                    {"word": "明白", "startTime": 0.5, "endTime": 1.0, "confidence": 0.8},
                ],
            }
        }
    ]
    segments = normalize_doubao_subtitles(payloads)
    assert len(segments) == 1
    assert segments[0]["start"] == 0.1
    assert segments[0]["end"] == 1.0


def test_timeline_duration_uses_audio_duration() -> None:
    timeline = normalize_timeline(
        [{"id": "seg_001", "text": "x", "start": 0, "end": 1, "emotion": "", "words": []}],
        source="test",
        audio_file="a.mp3",
        duration=2.0,
    )
    assert timeline["duration"] == 2.0
