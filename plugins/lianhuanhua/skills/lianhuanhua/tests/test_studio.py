from __future__ import annotations

import json

import pytest
from PIL import Image

from lianhuanhua.schema_validation import validate_file
from lianhuanhua.studio import (
    generate_storyboard,
    save_project_settings,
    studio_snapshot,
    update_storyboard_timeline,
    write_studio_action,
)
from lianhuanhua.utils import read_json, write_json
from lianhuanhua.validation import validate_manual_panels
from lianhuanhua.workspace import initialize_workspace


def test_initialize_workspace_writes_valid_studio_state(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "studio")

    assert ws.studio_state.exists()
    assert validate_file(ws.studio_state) == []


def test_manual_panel_validation_reports_deterministic_errors(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "manual-panels")
    Image.new("RGB", (1080, 1920), (240, 230, 220)).save(ws.panels_dir / "panel_001.png")

    result = validate_manual_panels(
        ws.root,
        filenames=["panel_001.png", "panel_001.png", "panel_999.png", "bad-name.png"],
    )

    assert not result["ok"]
    assert "panel_001.png" in result["duplicates"]
    assert "bad-name.png" in result["invalid_names"]
    assert "panel_999.png" in result["unexpected"]


def test_regenerate_panel_action_preserves_single_panel_scope(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "single-panel")

    write_studio_action(
        ws.root,
        {
            "stage": "images",
            "action": "regenerate_panel",
            "panel_id": "panel_004",
            "feedback": "画面太亮",
            "prompt": "更近一点",
        },
    )

    state = json.loads(ws.studio_state.read_text(encoding="utf-8"))
    assert state["action"] == "regenerate_panel"
    assert state["panel_id"] == "panel_004"
    assert "all_panels" not in state


def test_studio_snapshot_exposes_audio_and_character_preview(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "snapshot")
    Image.new("RGB", (128, 128), (240, 230, 220)).save(ws.input / "character" / "character.png")
    (ws.audio_dir / "narration.mp3").write_bytes(b"fake-audio")
    project = read_json(ws.project)
    project["paths"]["character_images"] = ["input/character/character.png"]
    write_json(ws.project, project)

    snapshot = studio_snapshot(ws.root)

    assert snapshot["audio"]["exists"] is True
    assert snapshot["audio"]["url"] == "/api/audio/narration.mp3"
    assert snapshot["character_images"][0]["url"] == "/api/character/character.png"


def test_save_project_settings_supports_style_only_codex_flow(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "style-only")

    project = save_project_settings(
        ws.root,
        {
            "story": "只靠风格描述也能开始。",
            "style_prompt": "黑白铅笔连环画",
            "character_identity_hint": "一猫人",
            "image_density": "three_sentences",
            "variation_strength": "明显",
            "image_provider": "codex",
        },
    )

    assert project["paths"]["character_images"] == []
    assert project["visual"]["style_prompt"] == "黑白铅笔连环画"
    assert project["visual"]["character_identity_hint"] == "一猫人"
    assert project["storyboard"]["image_density"] == "three_sentences"
    assert project["storyboard"]["variation_strength"] == "明显"
    assert project["image_workflow"]["mode"] == "codex"


def test_generate_storyboard_marks_confirmation_node_ready(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "storyboard-ready")
    write_json(
        ws.timeline,
        {
            "duration": 6.0,
            "segments": [
                {"id": "seg_001", "start": 0.0, "end": 2.0, "text": "第一句。"},
                {"id": "seg_002", "start": 2.1, "end": 4.0, "text": "第二句。"},
                {"id": "seg_003", "start": 4.1, "end": 6.0, "text": "第三句。"},
            ],
        },
    )

    result = generate_storyboard(
        ws.root,
        {
            "style_prompt": "柔和水彩",
            "image_density": "three_sentences",
            "image_provider": "codex",
        },
    )
    state = read_json(ws.studio_state)

    assert len(result["storyboard"]["shots"]) == 1
    assert state["action"] == "confirm_storyboard"
    assert state["node_status"]["voice"] == "confirmed"
    assert state["node_status"]["storyboard"] == "ready"
    assert (ws.output / "prompts-package.zip").exists()


def test_generate_storyboard_uses_user_identity_hint_and_variation(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "identity-variation")
    write_json(
        ws.timeline,
        {
            "duration": 4.0,
            "segments": [
                {"id": "seg_001", "start": 0.0, "end": 2.0, "text": "第一句。"},
                {"id": "seg_002", "start": 2.0, "end": 4.0, "text": "第二句。"},
            ],
        },
    )

    result = generate_storyboard(
        ws.root,
        {
            "character_identity_hint": "一猫人",
            "style_prompt": "可爱连环画",
            "image_density": "one_per_sentence",
            "variation_strength": "明显",
            "image_provider": "codex",
        },
    )
    character = read_json(ws.work / "character_bible.json")
    prompt = (ws.prompts_dir / "shot_001.md").read_text(encoding="utf-8")

    assert character["user_identity_hint"] == "一猫人"
    assert character["identity_research"]["prompt_identity"] == "一猫人"
    assert "一猫人" in prompt
    assert all(shot["camera"] for shot in result["storyboard"]["shots"])


def test_update_storyboard_timeline_updates_motion_and_rebuilds_prompts(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "timeline-update")

    result = update_storyboard_timeline(
        ws.root,
        {
            "shots": [
                {
                    "id": "shot_001",
                    "start": 0.25,
                    "end": 4.5,
                    "motion": {"type": "slow_zoom_in"},
                }
            ]
        },
    )
    storyboard = read_json(ws.work / "storyboard.json")

    assert result["storyboard"]["shots"][0]["start"] == 0.25
    assert storyboard["shots"][0]["end"] == 4.5
    assert storyboard["shots"][0]["motion"]["type"] == "slow_zoom_in"
    assert (ws.output / "prompts-package.zip").exists()


def test_update_storyboard_timeline_rejects_negative_duration(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "timeline-invalid")

    with pytest.raises(ValueError, match="non-positive duration"):
        update_storyboard_timeline(
            ws.root,
            {"shots": [{"id": "shot_001", "start": 2.0, "end": 1.0, "motion": {"type": "hold"}}]},
        )
