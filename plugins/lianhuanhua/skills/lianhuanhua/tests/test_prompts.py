from __future__ import annotations

import json
import zipfile

from PIL import Image

from lianhuanhua.prompts import build_panel_prompts
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
    assert data["image_workflow"] == {"mode": "ask", "review": "none", "repair": "ask"}
    assert data["panels"][0]["shot_id"] == "shot_001"
    assert "Output path" in data["panels"][0]["prompt"]
    assert "Copy this whole file into GPT" in pack_md.read_text(encoding="utf-8")

    with zipfile.ZipFile(ws.output / "prompts-package.zip") as archive:
        names = set(archive.namelist())
    assert {"README.md", "prompts.md", "prompts.csv", "prompts.json", "panels/panel_001.txt"} <= names


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
