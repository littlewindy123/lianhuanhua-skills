from __future__ import annotations

import shutil
from pathlib import Path

from .utils import ensure_dir


def export_project(workspace: Path) -> list[Path]:
    work = workspace / "work"
    output = ensure_dir(workspace / "output")
    exported: list[Path] = []

    direct_files = [
        (work / "timeline.json", output / "timeline.json"),
        (work / "subtitles.srt", output / "subtitles.srt"),
        (work / "storyboard.json", output / "storyboard.json"),
        (work / "character_bible.json", output / "character_bible.json"),
        (work / "style_bible.json", output / "style_bible.json"),
        (work / "continuity_ledger.json", output / "continuity_ledger.json"),
        (work / "panel_reviews.json", output / "panel_reviews.json"),
    ]
    for source, target in direct_files:
        if source.exists():
            shutil.copy2(source, target)
            exported.append(target)

    audio_candidates = list((work / "audio").glob("narration.*"))
    if not audio_candidates:
        audio_candidates = [work / "audio" / "extracted.wav"]
    for source in audio_candidates[:1]:
        if source.exists():
            target = output / source.name
            shutil.copy2(source, target)
            exported.append(target)

    panel_source = work / "panels"
    panel_target = output / "panels"
    if panel_source.exists():
        if panel_target.exists():
            shutil.rmtree(panel_target)
        shutil.copytree(panel_source, panel_target)
        exported.append(panel_target)

    prompt_source = work / "prompts"
    prompt_target = output / "prompts"
    if prompt_source.exists():
        if prompt_target.exists():
            shutil.rmtree(prompt_target)
        shutil.copytree(prompt_source, prompt_target)
        exported.append(prompt_target)

    return exported
