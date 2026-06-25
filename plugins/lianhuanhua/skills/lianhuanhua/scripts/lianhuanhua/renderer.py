from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any

from .utils import ensure_dir, read_json, resolve_workspace_path, run_command


TRANSITION_MAP = {
    "cut": "fade",
    "fade": "fade",
    "dissolve": "dissolve",
    "fadeblack": "fadeblack",
}


def _zoompan_filter(
    *,
    width: int,
    height: int,
    fps: int,
    frames: int,
    motion: dict[str, Any],
) -> str:
    motion_type = motion.get("type", "hold")
    strength = float(motion.get("strength", 0.25))
    strength = min(1.0, max(0.0, strength))
    denominator = max(1, frames - 1)
    delta = 0.05 + 0.10 * strength
    pan_zoom = 1.08 + 0.08 * strength

    if motion_type == "slow_zoom_in":
        z = f"1+{delta:.6f}*on/{denominator}"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif motion_type == "slow_zoom_out":
        z = f"{1+delta:.6f}-{delta:.6f}*on/{denominator}"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif motion_type == "pan_left":
        z = f"{pan_zoom:.6f}"
        x = f"(iw-iw/zoom)*(1-on/{denominator})"
        y = "ih/2-(ih/zoom/2)"
    elif motion_type == "pan_right":
        z = f"{pan_zoom:.6f}"
        x = f"(iw-iw/zoom)*(on/{denominator})"
        y = "ih/2-(ih/zoom/2)"
    elif motion_type == "float_up_down":
        z = f"{1.06 + 0.05 * strength:.6f}"
        x = "iw/2-(iw/zoom/2)"
        y = f"(ih-ih/zoom)/2+((ih-ih/zoom)/8)*sin(2*PI*on/{denominator})"
    else:
        z = "1.0"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"

    source_w = width * 2
    source_h = height * 2
    return (
        f"scale={source_w}:{source_h}:force_original_aspect_ratio=increase,"
        f"crop={source_w}:{source_h},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={width}x{height}:fps={fps},"
        "setsar=1,format=yuv420p"
    )


def _render_clip(
    *,
    image: Path,
    output: Path,
    duration: float,
    width: int,
    height: int,
    fps: int,
    motion: dict[str, Any],
    log_path: Path,
) -> None:
    if not image.exists():
        raise FileNotFoundError(f"Missing panel image: {image}")
    frames = max(1, int(math.ceil(duration * fps)))
    filter_chain = _zoompan_filter(
        width=width,
        height=height,
        fps=fps,
        frames=frames,
        motion=motion,
    )
    run_command(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-vf",
            filter_chain,
            "-frames:v",
            str(frames),
            "-r",
            str(fps),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ],
        log_path=log_path,
    )


def render_silent_video(workspace: Path) -> Path:
    project = read_json(workspace / "project.json")
    storyboard = read_json(workspace / "work" / "storyboard.json")
    video = storyboard.get("video", {})
    width = int(video.get("width", project["video"]["width"]))
    height = int(video.get("height", project["video"]["height"]))
    fps = int(video.get("fps", project["video"]["fps"]))
    shots = storyboard.get("shots", [])
    if not shots:
        raise ValueError("storyboard.json contains no shots")

    temp_dir = ensure_dir(workspace / "work" / "render_clips")
    log_path = workspace / "logs" / "ffmpeg_render.log"
    clip_paths: list[Path] = []
    transitions: list[tuple[str, float]] = []

    for index, shot in enumerate(shots):
        start = float(shot["start"])
        end = float(shot["end"])
        base_duration = end - start
        if base_duration <= 0:
            raise ValueError(f"Shot {shot['id']} has a non-positive duration")

        transition = shot.get("transition_out", {"type": "cut", "duration": 0})
        transition_duration = float(transition.get("duration", 0)) if index < len(shots) - 1 else 0.0
        if index < len(shots) - 1:
            transition_duration = max(0.001, transition_duration)
        extended_duration = base_duration + transition_duration
        image = resolve_workspace_path(workspace, shot["image"])
        assert image is not None
        clip = temp_dir / f"{index:04d}_{shot['id']}.mp4"
        _render_clip(
            image=image,
            output=clip,
            duration=extended_duration,
            width=width,
            height=height,
            fps=fps,
            motion=shot.get("motion", {"type": "hold"}),
            log_path=log_path,
        )
        clip_paths.append(clip)
        transitions.append((str(transition.get("type", "cut")), transition_duration))

    output = workspace / "output" / "silent_video.mp4"
    ensure_dir(output.parent)
    if len(clip_paths) == 1:
        shutil.copy2(clip_paths[0], output)
        return output

    args: list[str] = ["ffmpeg", "-y"]
    for clip in clip_paths:
        args.extend(["-i", str(clip)])

    filters: list[str] = []
    cumulative = float(shots[0]["end"]) - float(shots[0]["start"])
    previous_label = "[0:v]"
    for index in range(1, len(clip_paths)):
        transition_name, transition_duration = transitions[index - 1]
        mapped = TRANSITION_MAP.get(transition_name, "fade")
        output_label = f"[vx{index}]"
        filters.append(
            f"{previous_label}[{index}:v]xfade=transition={mapped}:duration={transition_duration:.6f}:offset={cumulative:.6f}{output_label}"
        )
        previous_label = output_label
        cumulative += float(shots[index]["end"]) - float(shots[index]["start"])

    args.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            previous_label,
            "-an",
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run_command(args, log_path=log_path)
    return output


def _escape_subtitle_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", "\\:").replace("'", "\\'")
    return value


def mux_final_video(workspace: Path, *, burn_subtitles: bool = False) -> Path:
    project = read_json(workspace / "project.json")
    silent = workspace / "output" / "silent_video.mp4"
    narration_candidates = [
        workspace / "work" / "audio" / "narration.mp3",
        workspace / "work" / "audio" / "extracted.wav",
        workspace / "work" / "audio" / "narration.wav",
    ]
    narration = next((path for path in narration_candidates if path.exists()), None)
    if narration is None:
        raise FileNotFoundError("No narration audio found in work/audio")
    if not silent.exists():
        raise FileNotFoundError("silent_video.mp4 does not exist; render it first")

    output = workspace / "output" / "final_video.mp4"
    log_path = workspace / "logs" / "ffmpeg_mux.log"
    args = ["ffmpeg", "-y", "-i", str(silent), "-i", str(narration)]

    subtitles = workspace / "work" / "subtitles.srt"
    if burn_subtitles and subtitles.exists():
        font = project.get("video", {}).get("subtitle_font", "Noto Sans CJK SC")
        escaped = _escape_subtitle_path(subtitles)
        style = (
            f"FontName={font},FontSize=18,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00101010,BorderStyle=1,Outline=2,Shadow=0,"
            "Alignment=2,MarginV=130"
        )
        args.extend(
            [
                "-vf",
                f"subtitles=filename='{escaped}':force_style='{style}'",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
            ]
        )
    else:
        args.extend(["-c:v", "copy"])

    args.extend(
        [
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    run_command(args, log_path=log_path)
    return output
