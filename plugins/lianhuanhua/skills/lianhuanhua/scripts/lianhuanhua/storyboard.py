from __future__ import annotations

from pathlib import Path
from typing import Any

from .prompts import build_panel_prompts
from .utils import read_json, write_json


DENSITY_SMART = "smart"
DENSITY_ONE_PER_SENTENCE = "one_per_sentence"
DENSITY_THREE_SENTENCES = "three_sentences"
VALID_DENSITIES = {DENSITY_SMART, DENSITY_ONE_PER_SENTENCE, DENSITY_THREE_SENTENCES}

MOTIONS = ["slow_zoom_in", "hold", "pan_right", "slow_zoom_out", "pan_left", "float_up_down"]


def normalize_density(value: str | None) -> str:
    density = (value or DENSITY_SMART).strip()
    if density not in VALID_DENSITIES:
        return DENSITY_SMART
    return density


def group_timeline_segments(segments: list[dict[str, Any]], density: str) -> list[list[dict[str, Any]]]:
    density = normalize_density(density)
    if density == DENSITY_ONE_PER_SENTENCE:
        return [[segment] for segment in segments]
    if density == DENSITY_THREE_SENTENCES:
        return [segments[index : index + 3] for index in range(0, len(segments), 3)]

    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for segment in segments:
        current.append(segment)
        start = float(current[0]["start"])
        end = float(current[-1]["end"])
        duration = end - start
        text = "".join(str(item.get("text", "")) for item in current)
        strong_turn = any(mark in text for mark in ("？", "！", "；", "。")) and duration >= 2.0
        if duration >= 4.2 or len(current) >= 2 or strong_turn:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def _shot_description(text: str, index: int, style_prompt: str) -> tuple[str, str, str]:
    base_style = style_prompt or "minimal emotional comic style"
    if index == 1:
        return (
            f"Opening image for: {text}",
            "quietly facing the viewer, emotionally vulnerable",
            f"simple opening scene in {base_style}",
        )
    if any(word in text for word in ("黑名单", "陌生", "删掉")):
        return (
            f"A symbolic phone or distance scene for: {text}",
            "small and rejected, restrained sadness",
            f"phone, empty chat, or distant room in {base_style}",
        )
    if any(word in text for word in ("想念", "失眠", "心痛")):
        return (
            f"A late-night longing scene for: {text}",
            "tired, missing someone, trying not to contact",
            f"night room, phone, bed, or memo notebook in {base_style}",
        )
    if any(word in text for word in ("放下", "纠缠", "忘")):
        return (
            f"A symbolic letting-go scene for: {text}",
            "trying to let go but still attached",
            f"red thread, paper heart, mirror, or dawn light in {base_style}",
        )
    return (
        f"Emotional comic scene for: {text}",
        "gentle reflective sadness",
        f"simple symbolic environment in {base_style}",
    )


def build_storyboard_data(
    *,
    timeline: dict[str, Any],
    project: dict[str, Any],
    density: str,
    style_prompt: str = "",
) -> dict[str, Any]:
    segments = list(timeline.get("segments", []))
    groups = group_timeline_segments(segments, density)
    video = project.get("video", {})
    shots: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        text = "".join(str(segment.get("text", "")) for segment in group)
        start = float(group[0]["start"])
        end = float(group[-1]["end"])
        visual_action, character_state, scene_state = _shot_description(text, index, style_prompt)
        shots.append(
            {
                "id": f"shot_{index:03d}",
                "segment_id": str(group[0].get("id", f"seg_{index:03d}")),
                "scene_id": f"scene_{index:03d}",
                "start": start,
                "end": end,
                "image": f"work/panels/panel_{index:03d}.png",
                "is_anchor": index == 1 or index % 5 == 0,
                "visual_action": visual_action,
                "character_state": character_state,
                "scene_state": scene_state,
                "composition": "clean 16:9 comic frame, main subject readable, clear subtitle-safe negative space",
                "previous_panel_summary": "Opening panel." if index == 1 else f"Continue from shot_{index - 1:03d}.",
                "motion": {
                    "type": MOTIONS[(index - 1) % len(MOTIONS)],
                    "strength": 0.18,
                    "focus_x": 0.5,
                    "focus_y": 0.5,
                },
                "transition_out": {
                    "type": "fade" if index < len(groups) else "fadeblack",
                    "duration": 0.25 if index < len(groups) else 0.0,
                },
            }
        )
    return {
        "version": "0.1",
        "video": {
            "width": int(video.get("width", 1080)),
            "height": int(video.get("height", 1920)),
            "fps": int(video.get("fps", 30)),
            "duration": float(timeline.get("duration", shots[-1]["end"] if shots else 0)),
        },
        "shots": shots,
    }


