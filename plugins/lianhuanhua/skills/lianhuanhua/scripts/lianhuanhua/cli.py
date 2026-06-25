from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .doubao_tts import config_from_project, synthesize_plan
from .exporter import export_project
from .media import extract_audio, save_transcription, transcribe_faster_whisper
from .prompts import build_panel_prompts
from .renderer import mux_final_video, render_silent_video
from .subtitles import parse_srt
from .timeline import normalize_timeline, write_timeline_files
from .utils import media_duration, read_json, write_json
from .validation import doctor_ok, doctor_report, validate_output, validate_workspace
from .workspace import initialize_workspace


def _workspace(value: str) -> Path:
    return Path(value).expanduser().resolve()


def cmd_doctor(_args: argparse.Namespace) -> int:
    report = doctor_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if doctor_ok(report) else 2


def cmd_init(args: argparse.Namespace) -> int:
    ws = initialize_workspace(_workspace(args.workspace), force=args.force)
    print(f"Initialized workspace: {ws.root}")
    return 0


def cmd_tts(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    project = read_json(workspace / "project.json")
    plan = read_json(workspace / "work" / "narration_plan.json")
    config = config_from_project(project)
    output_audio, timeline = synthesize_plan(
        plan=plan,
        output_dir=workspace / "work" / "audio",
        config=config,
        log_dir=workspace / "logs",
    )
    print(f"Audio: {output_audio}")
    print(f"Timeline segments: {len(timeline['segments'])}")
    return 0


def _media_mode(input_path: Path) -> str:
    video_suffixes = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
    return "video" if input_path.suffix.lower() in video_suffixes else "audio"


def cmd_extract_media(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    output = workspace / "work" / "audio" / "extracted.wav"
    extract_audio(input_path, output, workspace / "logs" / "ffmpeg_extract.log")

    project_path = workspace / "project.json"
    project = read_json(project_path)
    project["mode"] = _media_mode(input_path)
    project["paths"]["media"] = str(input_path)
    write_json(project_path, project)
    print(f"Extracted audio: {output}")
    return 0


def cmd_transcribe(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    audio = workspace / "work" / "audio" / "extracted.wav"
    if not audio.exists():
        raise FileNotFoundError("Run extract-media first; work/audio/extracted.wav is missing")
    timeline = transcribe_faster_whisper(
        audio,
        model_size=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
    )
    save_transcription(
        timeline,
        workspace / "work" / "timeline.json",
        workspace / "work" / "subtitles.srt",
    )
    print(f"Transcribed {len(timeline['segments'])} segments")
    return 0


def cmd_import_srt(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    srt = Path(args.srt).expanduser().resolve()
    audio = Path(args.audio).expanduser().resolve() if args.audio else None
    segments = parse_srt(srt)
    timeline = normalize_timeline(
        segments,
        source="srt",
        audio_file=str(audio) if audio else None,
        duration=media_duration(audio) if audio else None,
    )
    write_timeline_files(
        timeline,
        workspace / "work" / "timeline.json",
        workspace / "work" / "subtitles.srt",
    )
    if audio:
        target = workspace / "work" / "audio" / f"narration{audio.suffix.lower()}"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(audio, target)
    print(f"Imported {len(segments)} subtitle segments")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    errors = validate_workspace(workspace, require_images=args.require_images)
    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 2
    print("Workspace validation passed")
    return 0


def cmd_build_prompts(args: argparse.Namespace) -> int:
    manifest = build_panel_prompts(_workspace(args.workspace))
    print(f"Created {len(manifest['panels'])} panel prompts")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    silent = render_silent_video(workspace)
    print(f"Silent video: {silent}")
    if args.silent_only:
        return 0
    final = mux_final_video(workspace, burn_subtitles=args.burn_subtitles)
    print(f"Final video: {final}")
    return 0


def cmd_validate_output(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    errors = validate_output(workspace, tolerance_seconds=args.tolerance)
    if errors:
        print("Output validation failed:")
        for error in errors:
            print(f"- {error}")
        return 2
    print("Output validation passed")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    exported = export_project(_workspace(args.workspace))
    print("Exported:")
    for path in exported:
        print(f"- {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lianhuanhua",
        description="Deterministic helpers for the Lianhuanhua Codex skill.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Check Python, FFmpeg, packages, and environment")
    doctor.set_defaults(func=cmd_doctor)

    init = sub.add_parser("init", help="Initialize a workspace")
    init.add_argument("--workspace", required=True)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    tts = sub.add_parser("tts", help="Generate narration with Doubao Speech 2.0")
    tts.add_argument("--workspace", required=True)
    tts.set_defaults(func=cmd_tts)

    extract = sub.add_parser("extract-media", help="Extract normalized WAV from audio/video")
    extract.add_argument("--workspace", required=True)
    extract.add_argument("--input", required=True)
    extract.set_defaults(func=cmd_extract_media)

    transcribe = sub.add_parser("transcribe", help="Transcribe extracted audio using faster-whisper")
    transcribe.add_argument("--workspace", required=True)
    transcribe.add_argument("--model", default="small")
    transcribe.add_argument("--language", default="zh")
    transcribe.add_argument("--device", default="cpu")
    transcribe.add_argument("--compute-type", default="int8")
    transcribe.set_defaults(func=cmd_transcribe)

    import_srt = sub.add_parser("import-srt", help="Import an existing SRT timeline")
    import_srt.add_argument("--workspace", required=True)
    import_srt.add_argument("--srt", required=True)
    import_srt.add_argument("--audio")
    import_srt.set_defaults(func=cmd_import_srt)

    validate = sub.add_parser("validate", help="Validate workspace JSON and semantics")
    validate.add_argument("--workspace", required=True)
    validate.add_argument("--require-images", action="store_true")
    validate.set_defaults(func=cmd_validate)

    prompts = sub.add_parser("build-prompts", help="Build saved image-generation prompts")
    prompts.add_argument("--workspace", required=True)
    prompts.set_defaults(func=cmd_build_prompts)

    render = sub.add_parser("render", help="Render silent and final video")
    render.add_argument("--workspace", required=True)
    render.add_argument("--silent-only", action="store_true")
    render.add_argument("--burn-subtitles", action="store_true")
    render.set_defaults(func=cmd_render)

    validate_out = sub.add_parser("validate-output", help="Validate final deliverables with ffprobe")
    validate_out.add_argument("--workspace", required=True)
    validate_out.add_argument("--tolerance", type=float, default=0.25)
    validate_out.set_defaults(func=cmd_validate_output)

    export = sub.add_parser("export", help="Copy reproducibility artifacts into output/")
    export.add_argument("--workspace", required=True)
    export.set_defaults(func=cmd_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
