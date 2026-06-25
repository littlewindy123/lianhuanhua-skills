from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websockets

from .constants import (
    DOUBAO_ENDPOINT,
    DOUBAO_RESOURCE_ID,
    EVENT_CONNECTION_FAILED,
    EVENT_CONNECTION_STARTED,
    EVENT_FINISH_CONNECTION,
    EVENT_FINISH_SESSION,
    EVENT_SESSION_FAILED,
    EVENT_SESSION_FINISHED,
    EVENT_SESSION_STARTED,
    EVENT_START_CONNECTION,
    EVENT_START_SESSION,
    EVENT_TASK_REQUEST,
    EVENT_TTS_RESPONSE,
)
from .doubao_protocol import (
    MESSAGE_AUDIO_ONLY_RESPONSE,
    decode_frame,
    encode_json_event,
    frame_to_log,
)
from .subtitles import write_srt
from .timeline import normalize_doubao_subtitles, normalize_timeline
from .utils import append_jsonl, ensure_dir, media_duration, run_command, write_json
from .voice_catalog import resolve_catalog_voice


@dataclass
class DoubaoConfig:
    api_key: str
    speaker: str
    model: str = "seed-tts-2.0-expressive"
    audio_format: str = "mp3"
    sample_rate: int = 24000
    bit_rate: int = 128000
    speech_rate: float = 0
    loudness_rate: float = 0
    emotion: str | None = None
    emotion_scale: float = 4
    uid: str = "lianhuanhua"
    timeout_seconds: float = 90.0


class DoubaoError(RuntimeError):
    pass


