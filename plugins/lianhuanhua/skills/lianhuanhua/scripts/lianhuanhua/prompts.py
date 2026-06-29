from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from .utils import ensure_dir, read_json, write_json


def _fmt_mapping(mapping: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in mapping.items():
        if isinstance(value, list):
            value_text = ", ".join(str(item) for item in value)
        else:
            value_text = str(value)
        lines.append(f"- {key}: {value_text}")
    return "\n".join(lines)


def _image_workflow(project: dict[str, Any]) -> dict[str, str]:
    configured = project.get("image_workflow", {})
    return {
        "mode": str(configured.get("mode", "ask")),
        "review": str(configured.get("review", "none")),
        "repair": str(configured.get("repair", "ask")),
    }


READY_IDENTITY_RESEARCH_STATUSES = {"searched", "identified", "unidentified", "not_needed"}


def _workspace_reference_exists(workspace: Path, value: str) -> bool:
    path = Path(value)
    if not path.is_absolute():
        path = workspace / path
    return path.exists()


def _identity_research(character: dict[str, Any]) -> dict[str, Any]:
    research = character.get("identity_research")
    if isinstance(research, dict):
        return research
    has_refs = bool(character.get("reference_images"))
    return {
        "status": "pending" if has_refs else "not_needed",
        "is_known_ip": False,
        "ip_name": "",
        "aliases": [],
        "creator_or_owner": "",
        "source_urls": [],
        "confidence": "low",
        "observable_traits": [],
        "prompt_identity": "",
    }


def ensure_identity_research_ready(workspace: Path) -> None:
    character = read_json(workspace / "work" / "character_bible.json")
    references = [str(value) for value in character.get("reference_images", []) if str(value)]
    has_existing_reference = any(_workspace_reference_exists(workspace, value) for value in references)
    research = _identity_research(character)
    status = str(research.get("status", "pending"))
    if has_existing_reference and status not in READY_IDENTITY_RESEARCH_STATUSES:
        raise ValueError(
            "Reference image identity research is pending. Search the web for suspected IP, meme, logo, "
            "or known character identity first, then record identity_research in work/character_bible.json."
        )


def _fmt_identity_research(research: dict[str, Any]) -> str:
    aliases = ", ".join(str(item) for item in research.get("aliases", [])) or "none"
    sources = ", ".join(str(item) for item in research.get("source_urls", [])) or "none"
    traits = "; ".join(str(item) for item in research.get("observable_traits", [])) or "none recorded"
    return "\n".join(
        [
            f"- Status: {research.get('status', '')}",
            f"- Known IP: {bool(research.get('is_known_ip'))}",
            f"- IP name: {research.get('ip_name', '')}",
            f"- Aliases: {aliases}",
            f"- Creator or owner: {research.get('creator_or_owner', '')}",
            f"- Source URLs: {sources}",
            f"- Confidence: {research.get('confidence', '')}",
            f"- Observable traits: {traits}",
            f"- Prompt identity: {research.get('prompt_identity', '')}",
        ]
    )


def _write_prompt_pack(
    workspace: Path,
    *,
    project: dict[str, Any],
    manifest: dict[str, Any],
    storyboard: dict[str, Any],
) -> None:
    output_dir = ensure_dir(workspace / "output")
    prompt_pack_json = output_dir / "image_prompt_pack.json"
    prompt_pack_md = output_dir / "image_prompt_pack.md"
    workflow = _image_workflow(project)
    video = project.get("video", {})

    panels: list[dict[str, Any]] = []
    for panel in manifest["panels"]:
        prompt_path = workspace / panel["prompt_file"]
        panels.append(
            {
                **panel,
                "prompt": prompt_path.read_text(encoding="utf-8"),
            }
        )

    pack = {
        "version": project.get("version", "0.1"),
        "image_workflow": workflow,
        "target": {
            "width": video.get("width", 1080),
            "height": video.get("height", 1920),
            "aspect_ratio": "9:16",
        },
        "instructions": [
            "External mode: copy these prompts into GPT or another image generator, generate all panels, and save them with the exact output filenames.",
            "Codex should not call image generation or visual review unless the user explicitly chooses it.",
            "Default validation is low-cost only: file existence, readability, target aspect ratio, schemas, and ffprobe output checks.",
        ],
        "panels": panels,
    }
    write_json(prompt_pack_json, pack)

    lines = [
        "# Lianhuanhua image prompt pack",
        "",
        "Copy this whole file into GPT or another image generator and ask it to generate every panel.",
        "Save returned images using the exact `Output path` shown for each panel, then put them back into this workspace.",
        "",
        "## Low-token workflow",
        "",
        f"- Mode: `{workflow['mode']}`",
        f"- Review: `{workflow['review']}` (default means no Codex visual review)",
        f"- Repair: `{workflow['repair']}`",
        f"- Target size: `{video.get('width', 1080)}x{video.get('height', 1920)}`",
        "- Codex will only perform low-cost file/schema/FFmpeg checks unless you explicitly ask it to inspect or repair an image.",
        "",
        "## Required output files",
        "",
    ]
    for panel in panels:
        refs = ", ".join(panel.get("references", [])) or "none"
        lines.extend(
            [
                f"### {panel['shot_id']}",
                "",
                f"- Output path: `{panel['output_file']}`",
                f"- Generation mode: `{panel['mode']}`",
                f"- Anchor: `{bool(panel.get('is_anchor'))}`",
                f"- References: {refs}",
                "",
                "```text",
                panel["prompt"].rstrip(),
                "```",
                "",
            ]
        )
    prompt_pack_md.write_text("\n".join(lines), encoding="utf-8")
    _write_manual_prompt_package(
        workspace,
        project=project,
        manifest=manifest,
        storyboard=storyboard,
        panel_prompts=panels,
    )


def _timeline_segments(workspace: Path) -> dict[str, dict[str, Any]]:
    timeline_path = workspace / "work" / "timeline.json"
    if not timeline_path.exists():
        return {}
    timeline = read_json(timeline_path)
    return {str(segment.get("id")): segment for segment in timeline.get("segments", [])}


def _panel_id(index: int, shot: dict[str, Any]) -> str:
    image_name = Path(str(shot.get("image", ""))).stem
    if image_name.startswith("panel_"):
        return image_name
    return f"panel_{index:03d}"


def _narration_for_shot(segments: dict[str, dict[str, Any]], shot: dict[str, Any]) -> str:
    shot_start = float(shot.get("start", 0))
    shot_end = float(shot.get("end", 0))
    texts: list[str] = []
    for segment in segments.values():
        start = float(segment.get("start", 0))
        end = float(segment.get("end", 0))
        if start >= shot_start - 0.05 and end <= shot_end + 0.05:
            texts.append(str(segment.get("text", "")))
    if texts:
        return "".join(texts)
    return str(segments.get(str(shot.get("segment_id")), {}).get("text", ""))


def _manual_prompt_rows(
    workspace: Path,
    *,
    project: dict[str, Any],
    storyboard: dict[str, Any],
    panel_prompts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    segments = _timeline_segments(workspace)
    prompts_by_shot = {item["shot_id"]: item["prompt"] for item in panel_prompts}
    video = storyboard.get("video", {}) or project.get("video", {})
    size = f"{int(video.get('width', 1080))}x{int(video.get('height', 1920))}"
    rows: list[dict[str, Any]] = []
    for index, shot in enumerate(storyboard.get("shots", []), start=1):
        panel_id = _panel_id(index, shot)
        prompt = prompts_by_shot.get(shot["id"], "")
        rows.append(
            {
                "panel_id": panel_id,
                "start": float(shot.get("start", 0)),
                "end": float(shot.get("end", 0)),
                "narration": _narration_for_shot(segments, shot),
                "image_description": str(shot.get("visual_action", "")),
                "prompt_cn": prompt,
                "prompt_en": prompt,
                "size": size,
                "filename": f"{panel_id}.png",
            }
        )
    return rows


def _write_manual_prompt_package(
    workspace: Path,
    *,
    project: dict[str, Any],
    manifest: dict[str, Any],
    storyboard: dict[str, Any],
    panel_prompts: list[dict[str, Any]],
) -> None:
    del manifest
    output_dir = ensure_dir(workspace / "output")
    rows = _manual_prompt_rows(
        workspace,
        project=project,
        storyboard=storyboard,
        panel_prompts=panel_prompts,
    )
    video = storyboard.get("video", {}) or project.get("video", {})
    width = int(video.get("width", 1080))
    height = int(video.get("height", 1920))
    ratio = f"{width}:{height}"
    if width == 1080 and height == 1920:
        ratio = "9:16"

    prompts_json = {
        "version": "1.0",
        "project": {
            "ratio": ratio,
            "size": f"{width}x{height}",
            "style": project.get("mood", ""),
        },
        "panels": rows,
    }
    write_json(output_dir / "prompts.json", prompts_json)

    readme = "\n".join(
        [
            "# Lianhuanhua 手动生图提示词包",
            "",
            f"- 总图片数量: {len(rows)}",
            f"- 视频比例: {ratio}",
            f"- 推荐尺寸: {width}x{height}",
            "- 角色一致性: 保持主角外观、比例、服饰、颜色和画风一致。",
            "- 禁止事项: 不要在图片中生成字幕、水印、Logo 或多余文字。",
            "- 回传文件名: 使用 panel_001.png、panel_002.png 这样的三位编号。",
            "",
        ]
    )
    prompts_md_lines = ["# Prompts", ""]
    for row in rows:
        prompts_md_lines.extend(
            [
                f"## {row['panel_id']}",
                "",
                f"- 旁白: {row['narration']}",
                f"- 时间: {row['start']:.3f} - {row['end']:.3f}",
                f"- 画面描述: {row['image_description']}",
                f"- 推荐尺寸: {row['size']}",
                f"- 回传文件名: {row['filename']}",
                "",
                "### 中文提示词",
                "",
                str(row["prompt_cn"]).rstrip(),
                "",
                "### English Prompt",
                "",
                str(row["prompt_en"]).rstrip(),
                "",
            ]
        )

    csv_buffer = io.StringIO()
    writer = csv.DictWriter(
        csv_buffer,
        fieldnames=[
            "panel_id",
            "narration",
            "start",
            "end",
            "image_description",
            "prompt_cn",
            "prompt_en",
            "size",
            "filename",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)

    zip_path = output_dir / "prompts-package.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.md", readme)
        archive.writestr("prompts.md", "\n".join(prompts_md_lines))
        archive.writestr("prompts.csv", csv_buffer.getvalue())
        archive.writestr("prompts.json", json.dumps(prompts_json, ensure_ascii=False, indent=2) + "\n")
        for row in rows:
            archive.writestr(f"panels/{row['panel_id']}.txt", str(row["prompt_cn"]).rstrip() + "\n")


def build_panel_prompts(workspace: Path) -> dict[str, Any]:
    work = workspace / "work"
    project = read_json(workspace / "project.json")
    character = read_json(work / "character_bible.json")
    style = read_json(work / "style_bible.json")
    storyboard = read_json(work / "storyboard.json")
    identity_research = _identity_research(character)
    continuity_path = work / "continuity_ledger.json"
    continuity = read_json(continuity_path) if continuity_path.exists() else {"shots": []}
    continuity_by_shot = {item["shot_id"]: item for item in continuity.get("shots", [])}

    prompt_dir = ensure_dir(work / "prompts")
    manifest: dict[str, Any] = {"panels": []}
    references = list(character.get("reference_images", []))
    character_sheet = character.get("character_sheet")
    character_sheet_path = workspace / character_sheet if character_sheet else None
    if character_sheet and character_sheet_path and character_sheet_path.exists():
        references.append(character_sheet)

    previous_image: str | None = None
    nearest_anchor: str | None = None

    for shot in storyboard.get("shots", []):
        if shot.get("is_anchor"):
            nearest_anchor = shot["image"]
        shot_state = continuity_by_shot.get(shot["id"], {}).get("state", {})
        mode = "generate"
        if previous_image and not shot.get("is_anchor"):
            mode = "edit_previous_panel"

        panel_refs = list(references)
        if nearest_anchor and nearest_anchor not in panel_refs and nearest_anchor != shot["image"]:
            panel_refs.append(nearest_anchor)
        if previous_image and previous_image not in panel_refs:
            panel_refs.append(previous_image)

        prompt = f"""# Panel {shot['id']}

## Generation mode
{mode}

## Output path
{shot['image']}

## GLOBAL STYLE LOCK
- Visual style: {style.get('visual_style', '')}
- Line style: {style.get('line_style', '')}
- Palette: {', '.join(style.get('palette', []))}
- Shading: {style.get('shading', '')}
- Background: {style.get('background', '')}
- Lighting: {style.get('lighting', '')}
- Texture: {style.get('texture', '')}
- Aspect ratio: {style.get('aspect_ratio', '9:16')}
- Forbidden styles: {', '.join(style.get('forbidden_styles', []))}

## CHARACTER IDENTITY LOCK
{_fmt_mapping(character.get('immutable_features', {}))}

Character summary: {character.get('summary', '')}

## KNOWN CHARACTER / IP IDENTITY
{_fmt_identity_research(identity_research)}

## FORBIDDEN CHARACTER CHANGES
{chr(10).join('- ' + item for item in character.get('forbidden_changes', []))}

## CONTINUITY STATE
{_fmt_mapping(shot_state) if shot_state else '- Use the storyboard scene and character state exactly.'}

## PREVIOUS PANEL SUMMARY
{shot.get('previous_panel_summary', '')}

## CURRENT VISUAL ACTION
{shot.get('visual_action', '')}

## CHARACTER STATE
{shot.get('character_state', '')}

## SCENE STATE
{shot.get('scene_state', '')}

## CAMERA AND COMPOSITION
{shot.get('composition', '')}

## EXECUTION RULES
- Keep the same main character, proportions, colors, accessories, and drawing style.
- Change only what the current action and continuity state require.
- Do not add text, captions, watermarks, logos, extra characters, or unrequested props.
- Preserve clear negative space for subtitles when possible.
- For edit mode, preserve every correct part of the previous panel and modify only the requested change.
"""
        prompt_path = prompt_dir / f"{shot['id']}.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        manifest["panels"].append(
            {
                "shot_id": shot["id"],
                "prompt_file": str(prompt_path.relative_to(workspace)),
                "output_file": shot["image"],
                "mode": mode,
                "references": panel_refs,
                "is_anchor": bool(shot.get("is_anchor")),
            }
        )
        previous_image = shot["image"]

    write_json(prompt_dir / "manifest.json", manifest)
    _write_prompt_pack(workspace, project=project, manifest=manifest, storyboard=storyboard)
    return manifest
