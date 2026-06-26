from __future__ import annotations

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


def _write_prompt_pack(
    workspace: Path,
    *,
    project: dict[str, Any],
    manifest: dict[str, Any],
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


def build_panel_prompts(workspace: Path) -> dict[str, Any]:
    work = workspace / "work"
    project = read_json(workspace / "project.json")
    character = read_json(work / "character_bible.json")
    style = read_json(work / "style_bible.json")
    storyboard = read_json(work / "storyboard.json")
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
    _write_prompt_pack(workspace, project=project, manifest=manifest)
    return manifest