def _handshake_error_message(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return f"Doubao WebSocket connection failed: {exc}"

    status = getattr(response, "status_code", "unknown")
    body = getattr(response, "body", None)
    if isinstance(body, (bytes, bytearray)):
        body = bytes(body).decode("utf-8", "replace")
    body_text = str(body or "").strip()
    log_id = ""
    headers = getattr(response, "headers", None)
    if headers is not None:
        log_id = str(headers.get("X-Tt-Logid", "")).strip()

    details = f"HTTP {status}"
    if body_text:
        details += f": {body_text}"
    if log_id:
        details += f" (X-Tt-Logid: {log_id})"
    if status == 401:
        details += (
            ". The value must come from Doubao Speech Console > API Key Management; "
            "do not use an APP ID, Access Key, account AK/SK, or another product's key."
        )
    elif status == 403 and "resource not granted" in body_text.casefold():
        details += (
            ". The API key is valid, but its Doubao Speech application isn't authorized for "
            "the requested TTS resource. Open https://console.volcengine.com/speech/app, select "
            "the application that owns this key, and activate/grant Doubao Speech TTS 2.0 "
            "(`seed-tts-2.0`) or obtain the required resource pack."
        )
    return f"Doubao WebSocket connection failed: {details}"


LEGACY_VOICE_PROFILES = {
    "gentle-reflective-female": "温柔白月光 2.0",
    "warm-caring-female": "贴心妹妹 2.0",
}


def resolve_speaker(tts: dict[str, Any]) -> tuple[str, str]:
    explicit = str(tts.get("speaker") or os.getenv("DOUBAO_SPEAKER", "")).strip()
    if explicit:
        return explicit, "explicit"

    query = str(tts.get("voice_preference") or tts.get("voice_profile") or "").strip()
    query = LEGACY_VOICE_PROFILES.get(query, query)
    try:
        resolved = resolve_catalog_voice(query)
    except ValueError as exc:
        raise DoubaoError(str(exc)) from exc
    return str(resolved["id"]), str(resolved["name"])


async def _connect(headers: dict[str, str]):
    # websockets renamed extra_headers to additional_headers in newer versions.
    try:
        try:
            return await websockets.connect(
                DOUBAO_ENDPOINT,
                additional_headers=headers,
                max_size=None,
                ping_interval=20,
                ping_timeout=20,
            )
        except TypeError:
            return await websockets.connect(
                DOUBAO_ENDPOINT,
                extra_headers=headers,
                max_size=None,
                ping_interval=20,
                ping_timeout=20,
            )
    except websockets.exceptions.InvalidStatus as exc:
        raise DoubaoError(_handshake_error_message(exc)) from exc


async def _receive_frame(websocket, timeout: float):
    raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
    if isinstance(raw, str):
        raise DoubaoError(f"Doubao returned a text WebSocket message: {raw}")
    return decode_frame(raw)


def _session_payload(config: DoubaoConfig, instruction: str, section_id: str) -> dict[str, Any]:
    audio_params: dict[str, Any] = {
        "format": config.audio_format,
        "sample_rate": config.sample_rate,
        "bit_rate": config.bit_rate,
        "speech_rate": config.speech_rate,
        "loudness_rate": config.loudness_rate,
        "enable_subtitle": True,
    }
    if config.emotion:
        audio_params["emotion"] = config.emotion
        audio_params["emotion_scale"] = config.emotion_scale

    additions: dict[str, Any] = {
        "disable_markdown_filter": False,
        "silence_duration": 0,
        "section_id": section_id,
    }
    if instruction.strip():
        additions["context_texts"] = [instruction.strip()]

    return {
        "user": {"uid": config.uid},
        "event": EVENT_START_SESSION,
        "namespace": "BidirectionalTTS",
        "req_params": {
            "speaker": config.speaker,
            "model": config.model,
            "audio_params": audio_params,
            # The V3 specification defines additions as a JSON string.
            "additions": json.dumps(additions, ensure_ascii=False, separators=(",", ":")),
        },
    }


def _task_payload(config: DoubaoConfig, text: str) -> dict[str, Any]:
    return {
        "user": {"uid": config.uid},
        "event": EVENT_TASK_REQUEST,
        "namespace": "BidirectionalTTS",
        "req_params": {"text": text},
    }


async def synthesize_once(
    *,
    text: str,
    instruction: str,
    output_audio: Path,
    raw_events: Path,
    config: DoubaoConfig,
    section_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ensure_dir(output_audio.parent)
    ensure_dir(raw_events.parent)
    raw_events.unlink(missing_ok=True)

    connection_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    headers = {
        "X-Api-Key": config.api_key,
        "X-Api-Resource-Id": DOUBAO_RESOURCE_ID,
        "X-Api-Connect-Id": connection_id,
    }

    websocket = await _connect(headers)
    audio_chunks: list[bytes] = []
    json_payloads: list[Any] = []
    metadata: dict[str, Any] = {
        "connection_id": connection_id,
        "session_id": session_id,
        "resource_id": DOUBAO_RESOURCE_ID,
        "speaker": config.speaker,
        "model": config.model,
    }

    try:
        await websocket.send(encode_json_event(EVENT_START_CONNECTION, {}))
        while True:
            frame = await _receive_frame(websocket, config.timeout_seconds)
            append_jsonl(raw_events, frame_to_log(frame))
            if frame.event == EVENT_CONNECTION_FAILED:
                raise DoubaoError(f"Doubao connection failed: {frame.json_payload or frame.payload!r}")
            if frame.event == EVENT_CONNECTION_STARTED:
                metadata["server_connection_id"] = frame.connection_id
                break

        await websocket.send(
            encode_json_event(
                EVENT_START_SESSION,
                _session_payload(config, instruction, section_id),
                session_id=session_id,
            )
        )
        while True:
            frame = await _receive_frame(websocket, config.timeout_seconds)
            append_jsonl(raw_events, frame_to_log(frame))
            if frame.event == EVENT_SESSION_FAILED:
                raise DoubaoError(f"Doubao session failed: {frame.json_payload or frame.payload!r}")
            if frame.event == EVENT_SESSION_STARTED:
                break

        await websocket.send(
            encode_json_event(
                EVENT_TASK_REQUEST,
                _task_payload(config, text),
                session_id=session_id,
            )
        )
        await websocket.send(encode_json_event(EVENT_FINISH_SESSION, {}, session_id=session_id))

        while True:
            frame = await _receive_frame(websocket, config.timeout_seconds)
            append_jsonl(raw_events, frame_to_log(frame))
            if frame.message_type == MESSAGE_AUDIO_ONLY_RESPONSE or frame.event == EVENT_TTS_RESPONSE:
                if frame.payload:
                    audio_chunks.append(frame.payload)
            parsed = frame.json_payload
            if parsed is not None:
                json_payloads.append(parsed)
            if frame.event == EVENT_SESSION_FAILED:
                raise DoubaoError(f"Doubao session failed: {parsed or frame.payload!r}")
            if frame.event == EVENT_SESSION_FINISHED:
                metadata["session_result"] = parsed
                break

        await websocket.send(encode_json_event(EVENT_FINISH_CONNECTION, {}))
    finally:
        await websocket.close()

    if not audio_chunks:
        raise DoubaoError(
            "Doubao returned no audio bytes. Inspect the raw event log and verify the speaker/model combination."
        )
    output_audio.write_bytes(b"".join(audio_chunks))
    subtitles = normalize_doubao_subtitles(json_payloads)
    metadata["subtitle_count"] = len(subtitles)
    metadata["audio_bytes"] = output_audio.stat().st_size
    return subtitles, metadata


def _concat_audio(parts: list[tuple[Path, int]], output: Path, sample_rate: int, log: Path) -> None:
    """Concatenate audio parts and explicit pauses through one FFmpeg filter graph."""
    if len(parts) == 1 and parts[0][1] == 0:
        shutil.copy2(parts[0][0], output)
        return

    args: list[str] = ["ffmpeg", "-y"]
    labels: list[str] = []
    input_index = 0
    for audio_path, pause_ms in parts:
        args.extend(["-i", str(audio_path)])
        labels.append(f"[{input_index}:a]")
        input_index += 1
        if pause_ms > 0:
            args.extend(
                [
                    "-f",
                    "lavfi",
                    "-t",
                    f"{pause_ms/1000:.6f}",
                    "-i",
                    f"anullsrc=r={sample_rate}:cl=mono",
                ]
            )
            labels.append(f"[{input_index}:a]")
            input_index += 1

    filter_complex = "".join(labels) + f"concat=n={len(labels)}:v=0:a=1[outa]"
    args.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[outa]",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            str(output),
        ]
    )
    run_command(args, log_path=log)


