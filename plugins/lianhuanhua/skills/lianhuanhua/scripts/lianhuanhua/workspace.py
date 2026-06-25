from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from .utils import ensure_dir


@dataclass(frozen=True)
class Workspace:
    root: Path

    @property
    def input(self) -> Path:
        return self.root / "input"

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def output(self) -> Path:
        return self.root / "output"

    @property
    def logs(self) -> Path:
        return self.root / "logs"

    @property
    def project(self) -> Path:
        return self.root / "project.json"

    @property
    def timeline(self) -> Path:
        return self.work / "timeline.json"

    @property
    def storyboard(self) -> Path:
        return self.work / "storyboard.json"

    @property
    def audio_dir(self) -> Path:
        return self.work / "audio"

    @property
    def panels_dir(self) -> Path:
        return self.work / "panels"

    @property
    def prompts_dir(self) -> Path:
        return self.work / "prompts"


def skill_root() -> Path:
    return Path(__file__).resolve().parents[2]


def template_dir() -> Path:
    return skill_root() / "assets" / "templates"


def initialize_workspace(root: Path, force: bool = False) -> Workspace:
    root = root.resolve()
    ws = Workspace(root)
    if root.exists() and any(root.iterdir()) and not force:
        raise FileExistsError(
            f"Workspace is not empty: {root}. Use --force only when overwriting templates is safe."
        )

    for path in [
        ws.input,
        ws.input / "character",
        ws.input / "media",
        ws.work,
        ws.audio_dir,
        ws.panels_dir,
        ws.prompts_dir,
        ws.output,
        ws.logs,
    ]:
        ensure_dir(path)

    mapping = {
        "project.json": ws.project,
        "narration_plan.json": ws.work / "narration_plan.json",
        "character_bible.json": ws.work / "character_bible.json",
        "style_bible.json": ws.work / "style_bible.json",
        "continuity_ledger.json": ws.work / "continuity_ledger.json",
        "storyboard.json": ws.work / "storyboard.json",
        "panel_reviews.json": ws.work / "panel_reviews.json",
    }
    for source_name, target in mapping.items():
        source = template_dir() / source_name
        if force or not target.exists():
            shutil.copy2(source, target)

    story = ws.input / "story.txt"
    if force or not story.exists():
        story.write_text("Replace with the user's narration text.\n", encoding="utf-8")

    return ws
