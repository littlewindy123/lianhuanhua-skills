from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _srt_timestamp(seconds: float) -> str:
    seconds = max(0.0, seconds)
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def write_srt(path: Path, segments: Iterable[dict]) -> None:
    lines: list[str] = []
    for index, segment in enumerate(segments, start=1):
        lines.extend(
            [
                str(index),
                f"{_srt_timestamp(float(segment['start']))} --> {_srt_timestamp(float(segment['end']))}",
                str(segment.get("text", "")).strip(),
                "",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_srt_timestamp(value: str) -> float:
    hours, minutes, rest = value.strip().replace(".", ",").split(":")
    seconds, millis = rest.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def parse_srt(path: Path) -> list[dict]:
    blocks = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").split("\n\n")
    segments: list[dict] = []
    for block in blocks:
        rows = [row for row in block.splitlines() if row.strip()]
        if len(rows) < 2:
            continue
        timing_index = 1 if "-->" not in rows[0] else 0
        if timing_index >= len(rows) or "-->" not in rows[timing_index]:
            continue
        start_text, end_text = rows[timing_index].split("-->", 1)
        text = "\n".join(rows[timing_index + 1 :]).strip()
        segments.append(
            {
                "id": f"seg_{len(segments)+1:03d}",
                "text": text,
                "start": parse_srt_timestamp(start_text),
                "end": parse_srt_timestamp(end_text),
                "emotion": "",
                "words": [],
            }
        )
    return segments
