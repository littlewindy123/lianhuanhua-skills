from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .subtitles import parse_srt, write_srt
from .utils import media_duration, write_json


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_subtitle_objects(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        words = value.get("words")
        text = value.get("text")
        if isinstance(words, list) and isinstance(text, str):
            found.append(value)
        for nested in value.values():
            found.extend(_extract_subtitle_objects(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_extract_subtitle_objects(nested))
    return found


def normalize_doubao_subtitles(
    event_payloads: Iterable[Any],
    *,
    offset: float = 0.0,
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()

    for payload in event_payloads:
        for subtitle in _extract_subtitle_objects(payload):
            normalized_words: list[dict[str, Any]] = []
            for item in subtitle.get("words", []):
                if not isinstance(item, dict):
                    continue
                start = _to_float(item.get("startTime", item.get("start_time", item.get("start"))))
                end = _to_float(item.get("endTime", item.get("end_time", item.get("end"))))
                word = item.get("word", item.get("text", ""))
                if start is None or end is None or end < start:
                    continue
                normalized_words.append(
                    {
                        "word": str(word),
                        "start": start + offset,
                        "end": end + offset,
                        "confidence": _to_float(item.get("confidence")),
                    }
                )

            if normalized_words:
                start = min(word["start"] for word in normalized_words)
                end = max(word["end"] for word in normalized_words)
            else:
                raw_start = _to_float(
                    subtitle.get("startTime", subtitle.get("start_time", subtitle.get("start")))
                )
                raw_end = _to_float(
                    subtitle.get("endTime", subtitle.get("end_time", subtitle.get("end")))
                )
                if raw_start is None or raw_end is None:
                    continue
                start, end = raw_start + offset, raw_end + offset

            text = str(subtitle.get("text", "")).strip()
            key = (text, int(round(start * 1000)), int(round(end * 1000)))
            if not text or key in seen:
                continue
            seen.add(key)
            segments.append(
                {
                    "id": "",
                    "text": text,
                    "start": start,
                    "end": end,
                    "emotion": "",
                    "words": normalized_words,
                }
            )

    segments.sort(key=lambda item: (item["start"], item["end"], item["text"]))
    for index, segment in enumerate(segments, start=1):
        segment["id"] = f"seg_{index:03d}"
    return segments


def normalize_timeline(
    segments: list[dict[str, Any]],
    *,
    source: str,
    audio_file: str | None,
    duration: float | None = None,
) -> dict[str, Any]:
    ordered = sorted(segments, key=lambda item: (float(item["start"]), float(item["end"])))
    for index, segment in enumerate(ordered, start=1):
        segment["id"] = segment.get("id") or f"seg_{index:03d}"
        segment["start"] = round(float(segment["start"]), 6)
        segment["end"] = round(float(segment["end"]), 6)
        if segment["end"] < segment["start"]:
            raise ValueError(f"Segment ends before it starts: {segment['id']}")
        for word in segment.get("words", []):
            word["start"] = round(float(word["start"]), 6)
            word["end"] = round(float(word["end"]), 6)

    inferred = max((float(item["end"]) for item in ordered), default=0.0)
    total = max(inferred, float(duration or 0.0))
    return {
        "version": "0.1",
        "source": source,
        "audio_file": audio_file,
        "duration": round(total, 6),
        "segments": ordered,
    }


def timeline_from_srt(srt_path: Path, audio_path: Path | None = None) -> dict[str, Any]:
    segments = parse_srt(srt_path)
    duration = media_duration(audio_path) if audio_path and audio_path.exists() else None
    return normalize_timeline(
        segments,
        source="srt",
        audio_file=str(audio_path) if audio_path else None,
        duration=duration,
    )


def write_timeline_files(timeline: dict[str, Any], json_path: Path, srt_path: Path) -> None:
    write_json(json_path, timeline)
    write_srt(srt_path, timeline.get("segments", []))


def load_event_payloads(jsonl_path: Path) -> list[Any]:
    payloads: list[Any] = []
    if not jsonl_path.exists():
        return payloads
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = read_json_line(line)
        payload = record.get("json") if isinstance(record, dict) else None
        if payload is not None:
            payloads.append(payload)
    return payloads


def read_json_line(line: str) -> Any:
    import json

    return json.loads(line)
