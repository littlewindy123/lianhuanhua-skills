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


def build_panel_prompts(workspace: Path) -> dict[str, Any]:
    work = workspace / "work"
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
    if character_sheet:
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
    return manifest
