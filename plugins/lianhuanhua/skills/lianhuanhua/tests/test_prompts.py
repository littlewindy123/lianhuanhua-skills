from __future__ import annotations

import json
import zipfile

import pytest
from PIL import Image

from lianhuanhua.prompts import build_panel_prompts, ensure_identity_research_ready
from lianhuanhua.schema_validation import validate_data, validate_file
from lianhuanhua.utils import read_json, write_json
from lianhuanhua.validation import validate_workspace
from lianhuanhua.workspace import initialize_workspace


def test_build_prompts_writes_external_prompt_pack(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "prompts")

    manifest = build_panel_prompts(ws.root)

    assert len(manifest["panels"]) == 1
    pack_md = ws.output / "image_prompt_pack.md"
    pack_json = ws.output / "image_prompt_pack.json"
    assert pack_md.exists()
    assert pack_json.exists()
    assert (ws.output / "prompts-package.zip").exists()
    assert (ws.output / "prompts.json").exists()

    data = json.loads(pack_json.read_text(encoding="utf-8"))
    assert data["image_workflow"] == {"mode": "codex", "review": "none", "repair": "ask"}
    assert data["panels"][0]["shot_id"] == "shot_001"
    assert "Output path" in data["panels"][0]["prompt"]
    assert "Copy this whole file into GPT" in pack_md.read_text(encoding="utf-8")

    with zipfile.ZipFile(ws.output / "prompts-package.zip") as archive:
        names = set(archive.namelist())
    assert {"README.md", "prompts.md", "prompts.csv", "prompts.json", "panels/panel_001.txt"} <= names


def test_default_character_bible_identity_research_schema_is_valid(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "identity-schema")

    character = read_json(ws.work / "character_bible.json")

    assert character["identity_research"]["status"] == "pending"
    assert validate_file(ws.work / "character_bible.json") == []


def test_identified_known_ip_identity_research_schema_is_valid() -> None:
    character = {
        "character_id": "main_character",
        "summary": "Use the uploaded reference image as the identity lock.",
        "reference_images": ["input/character/reference_001.png"],
        "immutable_features": {"reference_lock": "match uploaded reference"},
        "mutable_features": ["pose", "expression"],
        "forbidden_changes": ["Do not redesign the character."],
        "uncertain_features": [],
        "character_sheet": None,
        "identity_research": {
            "status": "identified",
            "is_known_ip": True,
            "ip_name": "一猫人",
            "aliases": ["一猫人表情包"],
            "creator_or_owner": "大熊猫本猫",
            "source_urls": ["https://www.digitaling.com/projects/148078.html"],
            "confidence": "high",
            "observable_traits": ["猫人形象", "头顶红色文字标记"],
            "prompt_identity": "一猫人，按用户上传参考图锁定角色身份和可观察特征",
        },
    }

    assert validate_data(character, "character_bible.schema.json") == []


def test_known_ip_identity_is_injected_into_panel_prompt(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "known-ip-prompt")
    character = read_json(ws.work / "character_bible.json")
    character["identity_research"] = {
        "status": "identified",
        "is_known_ip": True,
        "ip_name": "一猫人",
        "aliases": ["一猫人表情包"],
        "creator_or_owner": "大熊猫本猫",
        "source_urls": ["https://www.digitaling.com/projects/148078.html"],
        "confidence": "high",
        "observable_traits": ["猫人形象", "头顶红色文字标记"],
        "prompt_identity": "一猫人，结合用户上传参考图生成，不要改写成普通猫或小熊",
    }
    write_json(ws.work / "character_bible.json", character)

    build_panel_prompts(ws.root)
    prompt = (ws.prompts_dir / "shot_001.md").read_text(encoding="utf-8")

    assert "## KNOWN CHARACTER / IP IDENTITY" in prompt
    assert "一猫人" in prompt
    assert "不要改写成普通猫或小熊" in prompt


def test_pending_identity_research_blocks_codex_image_generation_when_reference_exists(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "pending-identity")
    Image.new("RGB", (96, 96), (240, 230, 220)).save(ws.input / "character" / "character.png")

    with pytest.raises(ValueError, match="identity research is pending"):
        ensure_identity_research_ready(ws.root)


def test_require_images_does_not_require_visual_reviews_by_default(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "images")
    Image.new("RGB", (1080, 1920), (240, 230, 220)).save(ws.panels_dir / "panel_001.png")
    (ws.work / "panel_reviews.json").unlink()

    assert validate_workspace(ws.root, require_images=True) == []


def test_strict_review_requires_panel_reviews(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "strict")
    Image.new("RGB", (1080, 1920), (240, 230, 220)).save(ws.panels_dir / "panel_001.png")
    (ws.work / "panel_reviews.json").unlink()

    project = json.loads(ws.project.read_text(encoding="utf-8"))
    project["image_workflow"]["review"] = "strict"
    ws.project.write_text(json.dumps(project), encoding="utf-8")

    errors = validate_workspace(ws.root, require_images=True)
    assert "Missing visual review for shot_001" in errors


def test_require_images_rejects_bad_aspect_ratio(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "bad-aspect")
    Image.new("RGB", (1920, 1080), (240, 230, 220)).save(ws.panels_dir / "panel_001.png")

    errors = validate_workspace(ws.root, require_images=True)
    assert any("aspect ratio differs" in error for error in errors)
