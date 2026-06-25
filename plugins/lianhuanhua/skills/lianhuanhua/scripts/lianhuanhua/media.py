from __future__ import annotations

from pathlib import Path
from typing import Any

from .subtitles import write_srt
from .timeline import normalize_timeline
from .utils import ensure_dir, media_duration, run_command, write_json


def extract_audio(input_path: Path, output_path: Path, log_path: Path) -> Path:
    ensure_dir(output_path.parent)
    run_command(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ],
        log_path=log_path,
    )
    return output_path


def transcribe_faster_whisper(
    audio_path: Path,
    *,
    model_size: str = "small",
    language: str = "zh",
    device: str = "cpu",
    compute_type: str = "int8",
) -> dict[str, Any]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper is not installed. Install scripts/requirements-asr.txt or provide SRT/timeline.json."
        ) from exc

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    result_segments, info = model.transcribe(
        str(audio_path),
        language=language or None,
        vad_filter=True,
        word_timestamps=True,
        beam_size=5,
    )

    segments: list[dict[str, Any]] = []
    for index, segment in enumerate(result_segments, start=1):
        words: list[dict[str, Any]] = []
        for word in segment.words or []:
            if word.start is None or word.end is None:
                continue
            words.append(
                {
                    "word": word.word.strip(),
                    "start": float(word.start),
                    "end": float(word.end),
                    "confidence": float(word.probability) if word.probability is not None else None,
                }
            )
        segments.append(
            {
                "id": f"seg_{index:03d}",
                "text": segment.text.strip(),
                "start": float(segment.start),
                "end": float(segment.end),
                "emotion": "",
                "words": words,
            }
        )

    timeline = normalize_timeline(
        segments,
        source="faster-whisper",
        audio_file=str(audio_path),
        duration=media_duration(audio_path),
    )
    timeline["transcription"] = {
        "language": getattr(info, "language", language),
        "language_probability": getattr(info, "language_probability", None),
        "model_size": model_size,
        "device": device,
        "compute_type": compute_type,
    }
    return timeline


def save_transcription(timeline: dict[str, Any], timeline_path: Path, srt_path: Path) -> None:
    write_json(timeline_path, timeline)
    write_srt(srt_path, timeline["segments"])
