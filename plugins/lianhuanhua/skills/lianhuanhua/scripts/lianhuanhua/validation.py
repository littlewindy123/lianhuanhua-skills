from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from .schema_validation import SCHEMA_BY_FILE, validate_file
from .utils import executable, ffprobe, read_json


def doctor_report() -> dict[str, Any]:
    return {
        "python": {
            "version": sys.version.split()[0],
            "ok": sys.version_info >= (3, 10),
        },
        "ffmpeg": {"path": executable("ffmpeg"), "ok": bool(executable("ffmpeg"))},
        "ffprobe": {"path": executable("ffprobe"), "ok": bool(executable("ffprobe"))},
        "python_packages": {
            "websockets": bool(importlib.util.find_spec("websockets")),
            "jsonschema": bool(importlib.util.find_spec("jsonschema")),
            "PIL": bool(importlib.util.find_spec("PIL")),
            "faster_whisper_optional": bool(importlib.util.find_spec("faster_whisper")),
        },
        "environment": {
            "DOUBAO_API_KEY": bool(os.getenv("DOUBAO_API_KEY")),
            "DOUBAO_SPEAKER_optional_override": bool(os.getenv("DOUBAO_SPEAKER")),
            "built_in_voice_profiles": True,
        },
    }


def doctor_ok(report: dict[str, Any]) -> bool:
    return bool(
        report["python"]["ok"]
        and report["ffmpeg"]["ok"]
        and report["ffprobe"]["ok"]
        and report["python_packages"]["websockets"]
        and report["python_packages"]["jsonschema"]
    )


def validate_workspace(workspace: Path, *, require_images: bool = False) -> list[str]:
    errors: list[str] = []
    candidates = [
        workspace / "project.json",
        workspace / "work" / "narration_plan.json",
        workspace / "work" / "timeline.json",
        workspace / "work" / "character_bible.json",
        workspace / "work" / "style_bible.json",
        workspace / "work" / "continuity_ledger.json",
        workspace / "work" / "storyboard.json",
        workspace / "work" / "panel_reviews.json",
    ]
    for path in candidates:
        if not path.exists():
            if path.name in {"timeline.json"}:
                continue
            errors.append(f"Missing required file: {path}")
            continue
        schema_name = SCHEMA_BY_FILE.get(path.name)
        if schema_name:
            errors.extend(f"{path.name}: {message}" for message in validate_file(path, schema_name))

    timeline_path = workspace / "work" / "timeline.json"
    if timeline_path.exists():
        timeline = read_json(timeline_path)
        previous_end = 0.0
        for segment in timeline.get("segments", []):
            start, end = float(segment["start"]), float(segment["end"])
            if end <= start:
                errors.append(f"Timeline segment {segment['id']} has non-positive duration")
            if start < previous_end - 0.05:
                errors.append(f"Timeline segment {segment['id']} overlaps a previous segment unexpectedly")
            previous_end = max(previous_end, end)
        if previous_end > float(timeline.get("duration", 0)) + 0.1:
            errors.append("Timeline duration is shorter than the last segment")

    storyboard_path = workspace / "work" / "storyboard.json"
    storyboard_shots: list[dict[str, Any]] = []
    if storyboard_path.exists():
        storyboard = read_json(storyboard_path)
        shots = storyboard.get("shots", [])
        storyboard_shots = shots
        previous_start = -1.0
        for shot in shots:
            start, end = float(shot["start"]), float(shot["end"])
            if start < previous_start:
                errors.append(f"Storyboard shots are not sorted at {shot['id']}")
            if end <= start:
                errors.append(f"Shot {shot['id']} has non-positive duration")
            previous_start = start
            if require_images:
                image = Path(shot["image"])
                if not image.is_absolute():
                    image = workspace / image
                if not image.exists():
                    errors.append(f"Missing panel for {shot['id']}: {image}")

    if require_images and storyboard_shots:
        reviews_path = workspace / "work" / "panel_reviews.json"
        reviews = read_json(reviews_path).get("reviews", []) if reviews_path.exists() else []
        latest: dict[str, dict[str, Any]] = {}
        for review in reviews:
            shot_id = str(review.get("shot_id", ""))
            if not shot_id:
                continue
            current = latest.get(shot_id)
            if current is None or int(review.get("attempt", 0)) >= int(current.get("attempt", 0)):
                latest[shot_id] = review
        for shot in storyboard_shots:
            review = latest.get(str(shot["id"]))
            if review is None:
                errors.append(f"Missing visual review for {shot['id']}")
            elif not bool(review.get("passed")):
                errors.append(f"Latest visual review failed for {shot['id']}")

    return errors


def validate_output(workspace: Path, *, tolerance_seconds: float = 0.25) -> list[str]:
    errors: list[str] = []
    silent = workspace / "output" / "silent_video.mp4"
    final = workspace / "output" / "final_video.mp4"
    timeline_path = workspace / "work" / "timeline.json"

    for path in [silent, final]:
        if not path.exists() or path.stat().st_size == 0:
            errors.append(f"Missing or empty output: {path}")
            continue
        try:
            info = ffprobe(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ffprobe failed for {path}: {exc}")
            continue
        streams = info.get("streams", [])
        if not any(stream.get("codec_type") == "video" for stream in streams):
            errors.append(f"No video stream in {path}")
        if path == final and not any(stream.get("codec_type") == "audio" for stream in streams):
            errors.append(f"No audio stream in {path}")

    if timeline_path.exists() and final.exists():
        timeline = read_json(timeline_path)
        expected = float(timeline.get("duration", 0))
        try:
            actual = float(ffprobe(final).get("format", {}).get("duration", 0))
            if expected > 0 and abs(actual - expected) > tolerance_seconds:
                errors.append(
                    f"Final duration differs from timeline: expected {expected:.3f}s, got {actual:.3f}s"
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Could not compare final duration: {exc}")

    errors.extend(validate_workspace(workspace, require_images=True))
    return errors
