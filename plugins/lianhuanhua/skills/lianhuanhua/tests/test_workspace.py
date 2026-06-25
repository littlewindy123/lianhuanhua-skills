from __future__ import annotations

from lianhuanhua.validation import validate_workspace
from lianhuanhua.workspace import initialize_workspace


def test_initialize_workspace(tmp_path) -> None:
    ws = initialize_workspace(tmp_path / "demo")
    assert ws.project.exists()
    assert (ws.work / "storyboard.json").exists()
    assert validate_workspace(ws.root) == []