def build_character_bible(workspace: Path, project: dict[str, Any], style_prompt: str) -> dict[str, Any]:
    refs = [str(path) for path in project.get("paths", {}).get("character_images", []) if str(path)]
    if refs:
        summary = "Use the uploaded reference image as the identity lock. Preserve visible character shape, colors, accessories, and drawing style."
        immutable = {
            "reference_lock": "match the uploaded reference image",
            "style_request": style_prompt or "simple emotional comic character",
        }
        identity_research = {
            "status": "pending",
            "is_known_ip": False,
            "ip_name": "",
            "aliases": [],
            "creator_or_owner": "",
            "source_urls": [],
            "confidence": "low",
            "observable_traits": [],
            "prompt_identity": "",
        }
    else:
        summary = f"AI-designed protagonist based on the style prompt: {style_prompt or 'minimal emotional comic mascot'}."
        immutable = {
            "style_prompt": style_prompt or "minimal emotional comic mascot",
            "identity_rule": "keep one consistent protagonist across all panels",
        }
        identity_research = {
            "status": "not_needed",
            "is_known_ip": False,
            "ip_name": "",
            "aliases": [],
            "creator_or_owner": "",
            "source_urls": [],
            "confidence": "low",
            "observable_traits": [],
            "prompt_identity": "",
        }
    return {
        "character_id": "main_character",
        "summary": summary,
        "reference_images": refs,
        "immutable_features": immutable,
        "mutable_features": ["pose", "expression", "camera angle", "lighting", "background", "props"],
        "forbidden_changes": [
            "Do not redesign the protagonist between panels.",
            "Do not add captions, watermarks, logos, or unrelated text inside the image.",
            "Do not add extra main characters unless explicitly required by the storyboard.",
        ],
        "uncertain_features": [],
        "character_sheet": None,
        "identity_research": identity_research,
    }


def build_style_bible(project: dict[str, Any], style_prompt: str) -> dict[str, Any]:
    width = int(project.get("video", {}).get("width", 1080))
    height = int(project.get("video", {}).get("height", 1920))
    return {
        "visual_style": style_prompt or "minimal emotional 2D comic illustration",
        "line_style": "clean readable linework, stable character proportions",
        "palette": ["warm neutral", "soft gray", "muted coral", "dusty blue", "cream"],
        "shading": "flat restrained shading with very soft shadows",
        "background": "simple symbolic environments, low clutter, clear subtitle-safe space",
        "lighting": "soft diffused emotional light",
        "texture": "subtle paper grain",
        "aspect_ratio": f"{width}:{height}",
        "forbidden_styles": [
            "photorealistic",
            "3D render",
            "busy typography",
            "watermark or logo",
            "extra subtitles inside images",
        ],
    }


def build_continuity_ledger(storyboard: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
    clothing = ["uploaded reference identity"] if project.get("paths", {}).get("character_images") else ["AI-designed consistent protagonist"]
    shots: list[dict[str, Any]] = []
    for index, shot in enumerate(storyboard.get("shots", []), start=1):
        shots.append(
            {
                "shot_id": shot["id"],
                "scene_id": shot.get("scene_id", f"scene_{index:03d}"),
                "previous_shot_id": None if index == 1 else f"shot_{index - 1:03d}",
                "state": {
                    "location": str(shot.get("scene_state", "")),
                    "time_of_day": "unspecified emotional time",
                    "weather": "none",
                    "character_position": "composition follows storyboard",
                    "facing_direction": "composition follows storyboard",
                    "pose": str(shot.get("character_state", "")),
                    "expression": str(shot.get("character_state", "")),
                    "clothing_and_accessories": clothing,
                    "props": [],
                    "emotion": str(shot.get("character_state", "")),
                    "notes": "Carry character identity, style, and important props forward from the previous panel.",
                },
            }
        )
    return {"shots": shots}


def build_storyboard_workspace(workspace: Path) -> dict[str, Any]:
    project = read_json(workspace / "project.json")
    timeline = read_json(workspace / "work" / "timeline.json")
    visual = project.get("visual", {})
    storyboard_options = project.get("storyboard", {})
    density = normalize_density(str(storyboard_options.get("image_density", DENSITY_SMART)))
    style_prompt = str(visual.get("style_prompt") or project.get("mood", ""))

    storyboard = build_storyboard_data(
        timeline=timeline,
        project=project,
        density=density,
        style_prompt=style_prompt,
    )
    write_json(workspace / "work" / "character_bible.json", build_character_bible(workspace, project, style_prompt))
    write_json(workspace / "work" / "style_bible.json", build_style_bible(project, style_prompt))
    write_json(workspace / "work" / "storyboard.json", storyboard)
    write_json(workspace / "work" / "continuity_ledger.json", build_continuity_ledger(storyboard, project))
    manifest = build_panel_prompts(workspace)
    return {"storyboard": storyboard, "manifest": manifest}
