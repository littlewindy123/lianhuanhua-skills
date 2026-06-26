from __future__ import annotations

import json

from PIL import Image

from lianhuanhua.schema_validation import validate_file
from lianhuanhua.studio import write_studio_action
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