def synthesize_plan(
    *,
    plan: dict[str, Any],
    output_dir: Path,
    config: DoubaoConfig,
    log_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    chunks = plan.get("chunks") or []
    if not chunks:
        raise ValueError("narration_plan.json contains no chunks")

    ensure_dir(output_dir)
    ensure_dir(log_dir)
    section_id = str(uuid.uuid4())
    global_instruction = str(plan.get("global_instruction", "")).strip()
    audio_parts: list[tuple[Path, int]] = []
    all_segments: list[dict[str, Any]] = []
    chunk_meta: list[dict[str, Any]] = []
    offset = 0.0

    for index, chunk in enumerate(chunks, start=1):
        chunk_id = str(chunk.get("id") or f"chunk_{index:03d}")
        text = str(chunk.get("text", "")).strip()
        if not text:
            raise ValueError(f"Narration chunk {chunk_id} has empty text")
        instruction = str(chunk.get("instruction") or global_instruction).strip()
        pause_ms = int(chunk.get("pause_after_ms", 0))
        chunk_audio = output_dir / f"{chunk_id}.mp3"
        raw_events = log_dir / f"doubao_{chunk_id}_events.jsonl"

        subtitles, metadata = asyncio.run(
            synthesize_once(
                text=text,
                instruction=instruction,
                output_audio=chunk_audio,
                raw_events=raw_events,
                config=config,
                section_id=section_id,
            )
        )
        duration = media_duration(chunk_audio)
        for segment in subtitles:
            shifted = dict(segment)
            shifted["start"] = float(shifted["start"]) + offset
            shifted["end"] = float(shifted["end"]) + offset
            shifted["words"] = [
                {
                    **word,
                    "start": float(word["start"]) + offset,
                    "end": float(word["end"]) + offset,
                }
                for word in shifted.get("words", [])
            ]
            all_segments.append(shifted)
        metadata.update({"chunk_id": chunk_id, "duration": duration, "pause_after_ms": pause_ms})
        chunk_meta.append(metadata)
        audio_parts.append((chunk_audio, pause_ms))
        offset += duration + pause_ms / 1000.0

    output_audio = output_dir / "narration.mp3"
    _concat_audio(audio_parts, output_audio, config.sample_rate, log_dir / "ffmpeg_audio.log")
    final_duration = media_duration(output_audio)
    timeline = normalize_timeline(
        all_segments,
        source="doubao-tts-2.0",
        audio_file=str(output_audio),
        duration=final_duration,
    )
    write_json(output_dir / "doubao_metadata.json", {"chunks": chunk_meta})
    write_json(output_dir.parent / "timeline.json", timeline)
    write_srt(output_dir.parent / "subtitles.srt", timeline["segments"])
    return output_audio, timeline


def config_from_project(project: dict[str, Any]) -> DoubaoConfig:
    tts = project.get("tts", {})
    api_key = os.getenv("DOUBAO_API_KEY", "").strip()
    if not api_key:
        raise DoubaoError(
            "DOUBAO_API_KEY is not set. Create or open a Doubao Speech application at "
            "https://console.volcengine.com/speech/app and copy its API key. "
            "A speaker ID is not required when project.tts.voice_profile uses a built-in profile."
        )
    speaker, _source = resolve_speaker(tts)
    return DoubaoConfig(
        api_key=api_key,
        speaker=speaker,
        model=str(tts.get("model", "seed-tts-2.0-expressive")),
        audio_format=str(tts.get("format", "mp3")),
        sample_rate=int(tts.get("sample_rate", 24000)),
        bit_rate=int(tts.get("bit_rate", 128000)),
        speech_rate=float(tts.get("speech_rate", 0)),
        loudness_rate=float(tts.get("loudness_rate", 0)),
        emotion=tts.get("emotion") or None,
        emotion_scale=float(tts.get("emotion_scale", 4)),
    )
