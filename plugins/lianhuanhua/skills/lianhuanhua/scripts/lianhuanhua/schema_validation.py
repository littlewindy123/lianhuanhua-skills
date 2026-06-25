from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .utils import read_json
from .workspace import skill_root


SCHEMA_BY_FILE = {
    "project.json": "project.schema.json",
    "narration_plan.json": "narration_plan.schema.json",
    "timeline.json": "timeline.schema.json",
    "character_bible.json": "character_bible.schema.json",
    "style_bible.json": "style_bible.schema.json",
    "continuity_ledger.json": "continuity_ledger.schema.json",
    "storyboard.json": "storyboard.schema.json",
    "panel_reviews.json": "panel_reviews.schema.json",
}


def schema_path(name: str) -> Path:
    return skill_root() / "assets" / "schemas" / name


def validate_data(data: Any, schema_name: str) -> list[str]:
    schema = read_json(schema_path(schema_name))
    validator = Draft202012Validator(schema)
    errors: list[str] = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


def validate_file(path: Path, schema_name: str | None = None) -> list[str]:
    schema_name = schema_name or SCHEMA_BY_FILE.get(path.name)
    if not schema_name:
        raise ValueError(f"No schema mapping for {path.name}")
    return validate_data(read_json(path), schema_name)
